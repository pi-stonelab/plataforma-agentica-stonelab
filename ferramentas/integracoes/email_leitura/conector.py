"""E-mail, leitura por IMAP: as mensagens que os lojistas mandaram para a caixa da plataforma.

É uma integração separada do envio (`email`, SMTP): outro servidor, outra credencial e outra chave de liga e
desliga. Uma queda do IMAP não pausa o envio, e o envio pode estar ligado com a leitura desligada.

Configuração (.env): `EMAIL_IMAP_HOST` (preencher liga a leitura), `EMAIL_IMAP_PORTA`, `EMAIL_IMAP_SEGURANCA`
(`ssl`, o padrão, `starttls` ou `nenhuma`, esta só em localhost), `EMAIL_IMAP_USUARIO`, `EMAIL_IMAP_SENHA` e
`EMAIL_IMAP_PASTA` (padrão INBOX). `EMAIL_LEITURA_MODO` força `real`, `simulado` ou `desligado`.

Segurança e LGPD:
- Fora do localhost a conexão é sempre cifrada, com o certificado conferido. A pasta abre só para leitura
  (EXAMINE) e o corpo é lido com BODY.PEEK: nenhuma mensagem fica marcada como lida.
- Só se procura por remetentes que o código passa (os contatos do cadastro do lojista); nada do modelo vai para
  o comando IMAP. O filtro de assunto é feito aqui, depois de ler os cabeçalhos.
- Volta só o necessário: remetente, assunto, data e um trecho do texto, com teto de mensagens e de tamanho. A
  ferramenta mascara e marca tudo como conteúdo de terceiros.
- Erros e logs levam só a etapa e o tipo da falha: nada de host, usuário, senha, endereço ou texto.

No modo simulado, a caixa é montada com as interações por e-mail do mundo simulado (o CRM do mock) e a resposta
diz isso em `fonte`. Protocolo: IMAP4rev1 (RFC 3501), pelo `imaplib` da biblioteca padrão.
"""

import email
import imaplib
import os
import re
import ssl
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

from mock import falhas

from ferramentas import dados_sinteticos
from ferramentas.email_smtp import HOST_RE, HOSTS_LOCAIS, PORTA_RE, endereco_valido
from ferramentas.integracoes.cliente_http import CredencialRecusada, RespostaInvalida
from ferramentas.integracoes.conector import Conector, ConfiguracaoInvalida
from ferramentas.integracoes.registro import registrar

SEGURANCAS = ("ssl", "starttls", "nenhuma")
PORTA_PADRAO = {"ssl": 993, "starttls": 143, "nenhuma": 1143}
PADRAO_PASTA = re.compile(r"[A-Za-z0-9 _./\[\]-]{1,60}")  # ASCII e sem aspas: vai entre aspas no comando
PASTA_PADRAO = "INBOX"
TEMPO_LIMITE = 15  # segundos por operação de rede
CABECALHOS_LIDOS_NO_MAXIMO = 50  # quantas mensagens recentes entram no filtro de assunto
TAMANHO_MAXIMO_DA_MENSAGEM = 256_000  # maior que isso, só o cabeçalho é lido
TAMANHO_DO_TRECHO = 1500
TAMANHO_DO_ASSUNTO = 200
MESES_DO_IMAP = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PADRAO_TAG_HTML = re.compile(r"<[^>]{0,500}>")
PADRAO_TAMANHO = re.compile(rb"RFC822\.SIZE (\d{1,12})")
FUSO_DA_CAIXA = ZoneInfo("America/Sao_Paulo")
TRECHO_DE_MENSAGEM_GRANDE = "(mensagem grande demais para mostrar aqui; abra na caixa de e-mail)"
FONTE_REAL = "Caixa de e-mail da plataforma"
FONTE_SIMULADA = "Caixa simulada (modo de demonstração): mensagens do mundo simulado, não de uma caixa de verdade"
MENSAGEM_TESTE_SIMULADO = "Modo simulado: a caixa é montada com o mundo simulado, sem conectar a servidor nenhum."
CANAL_EMAIL = "email"
AUTOR_LOJISTA = "lojista"


@dataclass(frozen=True)
class ConfiguracaoImap:
    host: str
    porta: int
    seguranca: str
    usuario: str
    senha: str = field(repr=False)  # fora do repr: um log da configuração não leva a senha
    pasta: str = PASTA_PADRAO


def data_do_imap(dia):
    """Data no formato do SEARCH do IMAP ("15-Oct-2026"), sem depender do idioma do sistema."""
    return f"{dia.day:02d}-{MESES_DO_IMAP[dia.month - 1]}-{dia.year}"


