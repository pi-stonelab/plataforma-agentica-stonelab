"""Servidores de teste do Google Workspace e do Microsoft 365, em socket de verdade, no formato das APIs reais.

`ServidorDeEscritorio(responder)` sobe um `ThreadingHTTPServer` em 127.0.0.1 e chama `responder(pedido)` a cada pedido
(GET, POST, PUT, PATCH e DELETE). `pedido` traz `metodo`, `caminho`, `cabecalhos`, `corpo` (o JSON lido, ou None),
`formulario` (o corpo application/x-www-form-urlencoded, como o endereço de token do OAuth) e `bruto` (os bytes). A
função devolve `(status, cabecalhos, corpo_em_bytes)`. Os pedidos ficam em `servidor.pedidos`. Os dados são todos
inventados.

`GoogleDeTeste` e `MicrosoftDeTeste` falam como as APIs (documentação oficial):
- OAuth2 com PKCE: endereço de token (`authorization_code` conferindo `code_verifier` contra o `code_challenge`,
  `refresh_token`), revogação (Google) e erros `invalid_grant` e `invalid_client`.
- Google: Calendar v3 (events.list e events.insert com `id` e 409), Drive v3 (files.list com `q`), Sheets v4 (get,
  values.get, values.append, create) e Docs v1 (documents.get).
- Microsoft Graph v1.0: calendarView e events, drive search, driveItem, workbook (worksheets, usedRange, range PATCH) e o
  download de arquivo, que responde 302 para o endereço temporário de outro servidor.
Cada API confere o token (401 se desconhecido ou vencido) e o escopo do endpoint (403, no formato de cada uma).
"""

import base64
import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

JSON = {"Content-Type": "application/json; charset=utf-8"}

GOOGLE_CLIENT_ID = "123456789012-abcdefghijklmnop.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-segredo-de-teste-abcdefghij"
GOOGLE_REDIRECT_URI = "http://localhost:8000/integracoes/google_workspace/callback"
MICROSOFT_CLIENT_ID = "11111111-2222-3333-4444-555555555555"
MICROSOFT_CLIENT_SECRET = "segredo~de~teste~da~microsoft~0123"
MICROSOFT_REDIRECT_URI = "http://localhost:8000/integracoes/microsoft_365/callback"
MICROSOFT_TENANT = "99999999-8888-7777-6666-555555555555"
DOMINIOS = "stone.example,filial.example"
AUTH = "https://www.googleapis.com/auth/"
LEITURA_GOOGLE = (
    AUTH + "calendar.events.readonly", AUTH + "spreadsheets.readonly", AUTH + "documents.readonly",
    AUTH + "drive.metadata.readonly",
)
ESCRITA_GOOGLE = (AUTH + "calendar.events", AUTH + "spreadsheets")
LEITURA_MICROSOFT = ("Calendars.Read", "Files.Read", "offline_access")
ESCRITA_MICROSOFT = ("Calendars.ReadWrite", "Files.ReadWrite")


@dataclass
class Pedido:
    metodo: str
    caminho: str
    cabecalhos: dict
    corpo: object = None
    formulario: dict | None = None
    bruto: bytes = b""

    @property
    def rota(self):
        return urlsplit(self.caminho).path

    @property
    def consulta(self):
        return {k: v[0] for k, v in parse_qs(urlsplit(self.caminho).query, keep_blank_values=True).items()}

    @property
    def token(self):
        valor = self.cabecalhos.get("authorization", "")
        return valor[7:] if valor.startswith("Bearer ") else None


def resposta_json(dados, status=200, extra=None):
    return status, {**JSON, **(extra or {})}, json.dumps(dados, ensure_ascii=False).encode()


class _Atendimento(BaseHTTPRequestHandler):
    def _atender(self):
        servidor = self.server
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho) if tamanho else b""
        tipo = self.headers.get("Content-Type", "")
        corpo, formulario = None, None
        if "json" in tipo and bruto:
            corpo = json.loads(bruto)
        elif "x-www-form-urlencoded" in tipo:
            formulario = {k: v[0] for k, v in parse_qs(bruto.decode(), keep_blank_values=True).items()}
        pedido = Pedido(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, corpo, formulario, bruto)
        servidor.pedidos.append(pedido)
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

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _atender

    def log_message(self, *args):
        return


