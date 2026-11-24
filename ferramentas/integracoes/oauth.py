"""OAuth2 por pessoa (fluxo do código de autorização com PKCE), o mesmo para Google e Microsoft.

O que existe aqui (e é testado contra um servidor falso local):
1. `iniciar(id_usuario, escopos)`: monta o endereço da tela de consentimento, com `state` (aleatório, de uso
   único, preso à pessoa e válido por 10 minutos) e PKCE (`code_challenge` S256; o `code_verifier` fica só aqui).
2. `concluir(id_usuario, estado, codigo)`: confere o `state`, troca o código por tokens e guarda a credencial no
   `ProvedorDeCredencial`. Erro do serviço (código vencido ou já usado) vira `AutorizacaoRecusada`.
3. `renovar(credencial)`: troca o token de renovação por um novo token de acesso. Autorização revogada vira
   `ConcessaoRevogada`, e o provedor apaga a conta.
4. `desligar(id_usuario)`: esquece a conta e, onde o serviço tem endereço de revogação (Google), revoga o token.

Pedir só o escopo mínimo: leitura por padrão (`escopos_de_leitura` do conector) e os de escrita só quando a pessoa
usa uma ferramenta de escrita (autorização incremental: o `include_granted_scopes` do Google soma o que já havia).

Nada daqui é rota HTTP: quem recebe a pessoa de volta do Google ou da Microsoft é o back-end.
[A FAZER (Marcelo e Isabel, back-end, Sprint 3): as rotas GET /integracoes/{servico}/autorizar (chama `iniciar` com
o usuário do token do login e redireciona para a URL devolvida) e GET /integracoes/{servico}/callback (chama `concluir`
com o mesmo usuário; se o serviço mandou `error`, chama `cancelar`). Os estados pendentes ficam em memória neste
processo: com mais de um processo, guardar `PEDIDOS_PENDENTES` numa tabela com validade de 10 minutos]
[A FAZER (Larissa, interface, Sprint 3): o botão "Conectar conta" (e "Desconectar") na tela de conectores, para
`GET /integracoes` (`registro.estado_integracoes`, campo `credencial` = pessoa) e as rotas acima]
"""

import base64
import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlencode

from ferramentas.integracoes import credenciais
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida, pedir

VALIDADE_DO_ESTADO = timedelta(minutes=10)
LIMITE_POR_PESSOA = 3
LIMITE_GERAL = 1000
SEGUNDOS_DO_TOKEN_NO_MAXIMO = 24 * 3600
ERROS_DE_AUTORIZACAO_ACABADA = frozenset({"invalid_grant", "interaction_required", "consent_required", "login_required"})
MENSAGEM_ESTADO_INVALIDO = "O pedido de autorização não vale mais (expirou, já foi usado ou é de outra pessoa)."
MENSAGEM_CODIGO_RECUSADO = "O serviço não aceitou o código de autorização (expirou ou já foi usado). Comece de novo."
MENSAGEM_RESPOSTA_INVALIDA = "O serviço respondeu a autorização num formato inesperado."


class AutorizacaoRecusada(Exception):
    """A autorização não pôde ser concluída. A mensagem é para a pessoa e nunca traz código, token nem segredo."""


@dataclass(frozen=True)
class ConfiguracaoOAuth:
    """O que o fluxo precisa saber do serviço. Montada pelo conector a partir do .env, a cada uso."""

    nome: str
    rotulo: str
    url_de_autorizacao: str
    url_do_token: str
    client_id: str
    redirect_uri: str
    client_secret: str = field(default="", repr=False)
    url_de_revogacao: str = ""
    parametros_da_autorizacao: dict = field(default_factory=dict)
    escopos_sempre: tuple = ()  # Microsoft: `offline_access`, sem o qual não há token de renovação
    mais_amplos: dict = field(default_factory=dict)  # escopo -> escopos que o incluem
    escopos_de_escrita: frozenset = frozenset()


@dataclass
class PedidoPendente:
    id_usuario: str
    nome: str
    escopos: frozenset
    code_verifier: str = field(repr=False)
    expira_em: datetime