def criterio_de_remetentes(enderecos):
    """`FROM "a"` ou `OR FROM "a" OR FROM "b" FROM "c"`: qualquer um dos endereços (já validados)."""
    if len(enderecos) == 1:
        return ["FROM", f'"{enderecos[0]}"']
    return ["OR", "FROM", f'"{enderecos[0]}"', *criterio_de_remetentes(enderecos[1:])]


def _texto_do_corpo(mensagem):
    parte = mensagem.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return ""
    try:
        texto = parte.get_content()
    except (LookupError, ValueError):  # charset desconhecido ou corpo quebrado
        return ""
    if parte.get_content_type() == "text/html":
        texto = PADRAO_TAG_HTML.sub(" ", texto)
    return " ".join(texto.split())


def _data_hora(valor):
    try:
        momento = parsedate_to_datetime(valor) if valor else None
    except (TypeError, ValueError):
        return None
    if momento is None:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO_DA_CAIXA)
    return momento.astimezone(FUSO_DA_CAIXA).isoformat(timespec="minutes")


def _resumo_da_mensagem(bruto, com_corpo):
    mensagem = email.message_from_bytes(bruto, policy=policy.default)
    assunto = " ".join(str(mensagem.get("Subject", "")).split())[:TAMANHO_DO_ASSUNTO]
    remetente = parseaddr(str(mensagem.get("From", "")))[1].lower()
    trecho = _texto_do_corpo(mensagem)[:TAMANHO_DO_TRECHO] if com_corpo else TRECHO_DE_MENSAGEM_GRANDE
    return {"email": remetente, "assunto": assunto, "data_hora": _data_hora(mensagem.get("Date")), "trecho": trecho}


def _literal(resposta_do_fetch):
    """Os bytes do literal de um FETCH de uma mensagem só (o `imaplib` devolve [(b'1 (BODY[] {n}', b'...'), b')'])."""
    for item in resposta_do_fetch or ():
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], bytes):
            return item[1]
    raise RespostaInvalida("resposta fora do formato")


def _tamanho(resposta_do_fetch):
    for item in resposta_do_fetch or ():
        cabeca = item[0] if isinstance(item, tuple) else item
        achado = PADRAO_TAMANHO.search(cabeca) if isinstance(cabeca, bytes) else None
        if achado:
            return int(achado.group(1))
    raise RespostaInvalida("resposta fora do formato")


