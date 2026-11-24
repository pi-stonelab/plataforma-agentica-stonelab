"""Google Workspace: agenda, planilhas, documentos e arquivos da conta Google de cada pessoa (OAuth2).

Configuração (.env): `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` (o app OAuth do tipo "aplicativo da Web", criado no
Console do Google Cloud do domínio, com as APIs Calendar, Sheets, Docs e Drive ligadas), `GOOGLE_REDIRECT_URI` (o
endereço da rota de retorno do back-end, que também está cadastrado no app) e `ESCRITORIO_DOMINIOS` (domínios que
podem receber convite de evento, como `stone.com.br`; vazio: ninguém). Preencher o `GOOGLE_CLIENT_ID` liga a
integração; `GOOGLE_MODO` força `real`, `simulado` ou `desligado`. `GOOGLE_URL` só existe para os testes (um servidor
local no lugar de todos os endereços do Google).

Escopos mínimos (a pessoa só concede o que a ferramenta usa; escrita só pedida à parte):
- leitura: `calendar.events.readonly` (eventos), `spreadsheets.readonly` (planilhas), `documents.readonly` (documentos)
  e `drive.metadata.readonly` (só nome, tipo e data dos arquivos: a busca é por nome, nunca pelo conteúdo);
- escrita: `calendar.events` (criar evento) e `spreadsheets` (criar planilha e adicionar linha).

Pedidos (documentação oficial: https://developers.google.com/calendar/api/v3/reference/events,
https://developers.google.com/sheets/api/reference/rest, https://developers.google.com/docs/api/reference/rest/v1/documents e
https://developers.google.com/drive/api/reference/rest/v3/files):
- GET  calendar/v3/calendars/primary/events?timeMin&timeMax&singleEvents&orderBy&maxResults&timeZone&fields
- POST calendar/v3/calendars/primary/events?sendUpdates=all   {id, summary, start, end, attendees...}   → 200
  O `id` é nosso (hexadecimal): se o pedido se repetir, o Google responde 409 e nada é duplicado.
- GET  drive/v3/files?q=name contains '...' and trashed=false&orderBy=modifiedTime desc&fields=files(...)
- GET  v4/spreadsheets/{id}?fields=properties.title,sheets.properties(...)        (título e abas)
- GET  v4/spreadsheets/{id}/values/{aba}!A1:F20                                   (valores, como aparecem na tela)
- POST v4/spreadsheets/{id}/values/{aba}!A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS
  `RAW`: o que a pessoa (ou o modelo) escreveu fica como texto, nunca vira fórmula (`=IMPORTXML(...)` não executa).
- POST v4/spreadsheets   {properties, sheets[].data[].rowData}                    (planilha nova, valores como texto ou número)
- GET  v1/documents/{id}?fields=title,body(content(...))                          (texto do documento)
- 403 do Google também significa limite de pedidos (`rateLimitExceeded`), falta de permissão (`ACCESS_TOKEN_SCOPE_INSUFFICIENT`)
  e item sem acesso (`forbidden`): `classificar_recusa` separa as três.
"""

import os
import re
from datetime import datetime, time, timedelta

from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import cliente_http
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida, montar_url
from ferramentas.integracoes.conector import ConfiguracaoInvalida, ler_lista
from ferramentas.integracoes.escritorio import (
    FUSO,
    MENSAGEM_NAO_ENCONTRADO,
    PADRAO_DOMINIO,
    ConectorDeEscritorio,
    horario_local,
    limitar_intervalo,
    texto_da_celula,
    valor_da_celula,
)
from ferramentas.integracoes.oauth import ConfiguracaoOAuth
from ferramentas.integracoes.registro import registrar