class PedidosPendentes:
    """Os `state` já entregues e ainda não usados. Uso único, preso à pessoa e ao serviço, com validade curta."""

    def __init__(self):
        self._trava = threading.Lock()
        self._pedidos = {}

    def _recolher_vencidos(self):
        agora = credenciais.agora()
        for estado in [e for e, p in self._pedidos.items() if p.expira_em <= agora]:
            del self._pedidos[estado]

    def guardar(self, pedido):
        with self._trava:
            self._recolher_vencidos()
            da_pessoa = [e for e, p in self._pedidos.items() if p.id_usuario == pedido.id_usuario]
            if len(da_pessoa) >= LIMITE_POR_PESSOA:  # a mais antiga cai: quem abriu e desistiu não trava a conta
                del self._pedidos[da_pessoa[0]]
            if len(self._pedidos) >= LIMITE_GERAL:
                del self._pedidos[next(iter(self._pedidos))]
            estado = secrets.token_urlsafe(32)
            self._pedidos[estado] = pedido
            return estado

    def retirar(self, estado, id_usuario, nome):
        """O pedido do `estado`, só se ele é desta pessoa e deste serviço. Uso único: sai da lista de qualquer jeito."""
        with self._trava:
            self._recolher_vencidos()
            pedido = self._pedidos.pop(estado, None) if isinstance(estado, str) else None
        if pedido is None or pedido.id_usuario != id_usuario or pedido.nome != nome:
            return None
        return pedido

    def limpar(self):
        with self._trava:
            self._pedidos.clear()


PEDIDOS_PENDENTES = PedidosPendentes()


def _desafio_pkce(verificador):
    resumo = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")


def escopos_de(texto):
    """Os escopos de um campo `scope` (separados por espaço) como conjunto; ausente ou estranho: vazio."""
    return frozenset(texto.split()) if isinstance(texto, str) else frozenset()


def _erro_do_servico(erro):
    """O código de erro OAuth (`invalid_grant`...) de uma recusa 4xx do endereço de token, ou None."""
    dados = erro.dados if isinstance(erro.dados, dict) else {}
    codigo = dados.get("error")
    return codigo if isinstance(codigo, str) else None