class ConectorEmailLeitura(Conector):
    nome = "email_leitura"
    rotulo = "E-mail (leitura, IMAP)"
    variavel_modo = "EMAIL_LEITURA_MODO"
    modo_padrao = "desligado"
    variavel_que_liga = "EMAIL_IMAP_HOST"
    variaveis = (
        "EMAIL_LEITURA_MODO",
        "EMAIL_IMAP_HOST",
        "EMAIL_IMAP_PORTA",
        "EMAIL_IMAP_SEGURANCA",
        "EMAIL_IMAP_USUARIO",
        "EMAIL_IMAP_SENHA",
        "EMAIL_IMAP_PASTA",
    )
    credencial = "plataforma"
    mensagem_desligada = "A leitura da caixa de e-mail não está ligada nesta plataforma."
    como_ligar = "preencha EMAIL_IMAP_HOST, EMAIL_IMAP_USUARIO e EMAIL_IMAP_SENHA (ou use EMAIL_LEITURA_MODO=simulado)"
    dica_sem_rede = "Confira a internet e o EMAIL_IMAP_HOST, ou use EMAIL_LEITURA_MODO=simulado."
    dicas = {
        "EMAIL_IMAP_HOST": "EMAIL_IMAP_HOST inválido: só o nome do servidor, como imap.gmail.com.",
        "EMAIL_IMAP_PORTA": "EMAIL_IMAP_PORTA inválida: um número de 1 a 65535, ou vazia (993 no ssl, 143 no starttls).",
        "EMAIL_IMAP_SEGURANCA": "EMAIL_IMAP_SEGURANCA inválida: use ssl ou starttls (nenhuma só em localhost).",
        "EMAIL_IMAP_USUARIO": "EMAIL_IMAP_USUARIO inválido: o e-mail da caixa, sem acento.",
        "EMAIL_IMAP_SENHA": "EMAIL_IMAP_SENHA inválida: sem acento; no Gmail, use uma senha de app.",
        "EMAIL_IMAP_PASTA": "EMAIL_IMAP_PASTA inválida: o nome da pasta, sem acento nem aspas (vazia usa INBOX).",
    }

    def configuracao(self, ambiente=os.environ):
        host = ambiente.get("EMAIL_IMAP_HOST", "").strip()
        if not host or HOST_RE.fullmatch(host) is None:
            raise ConfiguracaoInvalida("EMAIL_IMAP_HOST")
        seguranca = ambiente.get("EMAIL_IMAP_SEGURANCA", "").strip().lower() or "ssl"
        if seguranca not in SEGURANCAS or (seguranca == "nenhuma" and host.lower() not in HOSTS_LOCAIS):
            raise ConfiguracaoInvalida("EMAIL_IMAP_SEGURANCA")
        porta_texto = ambiente.get("EMAIL_IMAP_PORTA", "").strip()
        if porta_texto and not PORTA_RE.fullmatch(porta_texto):
            raise ConfiguracaoInvalida("EMAIL_IMAP_PORTA")
        porta = int(porta_texto) if porta_texto else PORTA_PADRAO[seguranca]
        if not 0 < porta < 65536:
            raise ConfiguracaoInvalida("EMAIL_IMAP_PORTA")
        usuario = ambiente.get("EMAIL_IMAP_USUARIO", "").strip()
        senha = ambiente.get("EMAIL_IMAP_SENHA", "")
        # O LOGIN do IMAP vai em ASCII: acento quebraria toda leitura.
        if not usuario or not usuario.isascii() or any(c.isspace() for c in usuario):
            raise ConfiguracaoInvalida("EMAIL_IMAP_USUARIO")
        if not senha or not senha.isascii():
            raise ConfiguracaoInvalida("EMAIL_IMAP_SENHA")
        pasta = ambiente.get("EMAIL_IMAP_PASTA", "").strip() or PASTA_PADRAO
        if not PADRAO_PASTA.fullmatch(pasta):
            raise ConfiguracaoInvalida("EMAIL_IMAP_PASTA")
        return ConfiguracaoImap(host, porta, seguranca, usuario, senha, pasta)

    def conferir_configuracao(self, ambiente=os.environ):
        self.configuracao(ambiente)

    def fora_do_ar(self):
        return falhas.fora_do_ar("email_leitura")

    def _ligado(self, ambiente):
        modo = self.exigir_ligado(ambiente)
        if self.fora_do_ar():
            raise ConnectionError("leitura de e-mail fora do ar (falha simulada)")
        return modo

    def agora_real(self):
        """O relógio de verdade (Brasília). A suíte de testes pode trocar este método."""
        return datetime.now(FUSO_DA_CAIXA)

    def hoje(self, ambiente=os.environ):
        """O "hoje" do período padrão: o real numa caixa de verdade; o do mock na caixa simulada."""
        if self.modo(ambiente) == "real":
            return self.agora_real().date()
        return dados_sinteticos.HOJE_DO_MOCK

    def _abrir(self, config):
        """Conecta, cifra e faz o login. Levanta `CredencialRecusada`, `ConnectionError` ou `TimeoutError`."""
        contexto = ssl.create_default_context()  # confere o certificado e o nome do servidor
        try:
            if config.seguranca == "ssl":
                caixa = imaplib.IMAP4_SSL(config.host, config.porta, ssl_context=contexto, timeout=TEMPO_LIMITE)
            else:
                caixa = imaplib.IMAP4(config.host, config.porta, timeout=TEMPO_LIMITE)
                if config.seguranca == "starttls":
                    caixa.starttls(ssl_context=contexto)  # sem STARTTLS no servidor: erro, e a senha não vai
        except TimeoutError:
            raise TimeoutError("leitura de e-mail indisponível") from None
        except (OSError, imaplib.IMAP4.error):
            raise ConnectionError("leitura de e-mail indisponível") from None
        try:
            caixa.login(config.usuario, config.senha)
        except imaplib.IMAP4.abort:
            self._fechar(caixa)
            raise ConnectionError("leitura de e-mail indisponível") from None
        except imaplib.IMAP4.error:
            self._fechar(caixa)
            raise CredencialRecusada("leitura de e-mail indisponível") from None
        except BaseException:
            self._fechar(caixa)
            raise
        return caixa

    def _fechar(self, caixa):
        with suppress(Exception):
            caixa.logout()

    def _examinar(self, caixa, config):
        """Abre a pasta só para leitura e devolve quantas mensagens ela tem."""
        situacao, dados = caixa.select(f'"{config.pasta}"', readonly=True)
        if situacao != "OK":
            raise ConfiguracaoInvalida("EMAIL_IMAP_PASTA")
        return int(dados[0]) if dados and dados[0] and dados[0].isdigit() else 0

    def _com_a_caixa(self, config, funcao):
        """Roda `funcao(caixa)` com a pasta aberta, traduzindo as falhas do `imaplib` sem detalhe."""
        caixa = self._abrir(config)
        try:
            self._examinar(caixa, config)
            return funcao(caixa)
        except imaplib.IMAP4.abort:
            raise ConnectionError("leitura de e-mail indisponível") from None
        except imaplib.IMAP4.error:
            raise RespostaInvalida("resposta fora do formato") from None
        except TimeoutError:
            raise TimeoutError("leitura de e-mail indisponível") from None
        finally:
            self._fechar(caixa)

    def _ler_caixa(self, caixa, enderecos, desde, ate, filtro, limite):
        criterios = [*criterio_de_remetentes(enderecos), "SINCE", data_do_imap(desde), "BEFORE", data_do_imap(ate + timedelta(days=1))]
        situacao, dados = caixa.search(None, *criterios)
        if situacao != "OK":
            raise RespostaInvalida("resposta fora do formato")
        ids = (dados[0] or b"").split() if dados else []
        recentes = list(reversed(ids[-CABECALHOS_LIDOS_NO_MAXIMO:]))
        escolhidos = []
        for id_mensagem in recentes:
            cabecalho = _resumo_da_mensagem(_literal(caixa.fetch(id_mensagem, "(BODY.PEEK[HEADER])")[1]), False)
            if filtro(cabecalho["assunto"]):
                escolhidos.append(id_mensagem)
        mensagens = []
        for id_mensagem in escolhidos[:limite]:
            tamanho = _tamanho(caixa.fetch(id_mensagem, "(RFC822.SIZE)")[1])
            if tamanho <= TAMANHO_MAXIMO_DA_MENSAGEM:
                bruto = _literal(caixa.fetch(id_mensagem, "(BODY.PEEK[])")[1])
                mensagens.append(_resumo_da_mensagem(bruto, True))
            else:
                bruto = _literal(caixa.fetch(id_mensagem, "(BODY.PEEK[HEADER])")[1])
                mensagens.append(_resumo_da_mensagem(bruto, False))
        return mensagens, len(escolhidos)

    def _caixa_simulada(self, codigo, desde, ate, filtro, limite):
        contatos, _ = dados_sinteticos.buscar_contatos(codigo)
        remetente = next((c["email"] for c in contatos if c.get("email")), None)
        chamados, _ = dados_sinteticos.buscar_chamados(codigo, CABECALHOS_LIDOS_NO_MAXIMO)
        mensagens = []
        for chamado in chamados:
            interacoes, _ = dados_sinteticos.buscar_interacoes(codigo, chamado["codigo"], CABECALHOS_LIDOS_NO_MAXIMO)
            for interacao in interacoes:
                if interacao["canal"] != CANAL_EMAIL or interacao["autor"] != AUTOR_LOJISTA:
                    continue
                momento = datetime.fromisoformat(interacao["data_hora"]).replace(tzinfo=FUSO_DA_CAIXA)
                # O código do chamado, não o protocolo: a máscara de texto livre leria o protocolo como cartão.
                assunto = f"Chamado {chamado['codigo']}: {chamado['categoria']}"
                if desde <= momento.date() <= ate and filtro(assunto):
                    mensagens.append(
                        {
                            "email": remetente,
                            "assunto": assunto,
                            "data_hora": momento.isoformat(timespec="minutes"),
                            "trecho": " ".join(interacao["texto"].split())[:TAMANHO_DO_TRECHO],
                        }
                    )
        mensagens.sort(key=lambda m: m["data_hora"], reverse=True)
        return mensagens[:limite], len(mensagens)

    def mensagens(self, codigo, enderecos, desde, ate, assunto_contem, limite, ambiente=os.environ):
        """As mensagens mais recentes dos `enderecos` (os contatos do lojista `codigo`) no período, da mais nova
        para a mais antiga: ([{email, assunto, data_hora, trecho}], quantas acharam) e a `fonte`."""
        modo = self._ligado(ambiente)
        termo = (assunto_contem or "").casefold()

        def filtro(assunto):
            return termo in assunto.casefold()

        if modo == "simulado":
            achadas, total = self._caixa_simulada(codigo, desde, ate, filtro, limite)
            return achadas, total, FONTE_SIMULADA
        validos = [e.lower() for e in enderecos if endereco_valido(e) and e.isascii()]
        if not validos:
            return [], 0, FONTE_REAL
        config = self.configuracao(ambiente)
        achadas, total = self.chamar(
            "buscar", lambda: self._com_a_caixa(config, lambda c: self._ler_caixa(c, validos, desde, ate, filtro, limite))
        )
        return achadas, total, FONTE_REAL

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        config = self.configuracao(ambiente)

        def contar():
            caixa = self._abrir(config)
            try:
                return self._examinar(caixa, config)
            finally:
                self._fechar(caixa)

        quantas = self.chamar("testar", contar)
        return f"A caixa aceitou o login e a pasta {config.pasta} tem {quantas} mensagens. Nenhuma foi lida."


CONECTOR = registrar(ConectorEmailLeitura())
