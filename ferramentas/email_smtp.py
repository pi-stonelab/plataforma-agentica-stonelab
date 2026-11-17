"""Envio de e-mail por SMTP (`smtplib`): o envio do `enviar_email`.

A configuração vem só do ambiente (.env) e é lida na hora de cada uso. Sem `EMAIL_SMTP_HOST`, o envio está
desligado: o `enviar_email` responde que o envio não está configurado e não monta prévia.

Segurança:
- Fora do localhost a conexão é sempre cifrada (STARTTLS ou SSL) e o certificado é conferido. Servidor que
  não oferece STARTTLS não recebe nada: não há volta para texto puro, e a senha nunca vai sem TLS.
- O remetente é fixo (`EMAIL_REMETENTE`). O destinatário vem do cadastro, ou de `EMAIL_DESTINO_TESTE`, e é
  sempre um endereço só. O funcionário que confirmou aparece no nome ("Ana via Stone") e no "responder para"
  (Reply-To): o lojista responde a ele, e o envio continua pela conta da plataforma.
- Erros e logs levam só a etapa e o tipo da falha: nada de host, usuário, senha, endereço ou texto.
- Falha antes de a mensagem seguir vira `EnvioIndisponivel` (nada foi enviado). Falha depois de o texto ir ao
  servidor, sem resposta dele, vira `EfeitoIncerto`: o e-mail pode ter saído.

Teste manual com um endereço seu (com `MODO_TERMINAL=1`):
    python -m ferramentas.email_smtp --testar <seu endereço>
"""

import argparse
import logging
import os
import re
import secrets
import smtplib
import ssl
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, formataddr

from mock import falhas

from ferramentas import mascara
from ferramentas.base import EfeitoIncerto, ErroFerramenta

logger = logging.getLogger(__name__)

SEGURANCAS = ("starttls", "ssl", "nenhuma")
PORTA_PADRAO = {"starttls": 587, "ssl": 465, "nenhuma": 1025}
HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")  # só neles vale `nenhuma` (ex.: o Mailpit)
TEMPO_LIMITE = 15  # segundos por operação de rede
RECUSAS = (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError)

