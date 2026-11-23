"""Servidores de teste do Jira, do Slack e do Telegram, em socket de verdade, no formato das APIs reais.

`ServidorDeApi(responder)` sobe um `ThreadingHTTPServer` em 127.0.0.1 e chama `responder(pedido)` a cada
pedido; `pedido` traz `metodo`, `caminho` (com a query), `cabecalhos` e `corpo` (o JSON lido, ou None). A
função devolve `(status, cabecalhos, corpo_em_bytes)`. Os pedidos ficam em `servidor.pedidos`, para o teste
conferir o que o conector mandou (inclusive o corpo: aqui os dados são sintéticos).

Formatos, da documentação oficial (os valores são inventados):
- Jira Cloud REST v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/ (issue, comment, myself,
  project). Erros como {"errorMessages": [...], "errors": {...}}.
- Slack Web API: https://docs.slack.dev/reference/methods/chat.postMessage e auth.test. Recusa com HTTP 200 e
  {"ok": false, "error": "..."}; limite com HTTP 429 e Retry-After.
- Telegram Bot API: https://core.telegram.org/bots/api (sendMessage e getMe). Recusa com
  {"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}.
"""

import base64
import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

JSON = {"Content-Type": "application/json; charset=utf-8"}

JIRA_EMAIL = "plataforma@stonelab.example"
JIRA_TOKEN = "ATATT3xFfGF0-token-de-teste-do-jira-0123456789"
JIRA_PROJETOS = "KAN,PLAT"
JIRA_TIPOS = "Tarefa,Bug"
SLACK_TOKEN = "xoxb-1111111111-2222222222-tokendeteste"
SLACK_CANAIS = "financeiro:C0123ABCD,plantao:C0456EFGH,arquivado:C0789IJKL"
TELEGRAM_TOKEN = "123456789:AAH-token-de-teste-do-telegram-abcdefg"
TELEGRAM_CHATS = "plantao:-1001234567890,coordenacao:987654321"


@dataclass
class Pedido:
    metodo: str
    caminho: str
    cabecalhos: dict
    corpo: object

    @property
    def rota(self):
        return urlsplit(self.caminho).path

    @property
    def consulta(self):
        return parse_qs(urlsplit(self.caminho).query)


def resposta_json(dados, status=200, extra=None):
    return status, {**JSON, **(extra or {})}, json.dumps(dados, ensure_ascii=False).encode()


class _Atendimento(BaseHTTPRequestHandler):
    def _atender(self):
        servidor = self.server
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho) if tamanho else b""
        try:
            corpo = json.loads(bruto) if bruto else None
        except ValueError:
            corpo = bruto
        pedido = Pedido(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, corpo)
        servidor.pedidos.append(pedido)
        if servidor.atraso:
            time.sleep(servidor.atraso)
        status, cabecalhos, resposta = servidor.responder(pedido)
        if status is None:  # derrubar a conexão sem responder (o pedido já chegou)
            self.close_connection = True
            return
        self.send_response(status)
        for nome, valor in cabecalhos.items():
            self.send_header(nome, valor)
        self.send_header("Content-Length", str(len(resposta)))
        self.end_headers()
        self.wfile.write(resposta)

    do_GET = do_POST = _atender

    def log_message(self, *args):
        return


class ServidorDeApi(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, responder, atraso=0.0):
        super().__init__(("127.0.0.1", 0), _Atendimento)
        self.responder = responder
        self.atraso = atraso
        self.pedidos = []
        self._linha = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def __enter__(self):
        self._linha.start()
        return self

    def __exit__(self, *erro):
        self.shutdown()
        self.server_close()


# --- Jira ------------------------------------------------------------------------------------------------


def adf(*paragrafos):
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragrafos],
    }


def _comentario(numero, texto, quando):
    return {
        "id": str(10000 + numero),
        "author": {"accountId": "5b10ac8d82e05b22cc7d4ef5", "displayName": "Maria Analista", "emailAddress": "maria@stonelab.example"},
        "body": adf(texto),
        "created": quando,
        "updated": quando,
    }


