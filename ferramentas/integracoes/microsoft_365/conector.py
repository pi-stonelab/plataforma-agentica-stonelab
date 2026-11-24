"""Microsoft 365: agenda (Outlook), arquivos e planilhas (OneDrive e Excel) e documentos (Word) da conta de cada pessoa.

Configuração (.env): `MICROSOFT_CLIENT_ID` (o app registrado no Microsoft Entra ID, tipo "Web"), `MICROSOFT_CLIENT_SECRET`
(o valor do segredo do app; vazio só se o app foi registrado como cliente público), `MICROSOFT_TENANT` (o diretório da
Stone: GUID ou domínio; vazio: `organizations`), `MICROSOFT_REDIRECT_URI` (o endereço da rota de retorno do back-end,
igual ao cadastrado no app) e `ESCRITORIO_DOMINIOS` (domínios que podem receber convite de evento; vazio: ninguém).
Preencher o `MICROSOFT_CLIENT_ID` liga a integração; `MICROSOFT_MODO` força `real`, `simulado` ou `desligado`.
`MICROSOFT_URL` só existe para os testes (um servidor local no lugar do login e do Graph).

Permissões delegadas (a pessoa só concede o que a ferramenta usa; escrita só pedida à parte):
- leitura: `Calendars.Read` (eventos) e `Files.Read` (buscar arquivos, ler planilha Excel e ler documento Word);
- escrita: `Calendars.ReadWrite` (criar evento) e `Files.ReadWrite` (criar planilha e adicionar linha);
- `offline_access`, sempre: sem ele a Microsoft não devolve o token de renovação.
Nenhuma permissão `.All`: o app só enxerga o que a própria pessoa enxerga.

Pedidos (Microsoft Graph v1.0; https://learn.microsoft.com/graph/api/resources/event e /resources/excel):
- GET   me/calendarView?startDateTime&endDateTime&$select&$orderby&$top      com `Prefer: outlook.timezone="UTC"`
- POST  me/events   {subject, start, end, attendees, transactionId...}       → 201
  O `transactionId` é nosso: se o pedido se repetir, a Microsoft não duplica o evento.
- GET   me/drive/root/search(q='texto')?$select&$top                         (nome, e também o conteúdo)
- GET   me/drive/items/{id}?$select=name,file                                (nome e tipo, antes de abrir)
- GET   me/drive/items/{id}/workbook/worksheets                              (as abas)
- GET   me/drive/items/{id}/workbook/worksheets/{aba}/range(address='A1:F20')?$select=text
- GET   .../worksheets/{aba}/usedRange(valuesOnly=true)?$select=address,rowCount,columnCount
- PATCH .../worksheets/{aba}/range(address='A9:C9')   {numberFormat} e {values}   (linha nova)
- PUT   me/drive/root:/{nome}.xlsx:/content?@microsoft.graph.conflictBehavior=rename   (planilha nova; nunca sobrescreve)
- GET   me/drive/items/{id}/content   → 302 para o endereço de download em outro domínio (sharepoint.com, 1drv.com);
  o redirecionamento é seguido sem o token e só para esses domínios; o `.docx` é lido por `formatos.ler_docx`.
- 403 do Graph: `classificar_recusa` separa permissão do app, item sem acesso e limite de pedidos.
- A Microsoft não tem endereço de revogação do token de renovação: "desligar" apaga a conta daqui, e a pessoa revoga o
  app em myaccount.microsoft.com se quiser tirar o consentimento.

Não foi possível testar contra o serviço de verdade nesta etapa (sem conta nem app registrado, e só dados sintéticos): o
`python -m ferramentas.integracoes testar microsoft_365` confere o app do .env e o README diz o que o Pedro deve conferir.
"""

import os
import re
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlsplit

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http, formatos
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida, montar_url
from ferramentas.integracoes.conector import ConfiguracaoInvalida, ler_lista
from ferramentas.integracoes.escritorio import (
    FUSO,
    MENSAGEM_NAO_ENCONTRADO,
    PADRAO_DOMINIO,
    ConectorDeEscritorio,
    horario_local,
    limitar_intervalo,
    valor_da_celula,
)
from ferramentas.integracoes.oauth import ConfiguracaoOAuth
from ferramentas.integracoes.registro import registrar

