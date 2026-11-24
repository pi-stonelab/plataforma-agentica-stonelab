"""Base dos conectores de escritório (Google Workspace e Microsoft 365): agenda, planilhas, documentos e arquivos
da conta de CADA pessoa, com OAuth2 (ver `oauth.py` e `credenciais.py`).

As duas integrações respondem as mesmas operações, no mesmo formato, e as ferramentas de `documentos_e_agenda/`
não sabem de qual vêm. Cada operação recebe o `id_usuario` e usa só a conta dele:

- `eventos(id_usuario, data_inicio, data_fim, limite)` -> (lista, truncado). Evento: titulo, inicio, fim ("AAAA-MM-DD"
  de dia inteiro ou "AAAA-MM-DDTHH:MM", horário de Brasília), dia_inteiro, local, convidados (quantos).
- `criar_evento(id_usuario, evento)` -> titulo, inicio, fim. `evento` traz titulo, inicio e fim (datetime sem fuso, de
  Brasília), local, descricao, convidados (e-mails já conferidos) e id_unico (para não duplicar se o pedido repetir).
- `arquivos(id_usuario, consulta, tipo, limite)` -> lista de id_arquivo, titulo, tipo (planilha, documento, pasta,
  outro) e modificado_em.
- `descrever_planilha(id_usuario, id_arquivo)` -> titulo e abas (cada uma com o titulo).
- `ler_planilha(id_usuario, id_arquivo, aba, intervalo, limite)` -> titulo, aba, intervalo, linhas (listas de texto)
  e truncado.
- `adicionar_linha(id_usuario, id_arquivo, aba, valores)` -> linhas_adicionadas.
- `criar_planilha(id_usuario, titulo, linhas)` -> id_arquivo, titulo, link.
- `documento(id_usuario, id_arquivo, limite)` -> titulo, texto (até `limite` caracteres) e truncado.

Modos (`<SERVICO>_MODO`): `real` fala com a API da pessoa; `simulado` responde do `escritorio_simulado` (sem rede e
sem conta); `desligado`. No modo real, sem conta ligada ou sem a permissão pedida a ferramenta responde
`integracao_indisponivel` ("conta não ligada") e a pessoa liga a conta na tela de integrações.

O que não muda de uma API para a outra, e vive aqui: o pedido com o token da pessoa (e, num 401, uma única renovação
e repetição), a tradução das recusas (limite de pedidos, falta de permissão, sem acesso ao item, conta desligada), o
domínio permitido para convidados e o `testar`.
"""

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import cliente_http, credenciais
from ferramentas.integracoes.cliente_http import PedidoRecusado, pedir
from ferramentas.integracoes.conector import (
    Conector,
    CredencialRecusada,
    DestinoNaoPermitido,
    LimiteDePedidos,
    ler_lista,
)
from ferramentas.integracoes.escritorio_simulado import MundoSimulado
from ferramentas.integracoes.formatos import PADRAO_NUMERO
from ferramentas.integracoes.oauth import FluxoOAuth

FUSO = ZoneInfo("America/Sao_Paulo")
PADRAO_ID_ARQUIVO = re.compile(r"[A-Za-z0-9!_-]{5,128}")
PADRAO_DOMINIO = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?){1,4}")
PADRAO_INTERVALO = re.compile(r"([A-Za-z]{1,3})([1-9][0-9]{0,5}):([A-Za-z]{1,3})([1-9][0-9]{0,5})")
TIPOS_DE_ARQUIVO = ("planilha", "documento", "qualquer")
DOMINIOS_SIMULADOS = ("stonesim.example",)  # o domínio do diretório do mock (DOC-MOCK §3.3)
MENSAGEM_SEM_ACESSO = "A conta {rotulo} desta pessoa não tem acesso a este item."
MENSAGEM_NAO_ENCONTRADO = "Arquivo não encontrado, ou a sua conta não tem acesso a ele."


def limitar_intervalo(intervalo, limite):
    """"A1:F500" com `limite` linhas -> "A1:F{primeira + limite}" (uma linha a mais que o limite, para saber se truncou)."""
    achado = PADRAO_INTERVALO.fullmatch(intervalo)
    coluna_a, linha_a, coluna_b, linha_b = achado.groups()
    return f"{coluna_a.upper()}{linha_a}:{coluna_b.upper()}{min(int(linha_b), int(linha_a) + limite)}"


def valor_da_celula(texto):
    """O que vai à API ao gravar uma célula: número com cara de número (para somar na planilha) ou o texto como está."""
    if PADRAO_NUMERO.fullmatch(texto):
        numero = float(texto)
        return int(numero) if "." not in texto else numero
    return texto


def texto_da_celula(valor):
    """O valor de uma célula como texto (a API devolve número, texto ou vazio)."""
    return "" if valor is None else str(valor)