class JiraDeTeste:
    """Um Jira em memória: projetos KAN e PLAT, tipos por projeto, o chamado KAN-7 com 7 comentários."""

    def __init__(self):
        self.tipos_por_projeto = {"KAN": {"Tarefa", "Bug"}, "PLAT": {"Tarefa"}, "RH": {"Tarefa"}}
        self.chamados = {
            "KAN-7": {
                "summary": "Painel de liquidações lento",
                "status": {"name": "Em andamento", "statusCategory": {"key": "indeterminate"}},
                "issuetype": {"name": "Tarefa"},
                "priority": {"name": "Alta"},
                "created": "2026-11-20T10:15:30.000-0300",
                "updated": "2026-11-21T09:00:00.000-0300",
                "description": adf("O painel demora 40 s.", "Afeta o time de recebíveis."),
                "project": {"key": "KAN"},
                "comentarios": [
                    _comentario(n, f"Comentário {n}", f"2026-11-2{n % 10}T0{n}:00:00.000-0300") for n in range(1, 8)
                ],
            },
            "RH-1": {"summary": "Chamado de outro projeto", "project": {"key": "RH"}, "comentarios": []},
        }
        self.proximo = 124
        self.autorizacao = "Basic " + base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()

    def _nao_encontrado(self):
        return resposta_json({"errorMessages": ["Issue does not exist or you do not have permission to see it."], "errors": {}}, 404)

    def __call__(self, pedido):
        if pedido.cabecalhos.get("authorization") != self.autorizacao:
            return resposta_json({"errorMessages": ["You are not authenticated. Authentication required."]}, 401)
        partes = pedido.rota.strip("/").split("/")
        if partes[:3] != ["rest", "api", "3"]:
            return resposta_json({"errorMessages": ["not found"]}, 404)
        partes = partes[3:]
        if partes == ["myself"]:
            return resposta_json({"accountId": "5b10ac8d82e05b22cc7d4ef5", "emailAddress": JIRA_EMAIL, "active": True})
        if len(partes) == 2 and partes[0] == "project":
            if partes[1] not in self.tipos_por_projeto:
                return resposta_json({"errorMessages": ["No project could be found with key."]}, 404)
            return resposta_json({"id": "10000", "key": partes[1], "name": f"Projeto {partes[1]}"})
        if partes == ["issue"] and pedido.metodo == "POST":
            return self._criar(pedido.corpo)
        if len(partes) >= 2 and partes[0] == "issue":
            chamado = self.chamados.get(partes[1])
            if chamado is None:
                return self._nao_encontrado()
            if len(partes) == 2:
                campos = {k: v for k, v in chamado.items() if k != "comentarios"}
                return resposta_json({"id": "10007", "key": partes[1], "fields": campos})
            if partes[2] == "comment" and pedido.metodo == "GET":
                return self._comentarios(chamado, pedido.consulta)
            if partes[2] == "comment" and pedido.metodo == "POST":
                novo = _comentario(len(chamado["comentarios"]) + 50, "", "2026-11-22T10:00:00.000-0300")
                novo["body"] = pedido.corpo.get("body")
                chamado["comentarios"].append(novo)
                return resposta_json(novo, 201)
        return resposta_json({"errorMessages": ["not found"]}, 404)

    def _comentarios(self, chamado, consulta):
        maximo = int(consulta.get("maxResults", ["50"])[0])
        lista = sorted(chamado["comentarios"], key=lambda c: c["created"], reverse=consulta.get("orderBy") == ["-created"])
        return resposta_json({"startAt": 0, "maxResults": maximo, "total": len(lista), "comments": lista[:maximo]})

    def _criar(self, corpo):
        campos = corpo.get("fields", {}) if isinstance(corpo, dict) else {}
        projeto = campos.get("project", {}).get("key")
        tipo = campos.get("issuetype", {}).get("name")
        erros = {}
        if projeto not in self.tipos_por_projeto:
            erros["project"] = "valid project is required"
        elif tipo not in self.tipos_por_projeto[projeto]:
            erros["issuetype"] = "Specify a valid issue type"
        if not campos.get("summary") or "\n" in campos.get("summary", ""):
            erros["summary"] = "You must specify a summary of the issue."
        if erros:
            return resposta_json({"errorMessages": [], "errors": erros}, 400)
        chave = f"{projeto}-{self.proximo}"
        self.proximo += 1
        self.chamados[chave] = {**campos, "comentarios": []}
        return resposta_json({"id": "10100", "key": chave, "self": f"https://stonelab.atlassian.net/rest/api/3/issue/{chave}"}, 201)