PREFIXO_DOS_ESCOPOS = "https://graph.microsoft.com/"
CALENDARIO_LEITURA = "Calendars.Read"
CALENDARIO_ESCRITA = "Calendars.ReadWrite"
ARQUIVOS_LEITURA = "Files.Read"
ARQUIVOS_ESCRITA = "Files.ReadWrite"
ESCOPOS_DE_LEITURA = frozenset({CALENDARIO_LEITURA, ARQUIVOS_LEITURA})
ESCOPOS_DE_ESCRITA = frozenset({CALENDARIO_ESCRITA, ARQUIVOS_ESCRITA})
ESCOPOS_SEMPRE = ("offline_access",)
MAIS_AMPLOS = {
    CALENDARIO_LEITURA: (CALENDARIO_ESCRITA,),
    ARQUIVOS_LEITURA: (ARQUIVOS_ESCRITA, "Files.Read.All", "Files.ReadWrite.All"),
    ARQUIVOS_ESCRITA: ("Files.ReadWrite.All",),
}
PADRAO_CLIENT_ID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
PADRAO_SEGREDO = re.compile(r"[A-Za-z0-9_.~-]{8,120}")
PADRAO_TENANT = re.compile(PADRAO_CLIENT_ID.pattern + "|organizations|common|consumers|" + PADRAO_DOMINIO.pattern)
TENANT_PADRAO = "organizations"
HOSTS = {
    "login": "https://login.microsoftonline.com",
    "graph": "https://graph.microsoft.com/v1.0",
}
CAMINHOS_DE_TESTE = {"login": "", "graph": "/v1.0"}  # com `MICROSOFT_URL` (testes), tudo sai de um servidor só
DOMINIOS_DE_DOWNLOAD = ("sharepoint.com", "1drv.com", "onedrive.live.com")
MIME_POR_TIPO = {"planilha": formatos.TIPO_XLSX, "documento": formatos.TIPO_DOCX}
TIPOS_DO_ONEDRIVE = {mime: tipo for tipo, mime in MIME_POR_TIPO.items()}
MOTIVOS_DE_LIMITE = frozenset({"activityLimitReached", "throttledRequest", "tooManyRequests", "quotaLimitReached"})
MOTIVOS_DE_ESCOPO = frozenset({"Authorization_RequestDenied", "InsufficientPermissions", "insufficientScope"})
PADRAO_ENDERECO_USADO = re.compile(r"(?:.*!)?\$?[A-Z]{1,3}\$?([0-9]{1,7})(?::\$?[A-Z]{1,3}\$?([0-9]{1,7}))?")
EXTENSAO_DO_ARQUIVO = re.compile(r"\.(xlsx|docx)$", re.IGNORECASE)
CARACTERES_PROIBIDOS_NO_NOME = re.compile(r'[\x00-\x1f"*:<>?/\\|#%~&{}]')
TAMANHO_DO_NOME_DO_ARQUIVO = 100
NOME_PADRAO_DO_ARQUIVO = "Planilha"
PADRAO_DE_FRACAO = re.compile(r"\.[0-9]+")


def _codigo_do_erro(recusa):
    erro = recusa.dados.get("error") if isinstance(recusa.dados, dict) else None
    codigo = erro.get("code") if isinstance(erro, dict) else None
    return codigo if isinstance(codigo, str) else ""


def _escapar_na_busca(texto):
    """Dentro das aspas simples de `search(q='...')` (OData), a aspa simples se escreve dobrada."""
    return texto.replace("'", "''")


def _sem_fracao(texto):
    """"2026-10-16T17:00:00.0000000" -> "2026-10-16T17:00:00" (a Microsoft devolve sete casas, o Python 3.11 não lê)."""
    return PADRAO_DE_FRACAO.sub("", texto, count=1)


def _momento(marca):
    """O `{dateTime, timeZone}` de um evento (sempre UTC, pelo cabeçalho `Prefer`) como horário de Brasília."""
    if not isinstance(marca, dict) or marca.get("timeZone") != "UTC":
        raise RespostaInvalida("resposta fora do formato")
    return horario_local(_sem_fracao(marca["dateTime"]), UTC)