class ServidorDeEscritorio(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, responder):
        super().__init__(("127.0.0.1", 0), _Atendimento)
        self.responder = responder
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


def desafio_pkce(verificador):
    return base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()


@dataclass
class Token:
    usuario: str
    escopos: set
    vence_em: float = field(default_factory=lambda: time.time() + 3600)


class ServicoOAuthDeTeste:
    """O que Google e Microsoft têm igual no OAuth: códigos, tokens, renovação e conferência do PKCE."""

    def __init__(self, client_id, client_secret, redirect_uri, prefixo_do_token):
        self.client_id, self.client_secret, self.redirect_uri = client_id, client_secret, redirect_uri
        self.prefixo = prefixo_do_token
        self.codigos = {}
        self.tokens = {}
        self.renovacoes = {}
        self.proximas = []  # respostas forçadas das APIs (limite, erro 5xx...), usadas uma a uma
        self.expira_em_segundos = 3600
        self.contador = 0
        self.renova_o_refresh_token = False
        self.escopos_concedidos_a_menos = None  # consentimento granular: o serviço concede menos do que a tela pediu

    def consentir(self, usuario, url_de_autorizacao):
        """A pessoa clica em "permitir" na tela do serviço: devolve o `code` que viria no endereço de retorno."""
        consulta = {k: v[0] for k, v in parse_qs(urlsplit(url_de_autorizacao).query).items()}
        assert consulta["response_type"] == "code" and consulta["code_challenge_method"] == "S256"
        assert consulta["client_id"] == self.client_id and consulta["redirect_uri"] == self.redirect_uri
        self.contador += 1
        codigo = f"codigo-de-teste-{self.contador}"
        escopos = set(consulta["scope"].split())
        if self.escopos_concedidos_a_menos is not None:
            escopos &= set(self.escopos_concedidos_a_menos)
        self.codigos[codigo] = {"usuario": usuario, "escopos": escopos, "desafio": consulta["code_challenge"]}
        return codigo, consulta["state"]

    def emitir(self, usuario, escopos, com_refresh=True):
        """Cria direto um par de tokens (para os testes que não passam pela tela de consentimento)."""
        self.contador += 1
        acesso = f"{self.prefixo}token-de-acesso-{self.contador}"
        self.tokens[acesso] = Token(usuario, set(escopos), time.time() + self.expira_em_segundos)
        renovacao = None
        if com_refresh:
            renovacao = f"1//renovacao-de-teste-{self.contador}"
            self.renovacoes[renovacao] = {"usuario": usuario, "escopos": set(escopos)}
        return acesso, renovacao

    def vencer(self, acesso):
        self.tokens[acesso].vence_em = time.time() - 1

    def _erro_de_token(self, codigo, status=400):
        return resposta_json({"error": codigo, "error_description": "descrição que nunca vai a mensagem"}, status)

    def endereco_de_token(self, pedido):
        f = pedido.formulario or {}
        if f.get("client_id") != self.client_id or (f.get("client_secret") and f["client_secret"] != self.client_secret):
            return self._erro_de_token("invalid_client", 401)
        if f.get("grant_type") == "authorization_code":
            dados = self.codigos.pop(f.get("code"), None)
            if dados is None or f.get("redirect_uri") != self.redirect_uri:
                return self._erro_de_token("invalid_grant")
            if desafio_pkce(f.get("code_verifier", "")) != dados["desafio"]:
                return self._erro_de_token("invalid_grant")
            acesso, renovacao = self.emitir(dados["usuario"], dados["escopos"])
            return resposta_json(self._token(acesso, renovacao, dados["escopos"]))
        if f.get("grant_type") == "refresh_token":
            dados = self.renovacoes.get(f.get("refresh_token"))
            if dados is None:
                return self._erro_de_token("invalid_grant")
            acesso, novo = self.emitir(dados["usuario"], dados["escopos"], com_refresh=self.renova_o_refresh_token)
            if self.renova_o_refresh_token:
                del self.renovacoes[f["refresh_token"]]
            return resposta_json(self._token(acesso, novo, dados["escopos"]))
        return self._erro_de_token("unsupported_grant_type")

    def _token(self, acesso, renovacao, escopos):
        dados = {"access_token": acesso, "expires_in": self.expira_em_segundos, "token_type": "Bearer",
                 "scope": " ".join(sorted(escopos))}
        if renovacao:
            dados["refresh_token"] = renovacao
        return dados

    def autenticar(self, pedido, aceitos):
        """(None, Token) se o token vale e tem algum dos escopos `aceitos`; senão (resposta de erro, None)."""
        token = self.tokens.get(pedido.token)
        if token is None or token.vence_em <= time.time():
            return self.erro_de_credencial(), None
        if not token.escopos & set(aceitos):
            return self.erro_de_escopo(), None
        return None, token

    def erro_de_credencial(self):
        raise NotImplementedError

    def erro_de_escopo(self):
        raise NotImplementedError

    def forcada(self):
        return self.proximas.pop(0) if self.proximas else None