ENDERECO_RE = re.compile(r"[^@\s,;<>()\"']+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
HOST_RE = re.compile(r"[A-Za-z0-9.-]+|[0-9A-Fa-f:]+")
NOME_EXIBIDO = "Stone"
PREFIXO_TESTE = "[TESTE] "
AVISO_TESTE = "Mensagem de teste. Destinatário original no cadastro: "
ASSUNTO_DO_TESTE_MANUAL = "Teste de envio da Plataforma Agêntica"
CORPO_DO_TESTE_MANUAL = "Se este e-mail chegou, o envio por SMTP da plataforma está funcionando."


class ConfiguracaoInvalida(ConnectionError):
    """Uma variável `EMAIL_*` está errada. A mensagem diz qual, nunca o valor."""


class EnvioIndisponivel(ConnectionError):
    """O envio falhou antes de a mensagem seguir: nada foi enviado. Guarda a etapa e o tipo da falha."""

    def __init__(self, etapa, tipo):
        super().__init__(f"envio por SMTP indisponível na etapa {etapa}")
        self.etapa = etapa
        self.tipo = tipo


@dataclass(frozen=True)
class ConfiguracaoSmtp:
    host: str
    porta: int
    seguranca: str
    remetente: str
    usuario: str = ""
    senha: str = field(default="", repr=False)  # fora do repr: um log da configuração não leva a senha
    destino_teste: str = ""


def endereco_valido(texto):
    return isinstance(texto, str) and ENDERECO_RE.fullmatch(texto) is not None


MENSAGEM_DESLIGADO = "Envio de e-mail não configurado. Defina EMAIL_SMTP_HOST no .env."


def descricao_do_envio(ambiente=os.environ):
    """Por onde o e-mail saiu, para o terminal mostrar a quem confirmou."""
    if ambiente.get("EMAIL_DESTINO_TESTE", "").strip():
        return "enviado por SMTP ao destino de teste"
    return "enviado por SMTP"


def _invalida(variavel):
    logger.warning("configuracao de e-mail invalida: variavel=%s", variavel)
    return ConfiguracaoInvalida(f"{variavel} inválida no .env.")


def configuracao(ambiente=os.environ):
    """A configuração do SMTP lida do ambiente, ou None se o envio por SMTP está desligado."""
    host = ambiente.get("EMAIL_SMTP_HOST", "").strip()
    if not host:
        return None
    if HOST_RE.fullmatch(host) is None:
        raise _invalida("EMAIL_SMTP_HOST")
    seguranca = ambiente.get("EMAIL_SMTP_SEGURANCA", "").strip().lower() or "starttls"
    if seguranca not in SEGURANCAS or (seguranca == "nenhuma" and host.lower() not in HOSTS_LOCAIS):
        raise _invalida("EMAIL_SMTP_SEGURANCA")
    porta_texto = ambiente.get("EMAIL_SMTP_PORTA", "").strip()
    porta = int(porta_texto) if porta_texto.isdigit() else PORTA_PADRAO[seguranca] if not porta_texto else 0
    if not 0 < porta < 65536:
        raise _invalida("EMAIL_SMTP_PORTA")
    remetente = ambiente.get("EMAIL_REMETENTE", "").strip()
    if not endereco_valido(remetente):
        raise _invalida("EMAIL_REMETENTE")
    usuario = ambiente.get("EMAIL_SMTP_USUARIO", "").strip()
    senha = ambiente.get("EMAIL_SMTP_SENHA", "")
    if bool(usuario) != bool(senha):
        raise _invalida("EMAIL_SMTP_USUARIO e EMAIL_SMTP_SENHA")
    destino_teste = ambiente.get("EMAIL_DESTINO_TESTE", "").strip()
    if destino_teste and not endereco_valido(destino_teste):
        raise _invalida("EMAIL_DESTINO_TESTE")
    return ConfiguracaoSmtp(host, porta, seguranca, remetente, usuario, senha, destino_teste)


def exigir_configuracao(ambiente=os.environ):
    """A configuração do SMTP; sem `EMAIL_SMTP_HOST`, `ErroFerramenta` de integração indisponível."""
    config = configuracao(ambiente)
    if config is None:
        raise ErroFerramenta("integracao_indisponivel", MENSAGEM_DESLIGADO)
    return config


def enviar(para, assunto, corpo, config, funcionario=None):
    """Envia um e-mail de texto puro e devolve o id dele (como `MSG-3F9A2C71B0D4`).

    `para` é o endereço do cadastro. Com `config.destino_teste`, a mensagem vai para ele, com o aviso
    de teste. `funcionario` ({"nome", "email"}, de quem confirmou) vira o nome exibido e o Reply-To; sem ele,
    ou com e-mail inválido, a mensagem sai só com o remetente da plataforma.
    Levanta `EnvioIndisponivel` (nada saiu) ou `EfeitoIncerto` (pode ter saído)."""
    falhas.verificar("email")
    if not endereco_valido(para):
        raise ErroFerramenta("nao_encontrado", "O contato do lojista não tem um e-mail válido.")
    id_mensagem = f"MSG-{secrets.token_hex(6).upper()}"
    mensagem = _montar_mensagem(config, para, assunto, corpo, id_mensagem, funcionario or {})
    servidor = _abrir(config)
    try:
        _entregar(servidor, mensagem)
    finally:
        _fechar(servidor)
    return id_mensagem


def _de(config, funcionario):
    """O From: o remetente da plataforma, com o primeiro nome de quem confirmou ("Ana via Stone")."""
    nomes = str(funcionario.get("nome") or "").split()  # split também tira quebras de linha
    exibido = f"{nomes[0]} via {NOME_EXIBIDO}" if nomes else NOME_EXIBIDO
    return formataddr((exibido, config.remetente))


def _montar_mensagem(config, para, assunto, corpo, id_mensagem, funcionario):
    if config.destino_teste:
        para_de_fato = config.destino_teste
        assunto = PREFIXO_TESTE + assunto
        corpo = f"{corpo}\n\n--\n{AVISO_TESTE}{mascara.mascarar_valor('email', para)}"
    else:
        para_de_fato = para
    dominio = config.remetente.rpartition("@")[2]
    mensagem = EmailMessage()
    try:  # o EmailMessage recusa quebra de linha em cabeçalho (injeção de cabeçalho)
        mensagem["From"] = _de(config, funcionario)
        mensagem["To"] = para_de_fato
        mensagem["Subject"] = assunto
        if endereco_valido(funcionario.get("email")):
            mensagem["Reply-To"] = funcionario["email"]
    except ValueError:
        raise ErroFerramenta("parametro_invalido", "Assunto ou destinatário inválido.") from None
    mensagem["Date"] = format_datetime(datetime.now(UTC))
    mensagem["Message-ID"] = f"<{id_mensagem.lower()}@{dominio}>"
    mensagem.set_content(corpo)
    return mensagem


def _abrir(config):
    """Conecta, cifra e faz o login. Qualquer falha aqui: nada foi enviado."""
    contexto = ssl.create_default_context()  # confere o certificado e o nome do servidor
    try:
        if config.seguranca == "ssl":
            servidor = smtplib.SMTP_SSL(config.host, config.porta, timeout=TEMPO_LIMITE, context=contexto)
        else:
            servidor = smtplib.SMTP(config.host, config.porta, timeout=TEMPO_LIMITE)
        try:
            if config.seguranca == "starttls":
                servidor.starttls(context=contexto)  # sem STARTTLS no servidor: erro, e nada mais segue
            if config.usuario:
                servidor.login(config.usuario, config.senha)
        except BaseException:
            _fechar(servidor)
            raise
    except (OSError, smtplib.SMTPException) as erro:
        raise _indisponivel("conexao", erro) from None
    return servidor


def _entregar(servidor, mensagem):
    """Manda a mensagem. Recusa do servidor: nada saiu. Queda sem resposta: pode ter saído."""
    try:
        servidor.send_message(mensagem)
    except RECUSAS as erro:
        raise _indisponivel("recusa", erro) from None
    except (OSError, smtplib.SMTPException) as erro:
        logger.warning("envio por smtp incerto: tipo=%s", type(erro).__name__)
        raise EfeitoIncerto() from None


def _fechar(servidor):
    with suppress(OSError, smtplib.SMTPException):
        servidor.quit()
    with suppress(OSError):
        servidor.close()


def _indisponivel(etapa, erro):
    tipo = type(erro).__name__
    logger.warning("envio por smtp falhou: etapa=%s tipo=%s", etapa, tipo)
    return EnvioIndisponivel(etapa, tipo)


def principal(argumentos=None, ambiente=os.environ, escrever=print):
    """`python -m ferramentas.email_smtp --testar <endereço>`: um e-mail de teste, sem agente nem dado."""
    analisador = argparse.ArgumentParser(description="Teste do envio de e-mail por SMTP.")
    analisador.add_argument("--testar", metavar="ENDERECO", required=True, help="para onde mandar o teste")
    destino = analisador.parse_args(argumentos).testar.strip()
    if ambiente.get("MODO_TERMINAL") != "1":  # O12: ferramenta de desenvolvimento, só local
        raise SystemExit("Modo terminal desligado. Defina MODO_TERMINAL=1 para usar.")
    if not endereco_valido(destino):
        raise SystemExit("Endereço de teste inválido.")
    try:
        config = exigir_configuracao(ambiente)
        id_mensagem = enviar(destino, ASSUNTO_DO_TESTE_MANUAL, CORPO_DO_TESTE_MANUAL, replace(config, destino_teste=""))
    except ConfiguracaoInvalida as erro:
        raise SystemExit(str(erro)) from None
    except ErroFerramenta as erro:
        raise SystemExit(erro.mensagem) from None
    except EnvioIndisponivel as erro:
        raise SystemExit(f"Não enviou: falha na etapa {erro.etapa} ({erro.tipo}).") from None
    except EfeitoIncerto:
        raise SystemExit("O servidor não confirmou: o e-mail pode ter saído. Confira a caixa de entrada.") from None
    except ConnectionError:
        raise SystemExit("Envio desligado pelo mock (MOCK_FALHAS tem email).") from None
    escrever(f"Enviado ({id_mensagem}). Confira a caixa de entrada e o spam.")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    principal()
