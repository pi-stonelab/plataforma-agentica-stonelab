"""Slack (Web API): mensagem num canal interno da lista permitida, pelo bot da plataforma.

Configuração (.env): `SLACK_TOKEN` (token de bot, `xoxb-...`, com o escopo `chat:write`) e `SLACK_CANAIS`
(`apelido:ID` separados por vírgula, como `financeiro:C0123ABCD,plantao:C0456EFGH`). O modelo e a pessoa só
usam o apelido; o ID do canal fica no .env. Preencher o `SLACK_TOKEN` liga a integração; `SLACK_MODO` força
`real`, `simulado` ou `desligado`. `SLACK_URL` só existe para os testes (padrão: https://slack.com/api).

O Slack responde 200 também quando recusa: o resultado está em `{"ok": false, "error": "..."}`. Recusa quer
dizer que nada foi publicado. No modo simulado, a mensagem fica em memória (`MensagensSimuladas`) e a resposta
diz isso em `fonte`.

Pedidos (documentação oficial: https://docs.slack.dev/reference/methods/chat.postMessage e
https://docs.slack.dev/reference/methods/auth.test):
- POST /chat.postMessage  {"channel": ID, "text": ..., "unfurl_links": false, "unfurl_media": false}
                           → {"ok": true, "channel": ID, "ts": "1503435956.000247"}
- GET  /auth.test          → {"ok": true, "team": ..., "user": ...}   (só o `testar`; leitura, não publica nada)
"""

import os
import re
import threading
from collections import deque

from mock import falhas

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http
from ferramentas.integracoes.cliente_http import (
    CredencialRecusada,
    LimiteDePedidos,
    RespostaInvalida,
)
from ferramentas.integracoes.conector import Conector, ConfiguracaoInvalida, ler_destinos
from ferramentas.integracoes.registro import registrar

SLACK_PADRAO = "https://slack.com/api"
PADRAO_TOKEN = re.compile(r"xoxb-[A-Za-z0-9-]{10,250}")
PADRAO_CANAL = re.compile(r"[CG][A-Z0-9]{8,12}")
PADRAO_TS = re.compile(r"[0-9]{1,12}\.[0-9]{1,8}")
TAMANHO_MAXIMO_DO_TEXTO = 3000  # o Slack recomenda até 4.000 caracteres por mensagem
FONTE_REAL = "Slack"
FONTE_SIMULADA = "Slack simulado (modo de demonstração): nada foi publicado no Slack de verdade"
MENSAGEM_TESTE_SIMULADO = "Modo simulado: as mensagens ficam na memória da plataforma, sem chamar o Slack."
# Erros do Slack ({"ok": false, "error": ...}) e o que cada um quer dizer para quem usa. Nada foi publicado.
ERROS_DE_CREDENCIAL = frozenset(
    {"invalid_auth", "not_authed", "account_inactive", "token_revoked", "token_expired", "missing_scope",
     "no_permission", "not_allowed_token_type", "ekm_access_denied"}
)
ERROS_DO_CANAL = frozenset({"channel_not_found", "not_in_channel", "is_archived", "restricted_action"})
ERROS_DO_TEXTO = frozenset({"msg_too_long", "no_text", "invalid_blocks", "too_many_attachments"})
ERROS_DE_LIMITE = frozenset({"ratelimited", "rate_limited", "message_limit_exceeded"})
MENSAGEM_CANAL_RECUSOU = (
    "O Slack não aceitou a mensagem no canal {apelido}: o canal não existe mais ou o bot não foi convidado para"
    " ele. Nada foi enviado; avise quem administra a plataforma."
)
MENSAGEM_TEXTO_RECUSADO = "O Slack recusou o texto (vazio ou longo demais). Nada foi enviado."
LIMITE_DE_SIMULADAS = 50
CANAIS_SIMULADOS = {"plantao": "C0000PLANT", "financeiro": "C0000FINAN"}  # modo simulado sem SLACK_CANAIS


class MensagensSimuladas:
    """As mensagens do modo simulado, em memória e só as últimas `LIMITE_DE_SIMULADAS` (testes e demo)."""

    def __init__(self):
        self._trava = threading.Lock()
        self._mensagens = deque(maxlen=LIMITE_DE_SIMULADAS)
        self._contador = 0

    def publicar(self, apelido, texto):
        with self._trava:
            self._contador += 1
            id_mensagem = f"SIM-{self._contador}"
            self._mensagens.append({"id_mensagem": id_mensagem, "canal": apelido, "texto": texto})
            return id_mensagem

    def listar(self):
        with self._trava:
            return [dict(mensagem) for mensagem in self._mensagens]

    def limpar(self):
        with self._trava:
            self._mensagens.clear()
            self._contador = 0