def _em_utc(horario_de_brasilia):
    return horario_de_brasilia.replace(tzinfo=FUSO).astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def nome_do_arquivo(titulo):
    """O título como nome de arquivo do OneDrive: sem caracteres proibidos, sem ponto ou espaço nas pontas."""
    limpo = CARACTERES_PROIBIDOS_NO_NOME.sub(" ", titulo)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    return limpo[:TAMANHO_DO_NOME_DO_ARQUIVO].strip(" .") or NOME_PADRAO_DO_ARQUIVO


class ConectorMicrosoft365(ConectorDeEscritorio):
    nome = "microsoft_365"
    rotulo = "Microsoft 365"
    variavel_modo = "MICROSOFT_MODO"
    variavel_que_liga = "MICROSOFT_CLIENT_ID"
    variaveis = (
        "MICROSOFT_MODO", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_TENANT",
        "MICROSOFT_REDIRECT_URI", "MICROSOFT_URL", "ESCRITORIO_DOMINIOS",
    )
    escopos_de_leitura = ESCOPOS_DE_LEITURA
    escopos_de_escrita = ESCOPOS_DE_ESCRITA
    mais_amplos = MAIS_AMPLOS
    fonte_real = "Microsoft 365"
    fonte_simulada = "Microsoft 365 simulado (modo de demonstração): nada disto existe numa conta Microsoft de verdade"
    mensagem_desligada = "A integração com o Microsoft 365 (agenda, planilhas e documentos) não está ligada nesta plataforma."
    como_ligar = "preencha MICROSOFT_CLIENT_ID, MICROSOFT_TENANT e MICROSOFT_REDIRECT_URI (ou use MICROSOFT_MODO=simulado)"
    dica_sem_rede = "Confira a internet, ou use MICROSOFT_MODO=simulado."
    dicas = {
        "MICROSOFT_CLIENT_ID": (
            "MICROSOFT_CLIENT_ID inválido: use o ID do aplicativo (cliente), um GUID, do registro do app no Entra ID"
            " (veja ferramentas/integracoes/microsoft_365/README.md)."
        ),
        "MICROSOFT_CLIENT_SECRET": "MICROSOFT_CLIENT_SECRET inválido: use o VALOR do segredo do app (não o ID do segredo).",
        "MICROSOFT_TENANT": "MICROSOFT_TENANT inválido: o GUID do diretório, o domínio da empresa ou organizations.",
        "MICROSOFT_REDIRECT_URI": (
            "MICROSOFT_REDIRECT_URI inválida: o endereço https da rota de retorno do back-end, igual ao cadastrado no"
            " app (sem parâmetros)."
        ),
        "MICROSOFT_URL": "MICROSOFT_URL inválida: deixe vazia (usa os endereços da Microsoft).",
        "ESCRITORIO_DOMINIOS": "ESCRITORIO_DOMINIOS inválida: domínios separados por vírgula, como stone.com.br.",
    }

    def _urls(self, ambiente):
        base = (ambiente.get("MICROSOFT_URL") or "").strip()
        tenant = (ambiente.get("MICROSOFT_TENANT") or TENANT_PADRAO).strip()
        if not PADRAO_TENANT.fullmatch(tenant):
            raise ConfiguracaoInvalida("MICROSOFT_TENANT")
        if base:
            raiz = cliente_http.url_base(base, "MICROSOFT_URL")
            login, graph = raiz + CAMINHOS_DE_TESTE["login"], raiz + CAMINHOS_DE_TESTE["graph"]
        else:
            login, graph = f"{HOSTS['login']}/{tenant}", HOSTS["graph"]
        return {"auth": f"{login}/oauth2/v2.0/authorize", "token": f"{login}/oauth2/v2.0/token", "graph": graph}

    def _dominios_de_download(self, ambiente):
        base = (ambiente.get("MICROSOFT_URL") or "").strip()
        if base:  # nos testes o "download" é o mesmo servidor local, em outra porta
            return (urlsplit(cliente_http.url_base(base, "MICROSOFT_URL")).hostname,)
        return DOMINIOS_DE_DOWNLOAD

    def configuracao_oauth(self, ambiente):
        urls = self._urls(ambiente)
        client_id = ambiente.get("MICROSOFT_CLIENT_ID", "").strip()
        segredo = ambiente.get("MICROSOFT_CLIENT_SECRET", "").strip()
        if not PADRAO_CLIENT_ID.fullmatch(client_id):
            raise ConfiguracaoInvalida("MICROSOFT_CLIENT_ID")
        if segredo and not PADRAO_SEGREDO.fullmatch(segredo):
            raise ConfiguracaoInvalida("MICROSOFT_CLIENT_SECRET")
        redirect = cliente_http.url_base(ambiente.get("MICROSOFT_REDIRECT_URI", ""), "MICROSOFT_REDIRECT_URI")
        ler_lista(ambiente, "ESCRITORIO_DOMINIOS", PADRAO_DOMINIO)
        return ConfiguracaoOAuth(
            nome=self.nome,
            rotulo=self.rotulo,
            url_de_autorizacao=urls["auth"],
            url_do_token=urls["token"],
            client_id=client_id,
            redirect_uri=redirect,
            client_secret=segredo,
            # select_account: a pessoa escolhe a conta, em vez de a Microsoft usar a que estiver aberta no navegador.
            parametros_da_autorizacao={"response_mode": "query", "prompt": "select_account"},
            escopos_sempre=ESCOPOS_SEMPRE,
            mais_amplos=MAIS_AMPLOS,
            escopos_de_escrita=ESCOPOS_DE_ESCRITA,
            prefixo_dos_escopos=PREFIXO_DOS_ESCOPOS,
        )

    def conferir_configuracao(self, ambiente=os.environ):
        self.configuracao_oauth(ambiente)

    def classificar_recusa(self, recusa):
        if recusa.status == 401:
            return "conta"
        codigo = _codigo_do_erro(recusa)
        if codigo in MOTIVOS_DE_LIMITE:
            return "limite"
        if codigo in MOTIVOS_DE_ESCOPO:
            return "escopo"
        return "acesso"

    # --- chamadas ------------------------------------------------------------------------------------------------

    def _lista(self, dados, chave="value"):
        itens = dados.get(chave)
        if not isinstance(itens, list):
            raise RespostaInvalida("resposta fora do formato")
        return itens

    def eventos_real(self, ambiente, id_usuario, data_inicio, data_fim, limite):
        url = montar_url(self._urls(ambiente)["graph"], "me", "calendarView")
        parametros = {
            "startDateTime": datetime.combine(data_inicio, time.min, FUSO).isoformat(),
            "endDateTime": datetime.combine(data_fim + timedelta(days=1), time.min, FUSO).isoformat(),
            "$select": "subject,location,start,end,isAllDay,isCancelled,attendees",
            "$orderby": "start/dateTime",
            "$top": limite + 1,
        }
        dados = self._chamar_api(
            ambiente, id_usuario, "agenda", {CALENDARIO_LEITURA}, "GET", url,
            parametros=parametros, cabecalhos={"Prefer": 'outlook.timezone="UTC"'},
        )
        eventos = [
            self._evento(item) for item in self._lista(dados)
            if isinstance(item, dict) and item.get("isCancelled") is not True
        ]
        return eventos[:limite], len(eventos) > limite

    def _evento(self, item):
        try:
            dia_inteiro = item.get("isAllDay") is True
            if dia_inteiro:  # meia-noite em UTC: a data já é a do evento, sem conversão de fuso
                inicio = date.fromisoformat(_sem_fracao(item["start"]["dateTime"])[:10]).isoformat()
                fim = date.fromisoformat(_sem_fracao(item["end"]["dateTime"])[:10]).isoformat()
            else:
                inicio, fim = _momento(item["start"]), _momento(item["end"])
        except (KeyError, ValueError, TypeError):
            raise RespostaInvalida("resposta fora do formato") from None
        local = item.get("location")
        convidados = item.get("attendees")
        return {
            "titulo": str(item.get("subject") or "(sem título)")[:200],
            "inicio": inicio,
            "fim": fim,
            "dia_inteiro": dia_inteiro,
            "local": str(local.get("displayName") or "")[:200] if isinstance(local, dict) else "",
            "convidados": len(convidados) if isinstance(convidados, list) else 0,
        }

    def criar_evento_real(self, ambiente, id_usuario, evento):
        url = montar_url(self._urls(ambiente)["graph"], "me", "events")
        corpo = {
            "subject": evento["titulo"],
            "start": {"dateTime": _em_utc(evento["inicio"]), "timeZone": "UTC"},
            "end": {"dateTime": _em_utc(evento["fim"]), "timeZone": "UTC"},
            "transactionId": evento["id_unico"],
        }
        if evento.get("local"):
            corpo["location"] = {"displayName": evento["local"]}
        if evento.get("descricao"):
            corpo["body"] = {"contentType": "text", "content": evento["descricao"]}
        if evento.get("convidados"):
            corpo["attendees"] = [{"emailAddress": {"address": email}, "type": "required"} for email in evento["convidados"]]
        try:
            self._chamar_api(ambiente, id_usuario, "agenda", {CALENDARIO_ESCRITA}, "POST", url, corpo=corpo)
        except PedidoRecusado as recusa:
            if recusa.status != 409:  # 409: o `transactionId` já foi usado, ou seja, este mesmo pedido já tinha sido criado
                raise
        return {
            "titulo": evento["titulo"],
            "inicio": evento["inicio"].isoformat(timespec="minutes"),
            "fim": evento["fim"].isoformat(timespec="minutes"),
        }

    def arquivos_real(self, ambiente, id_usuario, consulta, tipo, limite):
        url = montar_url(
            self._urls(ambiente)["graph"], "me", "drive", "root", f"search(q='{_escapar_na_busca(consulta)}')",
            seguros="()'=",
        )
        parametros = {"$select": "id,name,file,folder,lastModifiedDateTime", "$top": min(limite * 3, 50)}
        dados = self._chamar_api(ambiente, id_usuario, "arquivos", {ARQUIVOS_LEITURA}, "GET", url, parametros=parametros)
        achados = []
        for item in self._lista(dados):
            if not isinstance(item, dict):
                continue
            arquivo = item.get("file")
            mime = arquivo.get("mimeType") if isinstance(arquivo, dict) else None
            achado_tipo = "pasta" if "folder" in item else TIPOS_DO_ONEDRIVE.get(mime, "outro")
            if tipo in MIME_POR_TIPO and achado_tipo != tipo:
                continue
            achados.append({
                "id_arquivo": str(item.get("id", ""))[:128],
                "titulo": str(item.get("name") or "")[:200],
                "tipo": achado_tipo,
                "modificado_em": str(item.get("lastModifiedDateTime") or "")[:10],
            })
        return achados[:limite]

    def _item(self, ambiente, id_usuario, id_arquivo, tipo_esperado, escopo):
        """(nome sem extensão, tamanho) do arquivo. Se não é do tipo esperado (`planilha` ou `documento`): `parametro_invalido`."""
        url = montar_url(self._urls(ambiente)["graph"], "me", "drive", "items", id_arquivo)
        dados = self._chamar_api(
            ambiente, id_usuario, "arquivos", {escopo}, "GET", url, parametros={"$select": "name,file,size"}
        )
        arquivo = dados.get("file")
        mime = arquivo.get("mimeType") if isinstance(arquivo, dict) else None
        nome = dados.get("name")
        if not isinstance(nome, str):
            raise RespostaInvalida("resposta fora do formato")
        if mime != MIME_POR_TIPO[tipo_esperado]:
            extensao = ".xlsx" if tipo_esperado == "planilha" else ".docx"
            artigo = "uma planilha do Excel" if tipo_esperado == "planilha" else "um documento do Word"
            raise ErroFerramenta("parametro_invalido", f"Este arquivo não é {artigo} ({extensao}).")
        tamanho = dados.get("size")
        return EXTENSAO_DO_ARQUIVO.sub("", nome)[:200], tamanho if isinstance(tamanho, int) else 0

    def _planilha(self, ambiente, id_usuario, id_arquivo, escopo):
        titulo, _ = self._item(ambiente, id_usuario, id_arquivo, "planilha", escopo)
        url = montar_url(self._urls(ambiente)["graph"], "me", "drive", "items", id_arquivo, "workbook", "worksheets")
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {escopo}, "GET", url, parametros={"$select": "name,position"}
        )
        nomes = [str(aba["name"])[:100] for aba in self._lista(dados) if isinstance(aba, dict) and "name" in aba]
        if not nomes:
            raise RespostaInvalida("resposta fora do formato")
        return {"titulo": titulo, "abas": [{"titulo": nome} for nome in nomes]}

    def _url_da_aba(self, ambiente, id_arquivo, aba):
        return montar_url(self._urls(ambiente)["graph"], "me", "drive", "items", id_arquivo, "workbook", "worksheets", aba)

    def descrever_planilha_real(self, ambiente, id_usuario, id_arquivo):
        return self._planilha(ambiente, id_usuario, id_arquivo, ARQUIVOS_LEITURA)

    def ler_planilha_real(self, ambiente, id_usuario, id_arquivo, aba, intervalo, limite):
        planilha = self._planilha(ambiente, id_usuario, id_arquivo, ARQUIVOS_LEITURA)
        aba = self._aba_existente(planilha, aba)
        recorte = limitar_intervalo(intervalo, limite) if intervalo else f"A1:Z{limite + 1}"
        url = montar_url(self._url_da_aba(ambiente, id_arquivo, aba), f"range(address='{recorte}')", seguros="()'=:")
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {ARQUIVOS_LEITURA}, "GET", url, parametros={"$select": "text"}
        )
        texto = dados.get("text")
        if not isinstance(texto, list) or not all(isinstance(linha, list) for linha in texto):
            raise RespostaInvalida("resposta fora do formato")
        linhas = [[str(celula) for celula in linha] for linha in texto]
        for linha in linhas:  # o Excel devolve o retângulo todo; o que sobra em branco no fim não é dado
            while linha and linha[-1] == "":
                linha.pop()
        while linhas and not linhas[-1]:
            linhas.pop()
        return {"titulo": planilha["titulo"], "aba": aba, "intervalo": intervalo or "", "linhas": linhas[:limite],
                "truncado": len(linhas) > limite}

    def _primeira_linha_livre(self, ambiente, id_usuario, id_arquivo, aba):
        """O número da linha logo abaixo do que já está preenchido na aba (1 se ela está vazia)."""
        url = montar_url(self._url_da_aba(ambiente, id_arquivo, aba), "usedRange(valuesOnly=true)", seguros="()=")
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "GET", url,
            parametros={"$select": "address,rowCount,columnCount"},
        )
        endereco, linhas, colunas = dados.get("address"), dados.get("rowCount"), dados.get("columnCount")
        achado = PADRAO_ENDERECO_USADO.fullmatch(endereco) if isinstance(endereco, str) else None
        if achado is None or not isinstance(linhas, int) or not isinstance(colunas, int):
            raise RespostaInvalida("resposta fora do formato")
        ultima = int(achado.group(2) or achado.group(1))
        if linhas == 1 and colunas == 1:  # aba vazia também devolve uma célula: confere se ela tem algo
            unica = montar_url(
                self._url_da_aba(ambiente, id_arquivo, aba), f"range(address='{endereco.rpartition('!')[2]}')",
                seguros="()'=:",
            )
            texto = self._chamar_api(
                ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "GET", unica, parametros={"$select": "text"}
            ).get("text")
            if texto == [[""]]:
                return 1
        return ultima + 1

    def adicionar_linha_real(self, ambiente, id_usuario, id_arquivo, aba, valores):
        """Escreve a linha logo abaixo do que já existe. O Graph não tem "acrescentar" para um intervalo comum (só para
        tabelas do Excel, que a planilha da pessoa pode não ter), então: as escritas da mesma pessoa na mesma aba andam
        uma de cada vez aqui, e a linha é lida de volta no fim. Se outra pessoa escreveu na mesma linha ao mesmo tempo,
        a leitura não bate e o resultado é `EfeitoIncerto` (a pessoa confere na planilha), nunca um "pronto" falso."""
        planilha = self._planilha(ambiente, id_usuario, id_arquivo, ARQUIVOS_ESCRITA)
        aba = self._aba_existente(planilha, aba)
        celulas = [formatos.celula_como_texto(valor) for valor in valores]
        gravaveis = [valor_da_celula(celula) for celula in celulas]
        # O Excel lê o que chega como se fosse digitado ("12/10" vira data, "=1+1" vira fórmula): células de texto
        # recebem o formato Texto antes, e o que parece fórmula já vai com o apóstrofo de `celula_como_texto`.
        formatos_das_celulas = [
            "@" if isinstance(gravavel, str) and not celula.startswith("'") else "General"
            for gravavel, celula in zip(gravaveis, celulas, strict=True)
        ]
        with self._travas_de_escrita.da((id_usuario, id_arquivo, aba)):
            linha = self._primeira_linha_livre(ambiente, id_usuario, id_arquivo, aba)
            endereco = f"A{linha}:{formatos.letra_da_coluna(len(valores) - 1)}{linha}"
            url = montar_url(self._url_da_aba(ambiente, id_arquivo, aba), f"range(address='{endereco}')", seguros="()'=:")
            if "@" in formatos_das_celulas:
                self._chamar_api(
                    ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "PATCH", url,
                    corpo={"numberFormat": [formatos_das_celulas]},
                )
            resposta = self._chamar_api(
                ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "PATCH", url, corpo={"values": [gravaveis]}
            )
            if not isinstance(resposta.get("address"), str):
                raise EfeitoIncerto()
            self._conferir_linha_gravada(ambiente, id_usuario, url, celulas)
        return {"linhas_adicionadas": 1}

    def _conferir_linha_gravada(self, ambiente, id_usuario, url, celulas):
        """Lê a linha de volta e compara a primeira célula (a leitura devolve o texto exibido, então só ela é
        comparada). Não bateu, ou a leitura falhou: `EfeitoIncerto`."""
        try:
            dados = self._chamar_api(
                ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "GET", url, parametros={"$select": "text"}
            )
            lido = dados["text"][0][0]
        except (ErroFerramenta, ConnectionError, TimeoutError, KeyError, IndexError, TypeError):
            raise EfeitoIncerto() from None
        if str(lido).strip() != celulas[0].removeprefix("'").strip():
            raise EfeitoIncerto()

    def criar_planilha_real(self, ambiente, id_usuario, titulo, linhas):
        nome = nome_do_arquivo(titulo)
        url = montar_url(self._urls(ambiente)["graph"], "me", "drive", "root:", f"{nome}.xlsx:", "content", seguros=":")
        dados = self._chamar_api(
            ambiente, id_usuario, "planilhas", {ARQUIVOS_ESCRITA}, "PUT", url,
            parametros={"@microsoft.graph.conflictBehavior": "rename"},  # nunca sobrescreve um arquivo que já existe
            conteudo=formatos.escrever_xlsx(linhas, aba=nome), cabecalhos={"Content-Type": formatos.TIPO_XLSX},
        )
        id_arquivo, link = dados.get("id"), dados.get("webUrl")
        if not isinstance(id_arquivo, str) or not isinstance(link, str) or not link.startswith("https://"):
            raise EfeitoIncerto()  # a planilha pode ter sido criada: a resposta não diz qual
        return {"id_arquivo": id_arquivo, "titulo": titulo, "link": link}

    def documento_real(self, ambiente, id_usuario, id_arquivo, limite):
        titulo, tamanho = self._item(ambiente, id_usuario, id_arquivo, "documento", ARQUIVOS_LEITURA)
        if tamanho > formatos.BYTES_NO_MAXIMO:
            raise ErroFerramenta("parametro_invalido", "O documento é grande demais para ler por aqui.")
        url = montar_url(self._urls(ambiente)["graph"], "me", "drive", "items", id_arquivo, "content")
        resposta = self._pedir_da_pessoa(
            ambiente, id_usuario, "documentos", {ARQUIVOS_LEITURA}, "GET", url, bruto=True,
            limite_de_bytes=formatos.BYTES_NO_MAXIMO, seguir_para=self._dominios_de_download(ambiente),
        )
        if resposta.status == 404 or not isinstance(resposta.dados, bytes):
            raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)
        texto = formatos.ler_docx(resposta.dados, limite)
        return {"titulo": titulo, "texto": texto["texto"], "truncado": texto["truncado"]}


CONECTOR = registrar(ConectorMicrosoft365())