class FluxoOAuth:
    """O fluxo OAuth de um serviço, com a configuração do momento. `chamar(etapa, funcao)` é o disjuntor do conector."""

    def __init__(self, configuracao, chamar, provedor=None):
        self.configuracao = configuracao
        self._chamar = chamar
        self._provedor = provedor

    @property
    def nome(self):
        return self.configuracao.nome

    @property
    def rotulo(self):
        return self.configuracao.rotulo

    @property
    def mais_amplos(self):
        return self.configuracao.mais_amplos

    @property
    def provedor(self):
        return self._provedor or credenciais.provedor()

    def tipo_de_acesso(self, escopos):
        """"escrita" se algum dos escopos permite alterar algo; senão "leitura" (para a mensagem à pessoa)."""
        return "escrita" if set(escopos) & self.configuracao.escopos_de_escrita else "leitura"

    def iniciar(self, id_usuario, escopos):
        """O endereço da tela de consentimento para `id_usuario` pedir `escopos`. Redirecione a pessoa para ele."""
        escopos = frozenset(escopos)
        if not escopos or not isinstance(id_usuario, str) or not id_usuario.strip():
            raise ValueError("pessoa e escopos são obrigatórios")
        verificador = secrets.token_urlsafe(64)
        estado = PEDIDOS_PENDENTES.guardar(
            PedidoPendente(id_usuario, self.nome, escopos, verificador, credenciais.agora() + VALIDADE_DO_ESTADO)
        )
        configuracao = self.configuracao
        parametros = {
            "response_type": "code",
            "client_id": configuracao.client_id,
            "redirect_uri": configuracao.redirect_uri,
            "scope": " ".join(sorted(escopos | set(configuracao.escopos_sempre))),
            "state": estado,
            "code_challenge": _desafio_pkce(verificador),
            "code_challenge_method": "S256",
            **configuracao.parametros_da_autorizacao,
        }
        return f"{configuracao.url_de_autorizacao}?{urlencode(parametros)}"

    def cancelar(self, id_usuario, estado):
        """A pessoa recusou na tela de consentimento: esquece o pedido."""
        PEDIDOS_PENDENTES.retirar(estado, id_usuario, self.nome)

    def concluir(self, id_usuario, estado, codigo):
        """Troca o `codigo` por tokens e guarda a credencial de `id_usuario`. `AutorizacaoRecusada` se não valer."""
        pedido = PEDIDOS_PENDENTES.retirar(estado, id_usuario, self.nome)
        if pedido is None or not isinstance(codigo, str) or not 1 <= len(codigo) <= 2048:
            raise AutorizacaoRecusada(MENSAGEM_ESTADO_INVALIDO)
        formulario = {
            "grant_type": "authorization_code",
            "code": codigo,
            "redirect_uri": self.configuracao.redirect_uri,
            "code_verifier": pedido.code_verifier,
            **self._cliente(),
        }
        try:
            dados = self._pedir_token("trocar_codigo", formulario)
        except PedidoRecusado:
            raise AutorizacaoRecusada(MENSAGEM_CODIGO_RECUSADO) from None
        credencial = self._credencial(dados, anterior=None, solicitados=pedido.escopos)
        self.provedor.guardar(id_usuario, self.nome, credencial)
        return credencial

    def renovar(self, credencial):
        """Uma `Credencial` nova a partir do token de renovação. Autorização acabada: `ConcessaoRevogada`."""
        formulario = {"grant_type": "refresh_token", "refresh_token": credencial.refresh_token, **self._cliente()}
        try:
            dados = self._pedir_token("renovar", formulario)
        except PedidoRecusado as erro:
            if _erro_do_servico(erro) in ERROS_DE_AUTORIZACAO_ACABADA:
                raise credenciais.ConcessaoRevogada from None
            raise
        return self._credencial(dados, anterior=credencial)

    def desligar(self, id_usuario):
        """Esquece a conta da pessoa e, se o serviço permite, revoga o token. Falha na revogação não impede de esquecer."""
        credencial = self.provedor.ler(id_usuario, self.nome)
        self.provedor.apagar(id_usuario, self.nome)
        url = self.configuracao.url_de_revogacao
        token = credencial and (credencial.refresh_token or credencial.access_token)
        if url and token:
            try:
                self._chamar("revogar", lambda: pedir("POST", url, formulario={"token": token}, repetivel=True))
            except (ConnectionError, TimeoutError, PedidoRecusado):
                pass  # o token já saiu daqui; o serviço o invalida quando vencer ou quando a pessoa revogar lá

    def _cliente(self):
        configuracao = self.configuracao
        cliente = {"client_id": configuracao.client_id}
        if configuracao.client_secret:
            cliente["client_secret"] = configuracao.client_secret
        return cliente

    def _pedir_token(self, etapa, formulario):
        url = self.configuracao.url_do_token
        # 401 aqui (`CredencialRecusada`) é o client_id ou o client_secret do app errados: erro de configuração
        return self._chamar(etapa, lambda: pedir("POST", url, formulario=formulario, repetivel=True)).dados

    def _credencial(self, dados, anterior, solicitados=frozenset()):
        """Valida a resposta do endereço de token e monta a `Credencial`. Formato estranho: `RespostaInvalida`."""
        if not isinstance(dados, dict):
            raise RespostaInvalida(MENSAGEM_RESPOSTA_INVALIDA)
        token = dados.get("access_token")
        duracao = dados.get("expires_in")
        if not token_valido(token) or str(dados.get("token_type", "")).lower() != "bearer":
            raise RespostaInvalida(MENSAGEM_RESPOSTA_INVALIDA)
        if isinstance(duracao, str) and duracao.isdigit():
            duracao = int(duracao)
        if type(duracao) is not int or not 1 <= duracao <= SEGUNDOS_DO_TOKEN_NO_MAXIMO:
            raise RespostaInvalida(MENSAGEM_RESPOSTA_INVALIDA)
        renovacao = dados.get("refresh_token") or (anterior.refresh_token if anterior else None)
        if renovacao is not None and not token_valido(renovacao):
            raise RespostaInvalida(MENSAGEM_RESPOSTA_INVALIDA)
        concedidos = escopos_de(dados.get("scope")) or (anterior.escopos if anterior else frozenset(solicitados))
        return credenciais.Credencial(token, credenciais.agora() + timedelta(seconds=duracao), concedidos, renovacao)


def token_valido(valor):
    """Token de verdade: texto sem espaço nem caractere de controle (vai num cabeçalho `Authorization`)."""
    return isinstance(valor, str) and 10 <= len(valor) <= 4096 and valor.isascii() and valor.isprintable() and " " not in valor
