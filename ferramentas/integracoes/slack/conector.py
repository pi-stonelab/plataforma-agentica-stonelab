"""Slack (Web API): mensagem num canal interno da lista permitida, pelo bot da plataforma.

Configuração (.env): `SLACK_TOKEN` (token de bot, `xoxb-...`, com os escopos `chat:write` e `channels:read`)
e `SLACK_CANAIS` (`apelido:ID[:Nome]` separados por vírgula, como
`financeiro:C0123ABCD:Time financeiro,plantao:C0456EFGH`). O modelo e a pessoa só usam o apelido; o ID do canal
fica no .env, e o nome (opcional) aparece no cartão de confirmação. Preencher o `SLACK_TOKEN` liga a integração;
`SLACK_MODO` força `real`, `simulado` ou `desligado`. `SLACK_URL` só existe para os testes (padrão:
https://slack.com/api).

O texto vai como texto puro: `&`, `<` e `>` viram `&amp;`, `&lt;` e `&gt;` (o escape que a documentação manda) e
`mrkdwn` fica desligado. Assim `<!channel>`, `<@U123>` e `<https://site|texto disfarçado>` escritos por alguém
(ou copiados de um e-mail de lojista) aparecem como texto e não notificam o canal nem viram link.

O Slack responde 200 também quando recusa: o resultado está em `{"ok": false, "error": "..."}`. Recusa quer
dizer que nada foi publicado. No modo simulado, a mensagem fica na caixa de saída simulada (`simuladas.py`) e a
resposta diz isso em `fonte`.

Pedidos (documentação oficial: https://docs.slack.dev/reference/methods/chat.postMessage,
https://docs.slack.dev/reference/methods/auth.test, https://docs.slack.dev/reference/methods/conversations.info e
https://docs.slack.dev/apis/web-api/rate-limits):
- POST /chat.postMessage  {"channel": ID, "text": ..., "mrkdwn": false, "unfurl_links": false, "unfurl_media": false}
                           → {"ok": true, "channel": ID, "ts": "1503435956.000247"}
- GET  /auth.test          → {"ok": true, "team": ..., "user": ...}   (só o `testar`)
- GET  /conversations.info?channel=ID → {"ok": true, "channel": {"name": ..., "is_member": true}}   (só o `testar`)
- 429 com `Retry-After` (segundos) quando passa do limite.
"""

import os
import re

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http, simuladas
from ferramentas.integracoes.cliente_http import RespostaInvalida
from ferramentas.integracoes.conector import (
    Conector,
    ConfiguracaoInvalida,
    CredencialRecusada,
    LimiteDePedidos,
    ler_destinos,
    ler_rotulos,
)
from ferramentas.integracoes.registro import registrar

SLACK_PADRAO = "https://slack.com/api"
PADRAO_TOKEN = re.compile(r"xoxb-[A-Za-z0-9-]{10,250}")
PADRAO_CANAL = re.compile(r"[CG][A-Z0-9]{8,12}")
PADRAO_TS = re.compile(r"[0-9]{1,12}\.[0-9]{1,8}")
TAMANHO_MAXIMO_DO_TEXTO = 3000  # o Slack recomenda até 4.000 caracteres por mensagem
FONTE_REAL = "Slack"
FONTE_SIMULADA = "Slack simulado (modo de demonstração): nada foi publicado no Slack de verdade"
MENSAGEM_TESTE_SIMULADO = (
    "Modo simulado: as mensagens ficam na caixa de saída simulada da plataforma, sem chamar o Slack"
    " (python -m ferramentas.integracoes simuladas mostra o que teria saído)."
)
MENSAGEM_DE_TESTE = "Teste da Plataforma Agêntica: a integração com o Slack está funcionando."
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
CANAIS_SIMULADOS = {"plantao": "C0000PLANT", "financeiro": "C0000FINAN"}  # modo simulado sem SLACK_CANAIS
ROTULOS_SIMULADOS = {"plantao": "Plantão de atendimento (demonstração)", "financeiro": "Time financeiro (demonstração)"}