def ambiente_do_jira(servidor, **extra):
    return {
        "JIRA_URL": servidor.url,
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_TOKEN": JIRA_TOKEN,
        "JIRA_PROJETOS": JIRA_PROJETOS,
        "JIRA_TIPOS": JIRA_TIPOS,
        **extra,
    }


# --- Slack -----------------------------------------------------------------------------------------------


class SlackDeTeste:
    """Canais C0123ABCD e C0456EFGH com o bot dentro; C0789IJKL arquivado; o resto não existe."""

    def __init__(self):
        self.publicadas = []
        self.recusa_seguinte = None  # força um {"ok": false, "error": ...} no próximo chat.postMessage

    def __call__(self, pedido):
        if pedido.cabecalhos.get("authorization") != f"Bearer {SLACK_TOKEN}":
            return resposta_json({"ok": False, "error": "invalid_auth"})
        if pedido.rota == "/auth.test":
            return resposta_json({"ok": True, "url": "https://stonelab.slack.com/", "team": "Stonelab", "user": "plataforma",
                                  "team_id": "T0001", "user_id": "U0001", "bot_id": "B0001"})
        if pedido.rota == "/chat.postMessage" and pedido.metodo == "POST":
            if self.recusa_seguinte:
                erro, self.recusa_seguinte = self.recusa_seguinte, None
                if erro == "ratelimited":
                    return resposta_json({"ok": False, "error": "ratelimited"}, 429, {"Retry-After": "30"})
                return resposta_json({"ok": False, "error": erro})
            canal = pedido.corpo.get("channel")
            if canal == "C0789IJKL":
                return resposta_json({"ok": False, "error": "is_archived"})
            if canal not in ("C0123ABCD", "C0456EFGH"):
                return resposta_json({"ok": False, "error": "channel_not_found"})
            self.publicadas.append(pedido.corpo)
            ts = f"1700000000.{len(self.publicadas):06d}"
            return resposta_json({"ok": True, "channel": canal, "ts": ts, "message": {"text": pedido.corpo.get("text"), "ts": ts}})
        return resposta_json({"ok": False, "error": "unknown_method"}, 404)


def ambiente_do_slack(servidor, **extra):
    return {"SLACK_URL": servidor.url, "SLACK_TOKEN": SLACK_TOKEN, "SLACK_CANAIS": SLACK_CANAIS, **extra}


# --- Telegram --------------------------------------------------------------------------------------------


class TelegramDeTeste:
    """O bot está nos chats -1001234567890 e 987654321; qualquer outro chat não existe para ele."""

    def __init__(self):
        self.enviadas = []

    def __call__(self, pedido):
        prefixo = f"/bot{TELEGRAM_TOKEN}/"
        if not pedido.rota.startswith(prefixo):
            return resposta_json({"ok": False, "error_code": 401, "description": "Unauthorized"}, 401)
        metodo = pedido.rota[len(prefixo):]
        if metodo == "getMe":
            return resposta_json({"ok": True, "result": {"id": 123456789, "is_bot": True, "first_name": "Plataforma",
                                                         "username": "stonelab_plataforma_bot"}})
        if metodo == "sendMessage" and pedido.metodo == "POST":
            if str(pedido.corpo.get("chat_id")) not in ("-1001234567890", "987654321"):
                return resposta_json({"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}, 400)
            self.enviadas.append(pedido.corpo)
            return resposta_json({"ok": True, "result": {"message_id": 40 + len(self.enviadas), "date": 1700000000,
                                                         "chat": {"id": pedido.corpo["chat_id"]}, "text": pedido.corpo["text"]}})
        return resposta_json({"ok": False, "error_code": 404, "description": "Not Found"}, 404)


def ambiente_do_telegram(servidor, **extra):
    return {"TELEGRAM_URL": servidor.url, "TELEGRAM_TOKEN": TELEGRAM_TOKEN, "TELEGRAM_CHATS": TELEGRAM_CHATS, **extra}