class ConectorDeEscritorio(Conector):
    tipo = "externo"
    credencial = "pessoa"
    modo_padrao = "desligado"
    servicos = ("autorizacao", "agenda", "planilhas", "documentos", "arquivos")
    escopos_de_leitura = frozenset()  # a subclasse diz (o mínimo para ler)
    escopos_de_escrita = frozenset()  # a subclasse diz (só para as ferramentas de escrita)
    mais_amplos = {}  # escopo -> escopos que o incluem (a subclasse diz)
    fonte_real = ""
    fonte_simulada = ""

    def __init__(self):
        super().__init__()
        self.mundo = MundoSimulado()

    # --- o que a subclasse escreve ------------------------------------------------------------------------------

    def configuracao_oauth(self, ambiente):
        """A `oauth.ConfiguracaoOAuth` montada do .env. Variável errada: `ConfiguracaoInvalida(VARIAVEL)`."""
        raise NotImplementedError

    def classificar_recusa(self, recusa):
        """Para um 401 ou 403 do serviço: `limite`, `escopo`, `acesso`, `conta` ou `plataforma`."""
        raise NotImplementedError

    # --- relógio, fonte e domínios ------------------------------------------------------------------------------

    def agora_real(self):
        """O relógio de verdade (Brasília). A suíte de testes pode trocar este método."""
        return datetime.now(FUSO)

    def hoje(self, ambiente=os.environ):
        """O "hoje" das datas padrão: o real numa conta de verdade; o do mock no escritório simulado."""
        if self.modo(ambiente) == "real":
            return self.agora_real().date()
        return dados_sinteticos.HOJE_DO_MOCK

    def fonte(self, ambiente=os.environ):
        return self.fonte_simulada if self.demonstracao(ambiente) else self.fonte_real

    def dominios_permitidos(self, ambiente=os.environ):
        """Domínios dos e-mails que podem receber convite. Do .env (`ESCRITORIO_DOMINIOS`); no simulado, o do mock."""
        dominios = ler_lista(ambiente, "ESCRITORIO_DOMINIOS", PADRAO_DOMINIO)
        if not dominios and self.modo(ambiente) == "simulado":
            return list(DOMINIOS_SIMULADOS)
        return dominios

    def exigir_convidado(self, endereco, ambiente=os.environ):
        """O e-mail em minúsculas se o domínio dele está na lista permitida; senão `DestinoNaoPermitido`."""
        endereco = endereco.strip().lower()
        _, arroba, dominio = endereco.rpartition("@")
        if not arroba:
            raise DestinoNaoPermitido("destino fora da lista permitida")
        self.exigir_destino(dominio, self.dominios_permitidos(ambiente))
        return endereco

    # --- conta de cada pessoa ------------------------------------------------------------------------------------

    def fluxo(self, ambiente=os.environ):
        """O `FluxoOAuth` do serviço agora (autorizar, concluir, renovar, desligar). É o que o back-end usa nas rotas."""
        return FluxoOAuth(
            self.configuracao_oauth(ambiente), lambda etapa, funcao: self.chamar(etapa, funcao, servico="autorizacao")
        )

    def autorizar(self, id_usuario, com_escrita=False, ambiente=os.environ):
        """O endereço para onde a pessoa vai ligar a conta. Só leitura, a não ser que `com_escrita`."""
        escopos = self.escopos_de_leitura | (self.escopos_de_escrita if com_escrita else frozenset())
        return self.fluxo(ambiente).iniciar(id_usuario, escopos)

    def conta_ligada(self, id_usuario, ambiente=os.environ):
        """True se a pessoa pode usar este serviço agora: no simulado sempre; no real, se ligou a conta."""
        if self.modo(ambiente) == "simulado":
            return True
        return credenciais.provedor().ligada(id_usuario, self.nome)

    def _pedir_da_pessoa(self, ambiente, id_usuario, servico, escopos, metodo, url, **pedido):
        """O pedido com o token da pessoa. 401: renova uma vez e repete. Recusa: traduzida para o que a pessoa entende."""
        fluxo = self.fluxo(ambiente)
        provedor = fluxo.provedor
        cabecalhos = pedido.pop("cabecalhos", None) or {}

        def com_token(token):
            return pedir(metodo, url, cabecalhos={**cabecalhos, "Authorization": f"Bearer {token}"}, **pedido)

        def chamada():
            token = provedor.token_de_acesso(id_usuario, fluxo, escopos)
            try:
                return com_token(token)
            except CredencialRecusada as recusa:
                if recusa.status != 401:
                    raise self._traduzir(recusa, fluxo, escopos) from None
            token = provedor.token_de_acesso(id_usuario, fluxo, escopos, recusado=token)
            try:
                return com_token(token)
            except CredencialRecusada as recusa:
                raise self._traduzir(recusa, fluxo, escopos) from None

        return self.chamar(metodo.lower(), chamada, servico=servico)

    def _traduzir(self, recusa, fluxo, escopos):
        tipo = self.classificar_recusa(recusa)
        if tipo == "limite":
            return LimiteDePedidos(cliente_http.MENSAGEM)
        if tipo == "escopo":
            return credenciais.PermissaoInsuficiente(fluxo.rotulo, fluxo.tipo_de_acesso(escopos))
        if tipo == "conta":
            return credenciais.ContaNaoLigada(fluxo.rotulo)
        if tipo == "acesso":
            return ErroFerramenta("permissao_negada", MENSAGEM_SEM_ACESSO.format(rotulo=fluxo.rotulo))
        return recusa  # `plataforma`: o app do .env foi recusado (API desligada no projeto, por exemplo)

    # --- as operações (o simulado ou a API de verdade) -----------------------------------------------------------

    def _operacao(self, nome, ambiente, id_usuario, *argumentos):
        if self._ligado(ambiente) == "simulado":
            return getattr(self.mundo, nome)(id_usuario, *argumentos)
        return getattr(self, f"{nome}_real")(ambiente, id_usuario, *argumentos)

    def eventos(self, id_usuario, data_inicio, data_fim, limite, ambiente=os.environ):
        return self._operacao("eventos", ambiente, id_usuario, data_inicio, data_fim, limite)

    def criar_evento(self, id_usuario, evento, ambiente=os.environ):
        for convidado in evento.get("convidados", ()):  # confere de novo na hora de criar: a lista do .env pode ter mudado
            self.exigir_convidado(convidado, ambiente)
        return self._operacao("criar_evento", ambiente, id_usuario, evento)

    def arquivos(self, id_usuario, consulta, tipo, limite, ambiente=os.environ):
        return self._operacao("arquivos", ambiente, id_usuario, consulta, tipo, limite)

    def descrever_planilha(self, id_usuario, id_arquivo, ambiente=os.environ):
        return self._operacao("descrever_planilha", ambiente, id_usuario, id_arquivo)

    def ler_planilha(self, id_usuario, id_arquivo, aba, intervalo, limite, ambiente=os.environ):
        return self._operacao("ler_planilha", ambiente, id_usuario, id_arquivo, aba, intervalo, limite)

    def adicionar_linha(self, id_usuario, id_arquivo, aba, valores, ambiente=os.environ):
        return self._operacao("adicionar_linha", ambiente, id_usuario, id_arquivo, aba, valores)

    def criar_planilha(self, id_usuario, titulo, linhas, ambiente=os.environ):
        return self._operacao("criar_planilha", ambiente, id_usuario, titulo, linhas)

    def documento(self, id_usuario, id_arquivo, limite, ambiente=os.environ):
        return self._operacao("documento", ambiente, id_usuario, id_arquivo, limite)

    # --- teste de quem configura ---------------------------------------------------------------------------------

    def testar(self, ambiente=os.environ):
        """Confere o app OAuth do .env sem nenhuma conta de pessoa: manda um código inventado ao endereço de token.

        `invalid_grant` quer dizer que o serviço aceitou o `client_id` e o segredo e só recusou o código; `invalid_client`
        e `unauthorized_client`, que o app está errado. Quem mexe em conta é cada pessoa, na tela de integrações."""
        if self._ligado(ambiente) == "simulado":
            return "Modo simulado: agenda, planilhas e documentos de demonstração, sem conta e sem rede."
        configuracao = self.configuracao_oauth(ambiente)
        formulario = {
            "grant_type": "authorization_code",
            "code": "codigo-de-teste-da-plataforma",
            "redirect_uri": configuracao.redirect_uri,
            "code_verifier": "teste-da-plataforma-" + "x" * 30,
            "client_id": configuracao.client_id,
            **({"client_secret": configuracao.client_secret} if configuracao.client_secret else {}),
        }
        try:
            self.chamar(
                "testar", lambda: pedir("POST", configuracao.url_do_token, formulario=formulario), servico="autorizacao"
            )
        except PedidoRecusado as recusa:
            codigo = recusa.dados.get("error") if isinstance(recusa.dados, dict) else None
            if codigo in ("invalid_client", "unauthorized_client"):
                raise CredencialRecusada(cliente_http.MENSAGEM) from None
            if codigo != "invalid_grant":
                return f"O serviço respondeu, mas recusou o teste ({str(codigo)[:40]}). Confira o endereço de retorno."
        return (
            "O serviço aceitou o app (client_id e segredo conferem). Nenhuma conta foi ligada: cada pessoa conecta a "
            "própria na tela de integrações."
        )

    def reiniciar(self):
        super().reiniciar()
        self.mundo.limpar()



def horario_local(texto, fuso_do_texto=FUSO):
    """Data e hora de uma API ("2026-10-16T14:00:00-03:00", ou sem fuso, que vale `fuso_do_texto`) como horário de
    Brasília ("2026-10-16T14:00"). Formato estranho: `ValueError`."""
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=fuso_do_texto)
    return momento.astimezone(FUSO).replace(tzinfo=None).isoformat(timespec="minutes")
