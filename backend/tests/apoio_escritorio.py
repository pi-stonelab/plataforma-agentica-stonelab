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
from datetime import UTC, datetime
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



# --- Microsoft ---------------------------------------------------------------------------------------------------------

GRAPH = "https://graph.microsoft.com/"
LEITURA_DE_ARQUIVOS = {"Files.Read", "Files.ReadWrite", "Files.Read.All", "Files.ReadWrite.All"}
ESCRITA_DE_ARQUIVOS = {"Files.ReadWrite", "Files.ReadWrite.All"}
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_de_teste(paragrafos, tabela=()):
    """Um .docx mínimo, montado na mão (sem biblioteca), com parágrafos e uma tabela."""
    import io
    import zipfile
    from xml.sax.saxutils import escape

    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    corpo = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragrafos)
    if tabela:
        corpo += "<w:tbl>" + "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(c)}</w:t></w:r></w:p></w:tc>" for c in linha) + "</w:tr>"
            for linha in tabela
        ) + "</w:tbl>"
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        pacote.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{corpo}</w:body></w:document>')
    return saida.getvalue()


def _colunas_do_endereco(coluna):
    indice = 0
    for letra in coluna:
        indice = indice * 26 + ord(letra) - 64
    return indice


class MicrosoftDeTeste(ServicoOAuthDeTeste):
    """Um Microsoft Graph em memória: agenda, OneDrive e pastas de trabalho do Excel de cada pessoa."""

    def __init__(self):
        super().__init__(MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_REDIRECT_URI, "EwB")
        self.renova_o_refresh_token = True  # a Microsoft troca o token de renovação a cada uso
        self.eventos = {}
        self.itens = {
            "01PLANILHAAAA": {
                "nome": "Acompanhamento de testes.xlsx", "tipo": MIME_XLSX, "dono": "F0001", "modificado": "2026-10-14T09:00:00Z",
                "abas": {
                    "Resumo": [["Semana", "Abertos", "Fechados"], ["28/09", "10", "8"], ["05/10", "12", "11"]],
                    "Outra aba": [["Fila", "Total"], ["Recebimento", "7"]],
                    "Vazia": [],
                },
            },
            "01DOCUMENTOAA": {
                "nome": "Guia de testes.docx", "tipo": MIME_DOCX, "dono": "F0001", "modificado": "2026-10-13T10:00:00Z",
                "docx": docx_de_teste(["Primeiro parágrafo do guia.", "Segundo parágrafo, com mais texto."], [["Passo", "Quem"], ["Abrir", "Ana"]]),
            },
            "01PASTAAAAAAA": {"nome": "Relatórios de teste", "tipo": None, "dono": "F0001", "modificado": "2026-10-01T10:00:00Z"},
        }
        self.formatos = {}  # (id, aba, linha, coluna) -> formato de número que o teste aplicou
        self.url_de_download = None  # o outro servidor, que entrega o conteúdo do arquivo
        self.downloads = {}
        self.versao_do_link = 0

    def erro_de_credencial(self):
        erro = {"code": "InvalidAuthenticationToken", "message": "Access token has expired or is not yet valid."}
        return resposta_json({"error": erro}, 401)

    def erro_de_escopo(self):
        return resposta_json({"error": {"code": "Authorization_RequestDenied", "message": "Insufficient privileges."}}, 403)

    def erro_sem_acesso(self):
        return resposta_json({"error": {"code": "accessDenied", "message": "Access denied."}}, 403)

    def erro_de_limite(self):
        return resposta_json({"error": {"code": "activityLimitReached", "message": "Throttled."}}, 429, {"Retry-After": "9"})

    def _nao_achou(self):
        return resposta_json({"error": {"code": "itemNotFound", "message": "The resource could not be found."}}, 404)

    def _token(self, acesso, renovacao, escopos):
        dados = super()._token(acesso, renovacao, escopos)
        dados["scope"] = " ".join(sorted(GRAPH + e for e in escopos if e != "offline_access"))
        return dados

    def __call__(self, pedido):
        rota = unquote(pedido.rota)
        if rota.endswith("/oauth2/v2.0/token"):
            return self.endereco_de_token(pedido)
        forcada = self.forcada()
        if forcada is not None:
            return forcada
        if rota == "/v1.0/me/calendarView" or rota == "/v1.0/me/events":
            return self._agenda(pedido)
        if rota.startswith("/v1.0/me/drive/"):
            return self._drive(pedido, rota[len("/v1.0/me/drive/"):])
        return self._nao_achou()

    # Outlook
    def _agenda(self, pedido):
        escrita = pedido.metodo == "POST"
        erro, token = self.autenticar(pedido, {"Calendars.ReadWrite"} if escrita else {"Calendars.Read", "Calendars.ReadWrite"})
        if erro:
            return erro
        eventos = self.eventos.setdefault(token.usuario, [])
        if escrita:
            corpo = pedido.corpo
            existente = next((e for e in eventos if e.get("transactionId") == corpo.get("transactionId")), None)
            if existente is None:
                eventos.append({**corpo, "id": f"AAMk{len(eventos)}", "isAllDay": False, "isCancelled": False})
                existente = eventos[-1]
            return resposta_json(existente, 201)
        assert pedido.cabecalhos.get("prefer") == 'outlook.timezone="UTC"'
        consulta = pedido.consulta
        minimo = datetime.fromisoformat(consulta["startDateTime"]).astimezone(UTC).replace(tzinfo=None)
        maximo = datetime.fromisoformat(consulta["endDateTime"]).astimezone(UTC).replace(tzinfo=None)
        dentro = [e for e in eventos if minimo <= _inicio_graph(e) < maximo]
        dentro.sort(key=_inicio_graph)
        return resposta_json({"value": dentro[: int(consulta["$top"])]})

    def evento(self, usuario, titulo, inicio, fim, **extra):
        """Um evento do Graph. `inicio` e `fim` em UTC ("AAAA-MM-DDTHH:MM:SS"); `dia_inteiro=True`: meia-noite em UTC."""
        dia_inteiro = extra.pop("dia_inteiro", False)
        self.contador += 1
        item = {
            "id": f"AAMk{self.contador}", "subject": titulo, "isAllDay": dia_inteiro, "isCancelled": False,
            "start": {"dateTime": inicio + ".0000000", "timeZone": "UTC"},
            "end": {"dateTime": fim + ".0000000", "timeZone": "UTC"}, **extra,
        }
        self.eventos.setdefault(usuario, []).append(item)
        return item

    # OneDrive e Excel
    def _drive(self, pedido, caminho):
        escrita = pedido.metodo != "GET"
        erro, token = self.autenticar(pedido, ESCRITA_DE_ARQUIVOS if escrita else LEITURA_DE_ARQUIVOS)
        if erro:
            return erro
        if caminho.startswith("root/search("):
            return self._buscar(token, re.fullmatch(r"root/search\(q='(.*)'\)", caminho).group(1).replace("''", "'"))
        if caminho.startswith("root:/"):
            return self._criar_arquivo(token, pedido, caminho)
        partes = caminho.split("/")
        if partes[0] != "items":
            return self._nao_achou()
        item = self.itens.get(partes[1])
        if item is None or item["dono"] != token.usuario:
            return self._nao_achou()
        if len(partes) == 2:
            return resposta_json(self._descrever(partes[1], item))
        if partes[2] == "content":
            self.versao_do_link += 1
            return 302, {"Location": f"{self.url_de_download}/baixar/{partes[1]}/{self.versao_do_link}"}, b""
        if partes[2] == "workbook" and item["tipo"] == MIME_XLSX:
            return self._pasta_de_trabalho(pedido, partes[1], item, partes[3:])
        return self._nao_achou()

    def _descrever(self, id_item, item):
        dados = {"id": id_item, "name": item["nome"], "lastModifiedDateTime": item["modificado"], "size": len(item.get("docx", b"")) or 5000}
        if item["tipo"] is None:
            dados["folder"] = {"childCount": 0}
        else:
            dados["file"] = {"mimeType": item["tipo"]}
        return dados

    def _buscar(self, token, texto):
        achados = [
            self._descrever(id_item, item) for id_item, item in self.itens.items()
            if item["dono"] == token.usuario and texto.lower() in item["nome"].lower()
        ]
        return resposta_json({"value": achados})

    def _criar_arquivo(self, token, pedido, caminho):
        assert pedido.metodo == "PUT" and caminho.endswith(":/content")
        assert pedido.consulta["@microsoft.graph.conflictBehavior"] == "rename"
        assert pedido.cabecalhos["content-type"] == MIME_XLSX
        from ferramentas.integracoes.formatos import ler_xlsx

        nome = caminho[len("root:/"):-len(":/content")]
        while any(i["nome"] == nome and i["dono"] == token.usuario for i in self.itens.values()):
            nome = nome.replace(".xlsx", " 1.xlsx")  # `conflictBehavior=rename`
        lido = ler_xlsx(pedido.bruto, limite_linhas=1000)
        self.contador += 1
        id_item = f"01NOVO{self.contador:06d}"
        self.itens[id_item] = {
            "nome": nome, "tipo": MIME_XLSX, "dono": token.usuario, "modificado": "2026-10-15T12:00:00Z",
            "abas": {lido["aba"]: lido["linhas"]},
        }
        return resposta_json({**self._descrever(id_item, self.itens[id_item]), "webUrl": f"https://onedrive.example/{id_item}"}, 201)

    def _pasta_de_trabalho(self, pedido, id_item, item, partes):
        if partes == ["worksheets"]:
            return resposta_json({"value": [{"name": nome, "position": i} for i, nome in enumerate(item["abas"])]})
        aba = partes[1]
        if aba not in item["abas"]:
            return self._nao_achou()
        linhas = item["abas"][aba]
        funcao = partes[2]
        if funcao.startswith("usedRange"):
            return self._area_usada(aba, linhas)
        endereco = re.fullmatch(r"range\(address='([A-Z$0-9:]+)'\)", funcao).group(1).replace("$", "")
        inicio, _, fim = endereco.partition(":")
        fim = fim or inicio
        coluna_a, linha_a = re.fullmatch(r"([A-Z]+)(\d+)", inicio).groups()
        coluna_b, linha_b = re.fullmatch(r"([A-Z]+)(\d+)", fim).groups()
        primeira, ultima = _colunas_do_endereco(coluna_a), _colunas_do_endereco(coluna_b)
        if pedido.metodo == "PATCH":
            return self._gravar(pedido, id_item, linhas, aba, endereco, int(linha_a), primeira, ultima)
        recorte = [
            [str(c) for c in (linhas[n - 1] if n <= len(linhas) else [])[primeira - 1 : ultima]]
            for n in range(int(linha_a), int(linha_b) + 1)
        ]
        largura = ultima - primeira + 1
        return resposta_json({"text": [linha + [""] * (largura - len(linha)) for linha in recorte]})

    def _area_usada(self, aba, linhas):
        if not any(any(c != "" for c in linha) for linha in linhas):
            return resposta_json({"address": f"{aba}!A1", "rowCount": 1, "columnCount": 1})
        ultima = max(n for n, linha in enumerate(linhas, 1) if any(c != "" for c in linha))
        largura = max(len(linha) for linha in linhas)
        return resposta_json({"address": f"{aba}!A1:{_letra(largura)}{ultima}", "rowCount": ultima, "columnCount": largura})

    def _gravar(self, pedido, id_item, linhas, aba, endereco, numero, primeira, ultima):
        corpo = pedido.corpo
        if "numberFormat" in corpo:
            for coluna, formato in enumerate(corpo["numberFormat"][0], start=primeira):
                self.formatos[(id_item, aba, numero, coluna)] = formato
        if "values" in corpo:
            while len(linhas) < numero:
                linhas.append([])
            linha = []
            for coluna, valor in enumerate(corpo["values"][0], start=primeira):
                if isinstance(valor, str) and valor.startswith("'"):  # o apóstrofo do Excel marca texto e não fica na célula
                    valor = valor[1:]
                elif isinstance(valor, str) and re.fullmatch(r"\d{1,2}/\d{1,2}", valor) and self.formatos.get((id_item, aba, numero, coluna)) != "@":
                    valor = "45000"  # o Excel leria "12/10" como data
                linha.append(valor)
            linhas[numero - 1] = linha
        return resposta_json({"address": f"{aba}!{endereco}"})


def _letra(indice):
    letras = ""
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _inicio_graph(evento):
    return datetime.fromisoformat(evento["start"]["dateTime"].split(".")[0])


class DownloadDeTeste:
    """O servidor de download temporário (outro endereço), que nunca deve receber o token da pessoa."""

    def __init__(self, graph):
        self.graph = graph

    def __call__(self, pedido):
        partes = pedido.rota.split("/")
        item = self.graph.itens.get(partes[2]) if len(partes) > 3 and partes[1] == "baixar" else None
        if item is None or "docx" not in item:
            return 404, {}, b""
        return 200, {"Content-Type": MIME_DOCX}, item["docx"]


def ambiente_da_microsoft(servidor, **extra):
    return {
        "MICROSOFT_MODO": "real", "MICROSOFT_CLIENT_ID": MICROSOFT_CLIENT_ID, "MICROSOFT_CLIENT_SECRET": MICROSOFT_CLIENT_SECRET,
        "MICROSOFT_TENANT": MICROSOFT_TENANT, "MICROSOFT_REDIRECT_URI": MICROSOFT_REDIRECT_URI,
        "MICROSOFT_URL": servidor.url, "ESCRITORIO_DOMINIOS": DOMINIOS, **extra,
    }