def escapar(texto):
    """O escape do Slack para texto puro: `&`, `<` e `>` (nesta ordem, para o `&` do escape não ser trocado)."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        raise LimiteDePedidos(cliente_http.MENSAGEM)  # o 429 de verdade (com Retry-After) vem do `cliente_http`
    raise ConnectionError(cliente_http.MENSAGEM)  # outra recusa do Slack: nada foi publicado


class ConectorSlack(Conector):
    nome = "slack"
    rotulo = "Slack"
    variavel_modo = "SLACK_MODO"
    modo_padrao = "desligado"
    variavel_que_liga = "SLACK_TOKEN"
    variaveis = ("SLACK_MODO", "SLACK_TOKEN", "SLACK_CANAIS", "SLACK_URL")
    servicos = ("publicar", "testar")
    credencial = "plataforma"
    mensagem_desligada = "O envio de mensagens no Slack não está ligado nesta plataforma."
    como_ligar = "preencha SLACK_TOKEN e SLACK_CANAIS (ou use SLACK_MODO=simulado)"
    dica_sem_rede = "Confira a internet, ou use SLACK_MODO=simulado."
    dicas = {
        "SLACK_TOKEN": (
            "SLACK_TOKEN inválido: use o token de bot do app (começa com xoxb-), com os escopos chat:write e"
            " channels:read (veja ferramentas/integracoes/slack/README.md)."
        ),
        "SLACK_CANAIS": (
            "SLACK_CANAIS inválida: apelido:ID separados por vírgula, como financeiro:C0123ABCD, com um nome"
            " opcional depois (financeiro:C0123ABCD:Time financeiro). O apelido usa letras minúsculas, números,"
            " - e _; o ID está em Detalhes do canal, no Slack."
        ),
        "SLACK_URL": "SLACK_URL inválida: deixe vazia (usa https://slack.com/api).",
    }

    def __init__(self):
        super().__init__()
        self.simuladas = simuladas.caixa(self.nome)

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

    def rotulos(self, ambiente=os.environ):
        """{apelido: nome legível} dos canais que têm nome no .env (no simulado, os de exemplo)."""
        rotulos = ler_rotulos(ambiente, "SLACK_CANAIS")
        if not ler_destinos(ambiente, "SLACK_CANAIS", PADRAO_CANAL) and self.modo(ambiente) == "simulado":
            return dict(ROTULOS_SIMULADOS)
        return rotulos

    def conferir_configuracao(self, ambiente=os.environ):
        self._url(ambiente)
        self._token(ambiente)
        if not self.canais(ambiente):
            raise ConfiguracaoInvalida("SLACK_CANAIS")

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
            return self.simuladas.guardar(f"#{apelido}", texto)
        url = cliente_http.montar_url(self._url(ambiente), "chat.postMessage")
        corpo = {
            "channel": canais[apelido],
            "text": escapar(texto),
            "mrkdwn": False,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        cabecalhos = self._cabecalhos(ambiente)
        return self.chamar(
            "publicar",
            lambda: _resultado_do_slack(cliente_http.pedir("POST", url, corpo=corpo, cabecalhos=cabecalhos).dados, apelido),
            servico="publicar",
        )

    def _ler(self, ambiente, metodo, parametros=None):
        """GET de leitura do `testar`: o JSON do Slack, com a credencial recusada traduzida."""
        url = cliente_http.montar_url(self._url(ambiente), metodo)
        cabecalhos = self._cabecalhos(ambiente)
        dados = self.chamar(
            "testar", lambda: cliente_http.pedir("GET", url, parametros=parametros, cabecalhos=cabecalhos).dados,
            servico="testar",
        )
        if not isinstance(dados, dict) or not isinstance(dados.get("ok"), bool):
            raise RespostaInvalida("resposta fora do formato")
        if dados["ok"] is False and dados.get("error") in ERROS_DE_CREDENCIAL - {"missing_scope"}:
            raise CredencialRecusada(cliente_http.MENSAGEM)
        return dados

    def _conferir_canal(self, ambiente, apelido, identificador):
        """Uma frase sobre o canal: existe e o bot está nele, ou o que falta (sem publicar nada)."""
        dados = self._ler(ambiente, "conversations.info", {"channel": identificador})
        if dados["ok"]:
            canal = dados.get("channel") if isinstance(dados.get("channel"), dict) else {}
            if canal.get("is_member") is False:
                return f"#{apelido}: existe, mas o bot não está nele (no Slack, /invite @nome-do-bot)."
            return f"#{apelido}: ok."
        erro = dados.get("error")
        if erro == "missing_scope":
            return f"#{apelido}: não deu para conferir (falta o escopo channels:read no app)."
        if erro == "channel_not_found":
            return f"#{apelido}: canal não encontrado (confira o ID em SLACK_CANAIS ou convide o bot)."
        return f"#{apelido}: o Slack recusou a consulta."

    def testar(self, ambiente=os.environ, enviar_para=None):
        """Confere o token e cada canal da lista. Com `enviar_para` (um apelido), publica uma mensagem de teste."""
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        if not self._ler(ambiente, "auth.test")["ok"]:
            raise CredencialRecusada(cliente_http.MENSAGEM)
        linhas = ["O Slack aceitou o token do bot."]
        linhas += [self._conferir_canal(ambiente, a, i) for a, i in sorted(self.canais(ambiente).items())]
        if enviar_para:
            apelido = enviar_para.strip().lower()
            if apelido not in self.canais(ambiente):
                raise ErroFerramenta("parametro_invalido", f"{apelido} não está em SLACK_CANAIS.")
            self.publicar(apelido, MENSAGEM_DE_TESTE, ambiente)
            linhas.append(f"Mensagem de teste publicada em #{apelido}.")
        return " ".join(linhas)

    def reiniciar(self):
        super().reiniciar()
        self.simuladas.limpar()


CONECTOR = registrar(ConectorSlack())