def _resultado_do_slack(dados, apelido):
    """O `ts` da mensagem publicada, ou o erro do Slack traduzido. Resposta sem `ok`: incerto."""
    if not isinstance(dados, dict) or not isinstance(dados.get("ok"), bool):
        raise EfeitoIncerto()  # o Slack recebeu o pedido, mas não dá para saber se publicou
    if dados["ok"]:
        ts = dados.get("ts")
        if not isinstance(ts, str) or not PADRAO_TS.fullmatch(ts):
            raise EfeitoIncerto()
        return ts
    erro = dados.get("error")
    if erro in ERROS_DE_CREDENCIAL:
        raise CredencialRecusada(cliente_http.MENSAGEM)
    if erro in ERROS_DO_CANAL:
        raise ErroFerramenta("integracao_indisponivel", MENSAGEM_CANAL_RECUSOU.format(apelido=apelido))
    if erro in ERROS_DO_TEXTO:
        raise ErroFerramenta("parametro_invalido", MENSAGEM_TEXTO_RECUSADO)
    if erro in ERROS_DE_LIMITE:
        raise LimiteDePedidos(cliente_http.MENSAGEM)
    raise ConnectionError(cliente_http.MENSAGEM)  # outra recusa do Slack: nada foi publicado


class ConectorSlack(Conector):
    nome = "slack"
    rotulo = "Slack"
    variavel_modo = "SLACK_MODO"
    modo_padrao = "desligado"
    variavel_que_liga = "SLACK_TOKEN"
    variaveis = ("SLACK_MODO", "SLACK_TOKEN", "SLACK_CANAIS", "SLACK_URL")
    credencial = "plataforma"
    mensagem_desligada = "O envio de mensagens no Slack não está ligado nesta plataforma."
    como_ligar = "preencha SLACK_TOKEN e SLACK_CANAIS (ou use SLACK_MODO=simulado)"
    dica_sem_rede = "Confira a internet, ou use SLACK_MODO=simulado."
    dicas = {
        "SLACK_TOKEN": "SLACK_TOKEN inválido: use o token de bot do app (começa com xoxb-), com o escopo chat:write.",
        "SLACK_CANAIS": (
            "SLACK_CANAIS inválida: apelido:ID separados por vírgula, como financeiro:C0123ABCD. O apelido usa"
            " letras minúsculas, números, - e _; o ID está em Detalhes do canal, no Slack."
        ),
        "SLACK_URL": "SLACK_URL inválida: deixe vazia (usa https://slack.com/api).",
    }

    def __init__(self):
        super().__init__()
        self.simuladas = MensagensSimuladas()

    def _url(self, ambiente):
        return cliente_http.url_base(ambiente.get("SLACK_URL") or SLACK_PADRAO, "SLACK_URL")

    def _token(self, ambiente):
        token = ambiente.get("SLACK_TOKEN", "").strip()
        if not PADRAO_TOKEN.fullmatch(token):
            raise ConfiguracaoInvalida("SLACK_TOKEN")
        return token

    def canais(self, ambiente=os.environ):
        """{apelido: ID} dos canais liberados no .env. No simulado sem lista: os de exemplo."""
        canais = ler_destinos(ambiente, "SLACK_CANAIS", PADRAO_CANAL)
        if not canais and self.modo(ambiente) == "simulado":
            return dict(CANAIS_SIMULADOS)
        return canais

    def conferir_configuracao(self, ambiente=os.environ):
        self._url(ambiente)
        self._token(ambiente)
        if not self.canais(ambiente):
            raise ConfiguracaoInvalida("SLACK_CANAIS")

    def fora_do_ar(self):
        return falhas.fora_do_ar("slack")

    def _ligado(self, ambiente):
        modo = self.exigir_ligado(ambiente)
        if self.fora_do_ar():
            raise ConnectionError("slack fora do ar (falha simulada)")
        return modo

    def apelidos(self, ambiente=os.environ):
        """Os apelidos liberados agora, para as mensagens de erro e para a prévia."""
        return sorted(self.canais(ambiente))

    def _cabecalhos(self, ambiente):
        return {"Authorization": f"Bearer {self._token(ambiente)}", "Content-Type": "application/json; charset=utf-8"}

    def publicar(self, apelido, texto, ambiente=os.environ):
        """Publica `texto` no canal do `apelido` e devolve o id da mensagem (o `ts` do Slack)."""
        modo = self._ligado(ambiente)
        canais = self.canais(ambiente)
        self.exigir_destino(apelido, canais)
        if modo == "simulado":
            return self.simuladas.publicar(apelido, texto)
        url = cliente_http.montar_url(self._url(ambiente), "chat.postMessage")
        corpo = {"channel": canais[apelido], "text": texto, "unfurl_links": False, "unfurl_media": False}
        cabecalhos = self._cabecalhos(ambiente)
        return self.chamar(
            "publicar",
            lambda: _resultado_do_slack(cliente_http.pedir("POST", url, corpo=corpo, cabecalhos=cabecalhos).dados, apelido),
        )

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        url = cliente_http.montar_url(self._url(ambiente), "auth.test")
        cabecalhos = self._cabecalhos(ambiente)
        dados = self.chamar("testar", lambda: cliente_http.pedir("GET", url, cabecalhos=cabecalhos).dados)
        if not isinstance(dados, dict) or dados.get("ok") is not True:
            if isinstance(dados, dict) and dados.get("error") in ERROS_DE_CREDENCIAL:
                raise CredencialRecusada(cliente_http.MENSAGEM)
            raise RespostaInvalida("resposta fora do formato")
        canais = ", ".join(self.apelidos(ambiente))
        return f"O Slack aceitou o token do bot. Canais liberados: {canais} (o bot precisa ter sido convidado a cada um)."

    def reiniciar(self):
        super().reiniciar()
        self.simuladas.limpar()


CONECTOR = registrar(ConectorSlack())