AUTH = "https://www.googleapis.com/auth/"
CALENDARIO_LEITURA = AUTH + "calendar.events.readonly"
CALENDARIO_ESCRITA = AUTH + "calendar.events"
PLANILHAS_LEITURA = AUTH + "spreadsheets.readonly"
PLANILHAS_ESCRITA = AUTH + "spreadsheets"
DOCUMENTOS_LEITURA = AUTH + "documents.readonly"
ARQUIVOS_LEITURA = AUTH + "drive.metadata.readonly"
ESCOPOS_DE_LEITURA = frozenset({CALENDARIO_LEITURA, PLANILHAS_LEITURA, DOCUMENTOS_LEITURA, ARQUIVOS_LEITURA})
ESCOPOS_DE_ESCRITA = frozenset({CALENDARIO_ESCRITA, PLANILHAS_ESCRITA})
# Escopos maiores que a pessoa pode ter concedido antes (por outro app do mesmo cliente) e que já cobrem o mínimo.
MAIS_AMPLOS = {
    CALENDARIO_LEITURA: (CALENDARIO_ESCRITA, AUTH + "calendar.readonly", AUTH + "calendar"),
    PLANILHAS_LEITURA: (PLANILHAS_ESCRITA, AUTH + "drive.readonly", AUTH + "drive"),
    DOCUMENTOS_LEITURA: (AUTH + "documents", AUTH + "drive.readonly", AUTH + "drive"),
    ARQUIVOS_LEITURA: (AUTH + "drive.metadata", AUTH + "drive.readonly", AUTH + "drive"),
    CALENDARIO_ESCRITA: (AUTH + "calendar",),
    PLANILHAS_ESCRITA: (AUTH + "drive",),
}
PADRAO_CLIENT_ID = re.compile(r"[0-9]{6,20}-[a-z0-9]{8,40}\.apps\.googleusercontent\.com")
PADRAO_SEGREDO = re.compile(r"[A-Za-z0-9_-]{10,120}")
HOSTS = {
    "auth": "https://accounts.google.com/o/oauth2/v2/auth",
    "token": "https://oauth2.googleapis.com/token",
    "revoke": "https://oauth2.googleapis.com/revoke",
    "calendar": "https://www.googleapis.com/calendar/v3",
    "drive": "https://www.googleapis.com/drive/v3",
    "sheets": "https://sheets.googleapis.com/v4/spreadsheets",
    "docs": "https://docs.googleapis.com/v1/documents",
}
CAMINHOS_DE_TESTE = {  # com `GOOGLE_URL` (testes), os mesmos caminhos saem de um servidor só
    "auth": "/o/oauth2/v2/auth", "token": "/token", "revoke": "/revoke", "calendar": "/calendar/v3",
    "drive": "/drive/v3", "sheets": "/v4/spreadsheets", "docs": "/v1/documents",
}
TIPOS_DO_DRIVE = {
    "application/vnd.google-apps.spreadsheet": "planilha",
    "application/vnd.google-apps.document": "documento",
    "application/vnd.google-apps.folder": "pasta",
}
MIME_POR_TIPO = {
    "planilha": "application/vnd.google-apps.spreadsheet",
    "documento": "application/vnd.google-apps.document",
}
LIMITE_DE_RESPOSTA_DO_DOCUMENTO = 2_000_000  # bytes: um documento longo cabe; o teto geral é de 1 MB
MOTIVOS_DE_LIMITE = frozenset({"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "dailyLimitExceeded"})
MOTIVOS_DE_ESCOPO = frozenset({"ACCESS_TOKEN_SCOPE_INSUFFICIENT"})
MOTIVOS_DE_PLATAFORMA = frozenset({"accessNotConfigured", "SERVICE_DISABLED", "API_KEY_SERVICE_BLOCKED"})
CAMPOS_DO_DOCUMENTO = "title,body(content(paragraph(elements(textRun(content))),table(tableRows(tableCells(content(paragraph(elements(textRun(content)))))))))"


def _motivos(recusa):
    """Os motivos que o Google escreveu numa recusa (`errors[].reason`, `details[].reason` e `status`)."""
    erro = recusa.dados.get("error") if isinstance(recusa.dados, dict) else None
    if not isinstance(erro, dict):
        return set()
    motivos = {item.get("reason") for item in erro.get("errors", ()) if isinstance(item, dict)}
    motivos |= {item.get("reason") for item in erro.get("details", ()) if isinstance(item, dict)}
    motivos.add(erro.get("status"))
    return {m for m in motivos if isinstance(m, str)}


def _escapar_na_busca(texto):
    """Dentro das aspas simples do `q` do Drive, a barra invertida e a aspa simples precisam de barra na frente."""
    return texto.replace("\\", "\\\\").replace("'", "\\'")


def _aba_no_intervalo(aba):
    return "'" + aba.replace("'", "''") + "'"


def _texto_dos_elementos(paragrafo):
    elementos = paragrafo.get("elements", ()) if isinstance(paragrafo, dict) else ()
    return "".join(
        item["textRun"].get("content", "") for item in elementos if isinstance(item, dict) and isinstance(item.get("textRun"), dict)
    )


def _texto_do_conteudo(conteudo, limite):
    """O texto de `body.content` do Docs: parágrafos e as células das tabelas (separadas por tabulação), até `limite`."""
    partes = []
    tamanho = 0
    for bloco in conteudo if isinstance(conteudo, list) else ():
        if not isinstance(bloco, dict):
            continue
        if "paragraph" in bloco:
            partes.append(_texto_dos_elementos(bloco["paragraph"]))
        elif isinstance(bloco.get("table"), dict):
            for linha in bloco["table"].get("tableRows", ()):
                celulas = linha.get("tableCells", ()) if isinstance(linha, dict) else ()
                partes.append("\t".join(_texto_da_celula(c) for c in celulas) + "\n")
        tamanho += len(partes[-1]) if partes else 0
        if tamanho > limite:
            break
    return "".join(partes)


def _texto_da_celula(celula):
    blocos = celula.get("content", ()) if isinstance(celula, dict) else ()
    return " ".join(
        _texto_dos_elementos(b["paragraph"]).strip() for b in blocos if isinstance(b, dict) and "paragraph" in b
    ).strip()


def _celula_nova(texto):
    valor = valor_da_celula(texto)
    return {"userEnteredValue": {"stringValue" if isinstance(valor, str) else "numberValue": valor}}


class ConectorGoogleWorkspace(ConectorDeEscritorio):
    nome = "google_workspace"
    rotulo = "Google Workspace"
    variavel_modo = "GOOGLE_MODO"
    variavel_que_liga = "GOOGLE_CLIENT_ID"
    variaveis = (
        "GOOGLE_MODO", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "GOOGLE_URL",
        "ESCRITORIO_DOMINIOS",
    )
    escopos_de_leitura = ESCOPOS_DE_LEITURA
    escopos_de_escrita = ESCOPOS_DE_ESCRITA
    mais_amplos = MAIS_AMPLOS
    fonte_real = "Google Workspace"
    fonte_simulada = "Google Workspace simulado (modo de demonstração): nada disto existe numa conta Google de verdade"
    mensagem_desligada = "A integração com o Google Workspace (agenda, planilhas e documentos) não está ligada nesta plataforma."
    como_ligar = "preencha GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e GOOGLE_REDIRECT_URI (ou use GOOGLE_MODO=simulado)"
    dica_sem_rede = "Confira a internet, ou use GOOGLE_MODO=simulado."
    dicas = {
        "GOOGLE_CLIENT_ID": (
            "GOOGLE_CLIENT_ID inválido: use o ID do cliente OAuth (termina em .apps.googleusercontent.com), do tipo"
            " aplicativo da Web (veja ferramentas/integracoes/google_workspace/README.md)."
        ),
        "GOOGLE_CLIENT_SECRET": "GOOGLE_CLIENT_SECRET inválido: use a chave secreta do mesmo cliente OAuth.",
        "GOOGLE_REDIRECT_URI": (
            "GOOGLE_REDIRECT_URI inválida: o endereço https da rota de retorno do back-end, igual ao cadastrado no"
            " cliente OAuth (sem parâmetros)."
        ),
        "GOOGLE_URL": "GOOGLE_URL inválida: deixe vazia (usa os endereços do Google).",
        "ESCRITORIO_DOMINIOS": "ESCRITORIO_DOMINIOS inválida: domínios separados por vírgula, como stone.com.br.",
    }

    def _urls(self, ambiente):
        base = (ambiente.get("GOOGLE_URL") or "").strip()
        if not base:
            return HOSTS
        raiz = cliente_http.url_base(base, "GOOGLE_URL")
        return {chave: raiz + caminho for chave, caminho in CAMINHOS_DE_TESTE.items()}

    def configuracao_oauth(self, ambiente):
        urls = self._urls(ambiente)
        client_id = ambiente.get("GOOGLE_CLIENT_ID", "").strip()
        segredo = ambiente.get("GOOGLE_CLIENT_SECRET", "").strip()
        if not PADRAO_CLIENT_ID.fullmatch(client_id):
            raise ConfiguracaoInvalida("GOOGLE_CLIENT_ID")
        if not PADRAO_SEGREDO.fullmatch(segredo):
            raise ConfiguracaoInvalida("GOOGLE_CLIENT_SECRET")
        redirect = cliente_http.url_base(ambiente.get("GOOGLE_REDIRECT_URI", ""), "GOOGLE_REDIRECT_URI")
        ler_lista(ambiente, "ESCRITORIO_DOMINIOS", PADRAO_DOMINIO)
        return ConfiguracaoOAuth(
            nome=self.nome,
            rotulo=self.rotulo,
            url_de_autorizacao=urls["auth"],
            url_do_token=urls["token"],
            client_id=client_id,
            redirect_uri=redirect,
            client_secret=segredo,
            url_de_revogacao=urls["revoke"],
            # offline: devolve o token de renovação; consent: devolve-o em toda autorização; include_granted_scopes:
            # a escrita pedida depois soma à leitura que a pessoa já tinha, em vez de trocar.
            parametros_da_autorizacao={"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"},
            mais_amplos=MAIS_AMPLOS,
            escopos_de_escrita=ESCOPOS_DE_ESCRITA,
        )

    def conferir_configuracao(self, ambiente=os.environ):
        self.configuracao_oauth(ambiente)

    def classificar_recusa(self, recusa):
        if recusa.status == 401:
            return "conta"
        motivos = _motivos(recusa)
        if motivos & MOTIVOS_DE_LIMITE:
            return "limite"
        if motivos & MOTIVOS_DE_ESCOPO:
            return "escopo"
        if motivos & MOTIVOS_DE_PLATAFORMA:
            return "plataforma"
        return "acesso"

    # --- chamadas ------------------------------------------------------------------------------------------------

    def _chamar_api(self, ambiente, id_usuario, servico, escopos, metodo, url, **pedido):
        """O pedido com o token da pessoa; devolve o JSON. 404 vira `nao_encontrado`; resposta que não é objeto, inválida."""
        resposta = self._pedir_da_pessoa(ambiente, id_usuario, servico, escopos, metodo, url, **pedido)
        if resposta.status == 404:
            raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)
        if not isinstance(resposta.dados, dict):
            raise RespostaInvalida("resposta fora do formato")
        return resposta.dados

    def eventos_real(self, ambiente, id_usuario, data_inicio, data_fim, limite):
        url = montar_url(self._urls(ambiente)["calendar"], "calendars", "primary", "events")
        parametros = {
            "timeMin": datetime.combine(data_inicio, time.min, FUSO).isoformat(),
            "timeMax": datetime.combine(data_fim + timedelta(days=1), time.min, FUSO).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": limite + 1,
            "timeZone": "America/Sao_Paulo",
            "fields": "items(summary,location,start,end,status,attendees(email))",
        }
        dados = self._chamar_api(
            ambiente, id_usuario, "agenda", {CALENDARIO_LEITURA}, "GET", url, parametros=parametros
        )
        itens = dados.get("items")
        if not isinstance(itens, list):
            raise RespostaInvalida("resposta fora do formato")
        eventos = [self._evento(item) for item in itens if isinstance(item, dict) and item.get("status") != "cancelled"]
        return eventos[:limite], len(eventos) > limite

    def _evento(self, item):
        inicio, fim = item.get("start"), item.get("end")
        if not isinstance(inicio, dict) or not isinstance(fim, dict):
            raise RespostaInvalida("resposta fora do formato")
        dia_inteiro = "date" in inicio
        try:
            marcas = (
                (inicio["date"], fim["date"]) if dia_inteiro
                else (horario_local(inicio["dateTime"]), horario_local(fim["dateTime"]))
            )
        except (KeyError, ValueError, TypeError):
            raise RespostaInvalida("resposta fora do formato") from None
        convidados = item.get("attendees")
        return {
            "titulo": str(item.get("summary") or "(sem título)")[:200],
            "inicio": marcas[0],
            "fim": marcas[1],
            "dia_inteiro": dia_inteiro,
            "local": str(item.get("location") or "")[:200],
            "convidados": len(convidados) if isinstance(convidados, list) else 0,
        }

    def criar_evento_real(self, ambiente, id_usuario, evento):
        url = montar_url(self._urls(ambiente)["calendar"], "calendars", "primary", "events")
        corpo = {
            "id": evento["id_unico"],
            "summary": evento["titulo"],
            "start": {"dateTime": evento["inicio"].replace(tzinfo=FUSO).isoformat(), "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": evento["fim"].replace(tzinfo=FUSO).isoformat(), "timeZone": "America/Sao_Paulo"},
            "reminders": {"useDefault": True},
        }
        if evento.get("local"):
            corpo["location"] = evento["local"]
        if evento.get("descricao"):
            corpo["description"] = evento["descricao"]
        if evento.get("convidados"):
            corpo["attendees"] = [{"email": email} for email in evento["convidados"]]
        try:
            self._chamar_api(
                ambiente, id_usuario, "agenda", {CALENDARIO_ESCRITA}, "POST", url,
                parametros={"sendUpdates": "all" if evento.get("convidados") else "none"}, corpo=corpo,
            )
        except PedidoRecusado as recusa:
            if recusa.status != 409:  # 409: o `id` já existe, ou seja, este mesmo pedido já tinha sido criado
                raise
        return {
            "titulo": evento["titulo"],
            "inicio": evento["inicio"].isoformat(timespec="minutes"),
            "fim": evento["fim"].isoformat(timespec="minutes"),
        }

    def arquivos_real(self, ambiente, id_usuario, consulta, tipo, limite):
        filtros = ["trashed = false", f"name contains '{_escapar_na_busca(consulta)}'"]
        if tipo in MIME_POR_TIPO:
            filtros.append(f"mimeType = '{MIME_POR_TIPO[tipo]}'")
        parametros = {
            "q": " and ".join(filtros),
            "pageSize": limite,
            "orderBy": "modifiedTime desc",
            "fields": "files(id,name,mimeType,modifiedTime)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        url = montar_url(self._urls(ambiente)["drive"], "files")
        dados = self._chamar_api(
            ambiente, id_usuario, "arquivos", {ARQUIVOS_LEITURA}, "GET", url, parametros=parametros
        )
        itens = dados.get("files")
        if not isinstance(itens, list):
            raise RespostaInvalida("resposta fora do formato")
        return [
            {
                "id_arquivo": str(item.get("id", ""))[:128],
                "titulo": str(item.get("name") or "")[:200],
                "tipo": TIPOS_DO_DRIVE.get(item.get("mimeType"), "outro"),
                "modificado_em": str(item.get("modifiedTime") or "")[:10],
            }
            for item in itens[:limite]
            if isinstance(item, dict)
        ]

    def _planilha(self, ambiente, id_usuario, id_arquivo, escopo):
        url = montar_url(self._urls(ambiente)["sheets"], id_arquivo)
        parametros = {"fields": "properties.title,sheets.properties.title"}
        dados = self._chamar_api(ambiente, id_usuario, "planilhas", {escopo}, "GET", url, parametros=parametros)
        try:
            abas = [{"titulo": str(aba["properties"]["title"])[:100]} for aba in dados["sheets"]]
            return {"titulo": str(dados["properties"]["title"])[:200], "abas": abas}
        except (KeyError, TypeError, ValueError):
            raise RespostaInvalida("resposta fora do formato") from None

    def descrever_planilha_real(self, ambiente, id_usuario, id_arquivo):
        return self._planilha(ambiente, id_usuario, id_arquivo, PLANILHAS_LEITURA)

    def _aba_existente(self, planilha, aba):
        titulos = [a["titulo"] for a in planilha["abas"]]
        if aba is None:
            return titulos[0]
        if aba not in titulos:
            raise ErroFerramenta("nao_encontrado", f"Aba não encontrada. Abas da planilha: {', '.join(titulos)}.")
        return aba

    def ler_planilha_real(self, ambiente, id_usuario, id_arquivo, aba, intervalo, limite):
        planilha = self._planilha(ambiente, id_usuario, id_arquivo, PLANILHAS_LEITURA)
        aba = self._aba_existente(planilha, aba)
        recorte = limitar_intervalo(intervalo, limite) if intervalo else f"A1:Z{limite + 1}"
        url = montar_url(
            self._urls(ambiente)["sheets"], id_arquivo, "values", f"{_aba_no_intervalo(aba)}!{recorte}", seguros=":!'"
        )
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {PLANILHAS_LEITURA}, "GET", url,
            parametros={"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"},
        )
        valores = dados.get("values", [])
        if not isinstance(valores, list) or not all(isinstance(linha, list) for linha in valores):
            raise RespostaInvalida("resposta fora do formato")
        linhas = [[texto_da_celula(c) for c in linha] for linha in valores]
        return {"titulo": planilha["titulo"], "aba": aba, "intervalo": intervalo or "", "linhas": linhas[:limite],
                "truncado": len(linhas) > limite}

    def adicionar_linha_real(self, ambiente, id_usuario, id_arquivo, aba, valores):
        url = montar_url(
            self._urls(ambiente)["sheets"], id_arquivo, "values", f"{_aba_no_intervalo(aba)}!A1:append", seguros=":!'"
        )
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {PLANILHAS_ESCRITA}, "POST", url,
            parametros={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            corpo={"majorDimension": "ROWS", "values": [[valor_da_celula(v) for v in valores]]},
        )
        atualizacao = dados.get("updates")
        if not isinstance(atualizacao, dict) or atualizacao.get("updatedRows") != 1:
            raise RespostaInvalida("resposta fora do formato")
        return {"linhas_adicionadas": 1}

    def criar_planilha_real(self, ambiente, id_usuario, titulo, linhas):
        corpo = {
            "properties": {"title": titulo},
            "sheets": [{"data": [{"startRow": 0, "startColumn": 0, "rowData": [
                {"values": [_celula_nova(celula) for celula in linha]} for linha in linhas
            ]}]}],
        }
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {PLANILHAS_ESCRITA}, "POST", self._urls(ambiente)["sheets"], corpo=corpo
        )
        id_arquivo, link = dados.get("spreadsheetId"), dados.get("spreadsheetUrl")
        if not isinstance(id_arquivo, str) or not isinstance(link, str) or not link.startswith("https://"):
            raise RespostaInvalida("resposta fora do formato")
        return {"id_arquivo": id_arquivo, "titulo": titulo, "link": link}

    def documento_real(self, ambiente, id_usuario, id_arquivo, limite):
        url = montar_url(self._urls(ambiente)["docs"], id_arquivo)
        resposta = self._pedir_da_pessoa(
            ambiente, id_usuario, "documentos", {DOCUMENTOS_LEITURA}, "GET", url,
            parametros={"fields": CAMPOS_DO_DOCUMENTO}, limite_de_bytes=LIMITE_DE_RESPOSTA_DO_DOCUMENTO,
        )
        if resposta.status == 404:
            raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)
        dados = resposta.dados
        if not isinstance(dados, dict) or not isinstance(dados.get("title"), str):
            raise RespostaInvalida("resposta fora do formato")
        texto = _texto_do_conteudo((dados.get("body") or {}).get("content"), limite)
        return {"titulo": dados["title"][:200], "texto": texto[:limite], "truncado": len(texto) > limite}


CONECTOR = registrar(ConectorGoogleWorkspace())