# --- Google ------------------------------------------------------------------------------------------------------


def _escopos_da_agenda(escrita):
    return {AUTH + "calendar.events" if escrita else AUTH + "calendar.events.readonly", AUTH + "calendar"}


class GoogleDeTeste(ServicoOAuthDeTeste):
    """Um Google em memória: agenda, Drive, Planilhas e Docs de cada pessoa."""

    def __init__(self):
        super().__init__(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, "ya29.")
        self.revogados = []
        self.eventos = {}
        self.planilhas = {
            "1aBcD-planilha-de-teste_01": {
                "titulo": "Acompanhamento de testes",
                "dono": "F0001",
                "modificado": "2026-10-14T09:00:00.000Z",
                "abas": {
                    "Resumo": [["Semana", "Abertos", "Fechados"], ["28/09", "10", "8"], ["05/10", "12", "11"]],
                    "Outra aba": [["Fila", "Total"], ["Recebimento", "7"]],
                },
            }
        }
        self.documentos = {
            "1xYz-documento-de-teste_01": {
                "titulo": "Guia de testes", "dono": "F0001", "modificado": "2026-10-13T10:00:00.000Z",
                "paragrafos": ["Primeiro parágrafo do guia.\n", "Segundo parágrafo, com mais texto.\n"],
                "tabela": [["Passo", "Quem"], ["Abrir", "Ana"]],
            }
        }

    def erro_de_credencial(self):
        return resposta_json({"error": {"code": 401, "message": "Invalid Credentials", "status": "UNAUTHENTICATED"}}, 401)

    def erro_de_escopo(self):
        erro = {
            "code": 403, "message": "Request had insufficient authentication scopes.", "status": "PERMISSION_DENIED",
            "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}],
        }
        return resposta_json({"error": erro}, 403)

    def erro_de_limite(self):
        erro = {"code": 403, "message": "Rate Limit Exceeded", "errors": [{"reason": "rateLimitExceeded"}]}
        return resposta_json({"error": erro}, 403)

    def erro_sem_acesso(self):
        erro = {"code": 403, "message": "The caller does not have permission", "status": "PERMISSION_DENIED"}
        return resposta_json({"error": erro}, 403)

    def __call__(self, pedido):
        rota = pedido.rota
        if rota == "/token":
            return self.endereco_de_token(pedido)
        if rota == "/revoke":
            self.revogados.append((pedido.formulario or {}).get("token"))
            return resposta_json({})
        forcada = self.forcada()
        if forcada is not None:
            return forcada
        if rota.startswith("/calendar/v3/calendars/primary/events"):
            return self._agenda(pedido)
        if rota == "/drive/v3/files":
            return self._arquivos(pedido)
        if rota.startswith("/v4/spreadsheets"):
            return self._planilhas(pedido)
        if rota.startswith("/v1/documents/"):
            return self._documento(pedido)
        return resposta_json({"error": {"code": 404, "message": "Not Found"}}, 404)

    # Calendar
    def _agenda(self, pedido):
        escrita = pedido.metodo == "POST"
        erro, token = self.autenticar(pedido, _escopos_da_agenda(escrita))
        if erro:
            return erro
        eventos = self.eventos.setdefault(token.usuario, [])
        if escrita:
            corpo = pedido.corpo
            if not re.fullmatch(r"[a-v0-9]{5,1024}", corpo["id"]):
                return resposta_json({"error": {"code": 400, "message": "Invalid resource id value."}}, 400)
            if any(e["id"] == corpo["id"] for e in eventos):
                return resposta_json({"error": {"code": 409, "message": "The requested identifier already exists."}}, 409)
            eventos.append({**corpo, "status": "confirmed", "htmlLink": "https://calendar.example/evento"})
            return resposta_json(eventos[-1])
        consulta = pedido.consulta
        minimo, maximo = datetime.fromisoformat(consulta["timeMin"]), datetime.fromisoformat(consulta["timeMax"])
        assert consulta["singleEvents"] == "true" and consulta["orderBy"] == "startTime"
        dentro = [e for e in eventos if minimo <= _inicio_do_evento(e) < maximo]
        dentro.sort(key=_inicio_do_evento)
        return resposta_json({"kind": "calendar#events", "items": dentro[: int(consulta["maxResults"])]})

    # Drive
    def _arquivos(self, pedido):
        erro, token = self.autenticar(
            pedido, {AUTH + "drive.metadata.readonly", AUTH + "drive.metadata", AUTH + "drive.readonly", AUTH + "drive"}
        )
        if erro:
            return erro
        q = pedido.consulta["q"]
        assert "trashed = false" in q
        nome = re.search(r"name contains '((?:[^'\\]|\\.)*)'", q).group(1)
        nome = re.sub(r"\\(.)", r"\1", nome).lower()
        mime = re.search(r"mimeType = '([^']+)'", q)
        achados = []
        for id_arquivo, item in {**self.planilhas, **self.documentos}.items():
            tipo = "application/vnd.google-apps.spreadsheet" if id_arquivo in self.planilhas else "application/vnd.google-apps.document"
            if item["dono"] == token.usuario and nome in item["titulo"].lower() and (not mime or mime.group(1) == tipo):
                achados.append({"id": id_arquivo, "name": item["titulo"], "mimeType": tipo, "modifiedTime": item["modificado"]})
        return resposta_json({"files": achados[: int(pedido.consulta["pageSize"])]})

    # Sheets
    def _planilhas(self, pedido):
        partes = unquote(pedido.rota).split("/")  # "", "v4", "spreadsheets", id, "values", range
        if pedido.metodo == "POST" and len(partes) == 3:
            erro, token = self.autenticar(pedido, {AUTH + "spreadsheets", AUTH + "drive"})
            return erro or self._criar_planilha(token, pedido.corpo)
        leitura = {AUTH + "spreadsheets.readonly", AUTH + "spreadsheets", AUTH + "drive.readonly", AUTH + "drive"}
        erro, token = self.autenticar(
            pedido, {AUTH + "spreadsheets", AUTH + "drive"} if pedido.metodo == "POST" else leitura
        )
        if erro:
            return erro
        planilha = self.planilhas.get(partes[3])
        if planilha is None or planilha["dono"] != token.usuario:
            return resposta_json({"error": {"code": 404, "message": "Requested entity was not found."}}, 404)
        if len(partes) == 4:
            abas = [
                {"properties": {"title": nome, "gridProperties": {"rowCount": len(linhas), "columnCount": max(map(len, linhas))}}}
                for nome, linhas in planilha["abas"].items()
            ]
            return resposta_json({"properties": {"title": planilha["titulo"]}, "sheets": abas})
        intervalo = "/".join(partes[5:])
        if pedido.metodo == "POST":
            return self._anexar(planilha, intervalo, pedido)
        aba, _, area = intervalo.partition("!")
        aba = aba.strip("'").replace("''", "'")
        if aba not in planilha["abas"]:
            return resposta_json({"error": {"code": 400, "message": "Unable to parse range"}}, 400)
        achado = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", area)
        primeira, ultima = int(achado.group(2)), int(achado.group(4))
        linhas = [linha for linha in planilha["abas"][aba][primeira - 1 : ultima]]
        return resposta_json({"range": intervalo, "majorDimension": "ROWS", "values": linhas})

    def _anexar(self, planilha, intervalo, pedido):
        consulta = pedido.consulta
        assert consulta["valueInputOption"] == "RAW" and consulta["insertDataOption"] == "INSERT_ROWS"
        aba = intervalo.split("!")[0].strip("'").replace("''", "'")
        assert intervalo.endswith(":append")
        if aba not in planilha["abas"]:
            return resposta_json({"error": {"code": 400, "message": "Unable to parse range"}}, 400)
        planilha["abas"][aba].extend(pedido.corpo["values"])
        return resposta_json({"updates": {"updatedRows": len(pedido.corpo["values"]), "updatedCells": 3}})

    def _criar_planilha(self, token, corpo):
        self.contador += 1
        id_arquivo = f"1novaPlanilha-{self.contador}_abcdef"
        linhas = []
        for linha in corpo["sheets"][0]["data"][0]["rowData"]:
            celulas = []
            for celula in linha["values"]:
                valor = celula["userEnteredValue"]
                assert set(valor) <= {"stringValue", "numberValue"}  # nunca fórmula
                numero = valor.get("numberValue")
                celulas.append(valor["stringValue"] if numero is None else f"{numero:g}")
            linhas.append(celulas)
        self.planilhas[id_arquivo] = {
            "titulo": corpo["properties"]["title"], "dono": token.usuario, "modificado": "2026-10-15T12:00:00.000Z",
            "abas": {"Sheet1": linhas},
        }
        return resposta_json({
            "spreadsheetId": id_arquivo, "spreadsheetUrl": f"https://docs.example/spreadsheets/d/{id_arquivo}/edit",
            "properties": {"title": corpo["properties"]["title"]},
        })

    # Docs
    def _documento(self, pedido):
        erro, token = self.autenticar(
            pedido, {AUTH + "documents.readonly", AUTH + "documents", AUTH + "drive.readonly", AUTH + "drive"}
        )
        if erro:
            return erro
        documento = self.documentos.get(pedido.rota.rsplit("/", 1)[1])
        if documento is None or documento["dono"] != token.usuario:
            return resposta_json({"error": {"code": 404, "message": "Requested entity was not found."}}, 404)
        conteudo = [{"paragraph": {"elements": [{"textRun": {"content": texto}}]}} for texto in documento["paragrafos"]]
        conteudo.append({"table": {"tableRows": [{"tableCells": _celulas_do_docs(l)} for l in documento["tabela"]]}})
        return resposta_json({"title": documento["titulo"], "body": {"content": conteudo}})

    def evento(self, usuario, titulo, inicio, fim, **extra):
        """Um evento do Google (início e fim "AAAA-MM-DDTHH:MM:SS-03:00"). Dia inteiro: datas AAAA-MM-DD."""
        chave = "date" if len(inicio) == 10 else "dateTime"
        self.contador += 1
        item = {"id": f"evento{self.contador}", "summary": titulo, "start": {chave: inicio}, "end": {chave: fim},
                "status": "confirmed", **extra}
        self.eventos.setdefault(usuario, []).append(item)
        return item


def _celulas_do_docs(linha):
    return [{"content": [{"paragraph": {"elements": [{"textRun": {"content": c + "\n"}}]}}]} for c in linha]


def _inicio_do_evento(evento):
    inicio = evento["start"].get("dateTime") or evento["start"]["date"] + "T00:00:00-03:00"
    return datetime.fromisoformat(inicio)


def ambiente_do_google(servidor, **extra):
    return {
        "GOOGLE_MODO": "real", "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID, "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        "GOOGLE_REDIRECT_URI": GOOGLE_REDIRECT_URI, "GOOGLE_URL": servidor.url, "ESCRITORIO_DOMINIOS": DOMINIOS, **extra,
    }

