"""Jira Cloud (REST API v3): ler, abrir e comentar chamados internos da Stone, pela conta de serviço da plataforma.

Configuração (.env): `JIRA_URL` (o site, como https://empresa.atlassian.net), `JIRA_EMAIL` e `JIRA_TOKEN` (um
usuário comum dedicado à plataforma e um token de API SEM escopos, autenticação Basic; conta de serviço da
Atlassian só funciona com `JIRA_URL=https://api.atlassian.com/ex/jira/<cloudId>`), `JIRA_PROJETOS` (chaves
liberadas, com nome opcional: `KAN:Kanban da plataforma,PLAT`) e `JIRA_TIPOS` (tipos de chamado liberados para
abrir, como `Tarefa,Bug`; o primeiro é o padrão). Preencher o `JIRA_TOKEN` liga a integração; `JIRA_MODO` força
`real`, `simulado` ou `desligado`.

O modelo nunca escolhe site nem projeto fora da lista: a chave do chamado tem de ser de um projeto liberado,
inclusive para ler. Descrição e comentários chegam do Jira em ADF (`adf.py`) e saem daqui em texto simples,
sem e-mail nem nome de ninguém (menção vira `[menção]`; e-mail no meio do texto sai mascarado pela ferramenta).
No modo simulado, os chamados ficam em memória (`ChamadosSimulados`), o que a plataforma abriu ou comentou vai
também para a caixa de saída simulada, e toda resposta diz isso em `fonte`.

Pedidos (documentação oficial: https://developer.atlassian.com/cloud/jira/platform/rest/v3/):
- GET  /rest/api/3/issue/{chave}?fields=...          (404: não existe ou a conta não vê)
- GET  /rest/api/3/issue/{chave}/comment?orderBy=-created&maxResults=N
- POST /rest/api/3/issue            {"fields": {project, issuetype, summary, description}}  → 201 {"key"}
- POST /rest/api/3/issue/{chave}/comment  {"body": ADF}                                   → 201 {"id"}
- GET  /rest/api/3/myself, /rest/api/3/project/{chave} e /rest/api/3/issue/createmeta/{chave}/issuetypes
                                                          (só o `testar`: a conta, o projeto e os tipos dele)
- 400 traz `{"errorMessages": [...], "errors": {"campo": "..."}}`: só os nomes dos campos aparecem no `testar`.
"""

import base64
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from ferramentas import dados_sinteticos
from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http, simuladas
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida
from ferramentas.integracoes.conector import (
    Conector,
    ConfiguracaoInvalida,
    DestinoNaoPermitido,
    ler_lista,
)
from ferramentas.integracoes.jira.adf import adf_do_texto, texto_do_adf
from ferramentas.integracoes.registro import registrar

PADRAO_PROJETO = re.compile(r"[A-Z][A-Z0-9_]{1,9}")
PADRAO_PROJETO_COM_NOME = re.compile(r"[A-Z][A-Z0-9_]{1,9}(:[^:,\n]{1,60})?")
PADRAO_CHAVE = re.compile(r"([A-Z][A-Z0-9_]{1,9})-[1-9][0-9]{0,8}")
PADRAO_TIPO = re.compile(r"[^\s,:][^,:\n]{0,38}[^\s,:]|[^\s,:]")
PADRAO_EMAIL_DA_CONTA = re.compile(r"[^@\s,]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
PADRAO_TOKEN = re.compile(r"[A-Za-z0-9_=+/.-]{16,300}")
PADRAO_ID = re.compile(r"[0-9]{1,18}")
CAMPOS_DO_CHAMADO = "summary,status,issuetype,priority,created,updated,description,project"
COMENTARIOS_POR_CONSULTA = 5
TAMANHO_DA_DESCRICAO = 2000
TAMANHO_DO_COMENTARIO = 1000
TAMANHO_DE_CAMPO_CURTO = 255
PROJETOS_SIMULADOS = ("PLAT",)
NOMES_SIMULADOS = {"PLAT": "Plataforma (demonstração)"}
TIPOS_SIMULADOS = ("Tarefa",)
FUSO = ZoneInfo("America/Sao_Paulo")
FONTE_REAL = "Jira"
FONTE_SIMULADA = "Jira simulado (modo de demonstração): nada disto existe no Jira de verdade"
MENSAGEM_TESTE_SIMULADO = "Modo simulado: os chamados ficam na memória da plataforma, sem chamar o Jira."
MENSAGEM_RECUSA_AO_ABRIR = (
    "O Jira recusou o chamado: confira se o projeto e o tipo liberados existem no Jira. Nada foi criado."
)
MENSAGEM_RECUSA_AO_COMENTAR = "O Jira recusou o comentário. Nada foi gravado."


@dataclass(frozen=True)
class ConfiguracaoJira:
    url: str
    projetos: tuple
    tipos: tuple
    autorizacao: str = field(repr=False)  # o cabeçalho Basic pronto (e-mail e token): fora do repr e de log


def _data(valor):
    """Data e hora do Jira ("2026-11-20T10:15:30.000-0300") como ISO curto; formato estranho: texto cortado."""
    if not isinstance(valor, str):
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S.%f%z").isoformat(timespec="minutes")
    except ValueError:
        return valor[:25]


def _nome(objeto):
    """O `name` de um objeto do Jira (situação, tipo, prioridade), curto; ausente: None."""
    nome = objeto.get("name") if isinstance(objeto, dict) else None
    return nome[:TAMANHO_DE_CAMPO_CURTO] if isinstance(nome, str) else None


def _chamado_do_jira(dados, chave):
    campos = dados.get("fields") if isinstance(dados, dict) else None
    if not isinstance(campos, dict) or dados.get("key") != chave or not isinstance(campos.get("summary"), str):
        raise RespostaInvalida("resposta fora do formato")
    return {
        "chave_jira": chave,
        "resumo": campos["summary"][:TAMANHO_DE_CAMPO_CURTO],
        "situacao": _nome(campos.get("status")),
        "tipo": _nome(campos.get("issuetype")),
        "prioridade": _nome(campos.get("priority")),
        "criado_em": _data(campos.get("created")),
        "atualizado_em": _data(campos.get("updated")),
        "texto": texto_do_adf(campos.get("description"), TAMANHO_DA_DESCRICAO),  # a descrição do chamado
    }


def _comentarios_do_jira(dados):
    if not isinstance(dados, dict) or not isinstance(dados.get("comments"), list):
        raise RespostaInvalida("resposta fora do formato")
    total = dados.get("total") if isinstance(dados.get("total"), int) else len(dados["comments"])
    comentarios = [
        {"criado_em": _data(item.get("created")), "texto": texto_do_adf(item.get("body"), TAMANHO_DO_COMENTARIO)}
        for item in dados["comments"][:COMENTARIOS_POR_CONSULTA]
        if isinstance(item, dict)
    ]
    return comentarios, total


def _agora_do_mock():
    """O "agora" do mundo simulado (15/10/2026), em ISO com o fuso: o simulado não usa o relógio de verdade."""
    return dados_sinteticos.AGORA_DO_MOCK.replace(tzinfo=FUSO).isoformat(timespec="minutes")


def _campos_recusados(dados):
    """Os NOMES dos campos que o Jira recusou num 400 (`errors`), nunca as mensagens: só o `testar` mostra."""
    erros = dados.get("errors") if isinstance(dados, dict) else None
    return sorted(str(campo)[:40] for campo in erros) if isinstance(erros, dict) else []


class ChamadosSimulados:
    """Os chamados do modo simulado, em memória: dois de exemplo por projeto e os que a plataforma abrir."""

    def __init__(self):
        self._trava = threading.Lock()
        self._chamados = {}
        self._proximo = {}

    def _semear(self, projeto):
        if projeto in self._proximo:
            return
        exemplos = (
            ("Painel de liquidações lento para o time de recebíveis", "Em andamento", "Tarefa"),
            ("Acesso ao relatório semanal de chargebacks", "Concluído", "Tarefa"),
        )
        for numero, (resumo, situacao, tipo) in enumerate(exemplos, start=1):
            self._chamados[f"{projeto}-{numero}"] = {
                "chave_jira": f"{projeto}-{numero}",
                "resumo": resumo,
                "situacao": situacao,
                "tipo": tipo,
                "prioridade": "Média",
                "criado_em": "2026-10-13T09:00-03:00",
                "atualizado_em": "2026-10-14T16:30-03:00",
                "texto": "Chamado de exemplo do modo de demonstração.",
                "comentarios": [{"criado_em": "2026-10-14T16:30-03:00", "texto": "Em análise pelo time responsável."}],
            }
        self._proximo[projeto] = 101

    def chamado(self, chave):
        with self._trava:
            self._semear(PADRAO_CHAVE.fullmatch(chave).group(1))
            chamado = self._chamados.get(chave)
            return None if chamado is None else {**chamado, "comentarios": list(chamado["comentarios"])}

    def abrir(self, projeto, tipo, resumo, descricao):
        agora = _agora_do_mock()
        with self._trava:
            self._semear(projeto)
            chave = f"{projeto}-{self._proximo[projeto]}"
            self._proximo[projeto] += 1
            self._chamados[chave] = {
                "chave_jira": chave, "resumo": resumo, "situacao": "Aberto", "tipo": tipo, "prioridade": "Média",
                "criado_em": agora, "atualizado_em": agora, "texto": descricao, "comentarios": [],
            }
            return chave

    def comentar(self, chave, texto):
        agora = _agora_do_mock()
        with self._trava:
            self._semear(PADRAO_CHAVE.fullmatch(chave).group(1))
            chamado = self._chamados.get(chave)
            if chamado is None:
                return None
            chamado["comentarios"].insert(0, {"criado_em": agora, "texto": texto})
            chamado["atualizado_em"] = agora
            return str(len(chamado["comentarios"]))

    def limpar(self):
        with self._trava:
            self._chamados.clear()
            self._proximo.clear()


class ConectorJira(Conector):
    nome = "jira"
    rotulo = "Jira"
    variavel_modo = "JIRA_MODO"
    modo_padrao = "desligado"
    variavel_que_liga = "JIRA_TOKEN"
    variaveis = ("JIRA_MODO", "JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJETOS", "JIRA_TIPOS")
    credencial = "plataforma"
    mensagem_desligada = "Os chamados internos (Jira) não estão ligados nesta plataforma."
    como_ligar = "preencha JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJETOS e JIRA_TIPOS (ou use JIRA_MODO=simulado)"
    dica_sem_rede = "Confira a internet e o JIRA_URL, ou use JIRA_MODO=simulado."
    dicas = {
        "JIRA_URL": "JIRA_URL inválida: use o endereço do site, como https://empresa.atlassian.net, sem / no fim.",
        "JIRA_EMAIL": "JIRA_EMAIL inválido: use o e-mail do usuário da plataforma que criou o token.",
        "JIRA_TOKEN": (
            "JIRA_TOKEN inválido: em id.atlassian.com, Segurança > Criar token de API (sem escopos)."
        ),
        "JIRA_PROJETOS": (
            "JIRA_PROJETOS inválida: as chaves dos projetos separadas por vírgula, como KAN,PLAT, com um nome"
            " opcional (KAN:Kanban da plataforma)."
        ),
        "JIRA_TIPOS": "JIRA_TIPOS inválida: os tipos de chamado separados por vírgula, como Tarefa,Bug.",
    }

    def __init__(self):
        super().__init__()
        self.simulados = ChamadosSimulados()
        self.simuladas = simuladas.caixa(self.nome)

    def _listas(self, ambiente):
        projetos = [item.split(":", 1)[0] for item in ler_lista(ambiente, "JIRA_PROJETOS", PADRAO_PROJETO_COM_NOME)]
        tipos = ler_lista(ambiente, "JIRA_TIPOS", PADRAO_TIPO)
        return tuple(projetos), tuple(tipos)

    def nomes_dos_projetos(self, ambiente=os.environ):
        """{chave: nome legível} dos projetos com nome no .env (no simulado sem lista, o de exemplo)."""
        if self.modo(ambiente) == "simulado" and not self._listas(ambiente)[0]:
            return dict(NOMES_SIMULADOS)
        itens = (item.partition(":") for item in ler_lista(ambiente, "JIRA_PROJETOS", PADRAO_PROJETO_COM_NOME))
        return {chave: nome.strip() for chave, _, nome in itens if nome.strip()}

    def _configuracao(self, ambiente):
        url = cliente_http.url_base(ambiente.get("JIRA_URL", ""), "JIRA_URL")
        email = ambiente.get("JIRA_EMAIL", "").strip()
        token = ambiente.get("JIRA_TOKEN", "").strip()
        if not PADRAO_EMAIL_DA_CONTA.fullmatch(email):
            raise ConfiguracaoInvalida("JIRA_EMAIL")
        if not PADRAO_TOKEN.fullmatch(token):
            raise ConfiguracaoInvalida("JIRA_TOKEN")
        projetos, tipos = self._listas(ambiente)
        if not projetos:
            raise ConfiguracaoInvalida("JIRA_PROJETOS")
        if not tipos:
            raise ConfiguracaoInvalida("JIRA_TIPOS")
        credencial = base64.b64encode(f"{email}:{token}".encode()).decode()
        return ConfiguracaoJira(url, projetos, tipos, f"Basic {credencial}")

    def conferir_configuracao(self, ambiente=os.environ):
        self._configuracao(ambiente)

    def destinos(self, ambiente=os.environ):
        """(projetos, tipos) liberados agora. No simulado sem lista no .env: os de exemplo."""
        if self.modo(ambiente) == "simulado":
            projetos, tipos = self._listas(ambiente)
            return projetos or PROJETOS_SIMULADOS, tipos or TIPOS_SIMULADOS
        return self._listas(ambiente)

    def exigir_chave(self, chave, ambiente=os.environ):
        """A chave do chamado, se tem o formato e é de um projeto liberado; senão `DestinoNaoPermitido`."""
        achado = PADRAO_CHAVE.fullmatch(chave) if isinstance(chave, str) else None
        if achado is None:
            raise ValueError("chave fora do formato")
        self.exigir_destino(achado.group(1), self.destinos(ambiente)[0])
        return chave

    def chave_para_ferramenta(self, chave, ambiente=os.environ):
        """A chave pedida pelo modelo, em maiúsculas, já conferida; senão `parametro_invalido` dizendo o porquê."""
        chave = chave.strip().upper()
        if not PADRAO_CHAVE.fullmatch(chave):
            raise ErroFerramenta("parametro_invalido", "A chave do chamado deve ser como KAN-123.")
        try:
            return self.exigir_chave(chave, ambiente)
        except DestinoNaoPermitido:
            liberados = ", ".join(self.destinos(ambiente)[0]) or "nenhum"
            mensagem = f"Esse projeto não está liberado nesta plataforma. Projetos liberados: {liberados}."
            raise ErroFerramenta("parametro_invalido", mensagem) from None

    def _cabecalhos(self, config):
        return {"Authorization": config.autorizacao}

    def chamado(self, chave, ambiente=os.environ):
        """O chamado `chave` com os últimos comentários, ou None se não existe (ou a conta não vê)."""
        modo = self._ligado(ambiente)
        self.exigir_chave(chave, ambiente)
        if modo == "simulado":
            chamado = self.simulados.chamado(chave)
            if chamado is None:
                return None
            total = len(chamado["comentarios"])
            chamado["comentarios"] = chamado["comentarios"][:COMENTARIOS_POR_CONSULTA]
            return {**chamado, "total_comentarios": total, "fonte": FONTE_SIMULADA}
        config = self._configuracao(ambiente)
        url = cliente_http.montar_url(config.url, "rest", "api", "3", "issue", chave)
        parametros = {"fields": CAMPOS_DO_CHAMADO}

        def ler_chamado():
            resposta = cliente_http.pedir("GET", url, parametros=parametros, cabecalhos=self._cabecalhos(config))
            return None if resposta.status == 404 else _chamado_do_jira(resposta.dados, chave)

        chamado = self.chamar("consultar_chamado", ler_chamado)
        if chamado is None:
            return None
        url_comentarios = cliente_http.montar_url(config.url, "rest", "api", "3", "issue", chave, "comment")
        parametros = {"orderBy": "-created", "startAt": 0, "maxResults": COMENTARIOS_POR_CONSULTA}

        def ler_comentarios():
            resposta = cliente_http.pedir(
                "GET", url_comentarios, parametros=parametros, cabecalhos=self._cabecalhos(config)
            )
            return ([], 0) if resposta.status == 404 else _comentarios_do_jira(resposta.dados)

        comentarios, total = self.chamar("consultar_comentarios", ler_comentarios)
        return {**chamado, "comentarios": comentarios, "total_comentarios": total, "fonte": FONTE_REAL}

    def _escrever(self, etapa, url, corpo, config, mensagem_de_recusa):
        """POST de escrita. Recusa (4xx): nada foi criado. Resposta sem o que esperamos depois de um 2xx: a
        ação aconteceu e não sabemos o resultado (`EfeitoIncerto`)."""

        def enviar():
            try:
                resposta = cliente_http.pedir("POST", url, corpo=corpo, cabecalhos=self._cabecalhos(config))
            except ErroFerramenta as erro:
                raise ErroFerramenta(erro.tipo_erro, mensagem_de_recusa) from None
            if resposta.status == 404:
                raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira. Nada foi gravado.")
            return resposta.dados

        return self.chamar(etapa, enviar)

    def abrir(self, projeto, tipo, resumo, descricao, ambiente=os.environ):
        """Abre um chamado e devolve a chave criada (ex.: KAN-123)."""
        modo = self._ligado(ambiente)
        projetos, tipos = self.destinos(ambiente)
        self.exigir_destino(projeto, projetos)
        self.exigir_destino(tipo, tipos)
        if modo == "simulado":
            chave = self.simulados.abrir(projeto, tipo, resumo, descricao)
            self.simuladas.guardar(chave, f"{resumo}\n\n{descricao}")
            return chave
        config = self._configuracao(ambiente)
        corpo = {
            "fields": {
                "project": {"key": projeto},
                "issuetype": {"name": tipo},
                "summary": resumo,
                "description": adf_do_texto(descricao),
            }
        }
        url = cliente_http.montar_url(config.url, "rest", "api", "3", "issue")
        dados = self._escrever("abrir_chamado", url, corpo, config, MENSAGEM_RECUSA_AO_ABRIR)
        chave = dados.get("key") if isinstance(dados, dict) else None
        if not isinstance(chave, str) or not chave.startswith(f"{projeto}-") or not PADRAO_CHAVE.fullmatch(chave):
            raise EfeitoIncerto()  # o Jira aceitou o pedido, mas a resposta não diz qual chamado ficou
        return chave

    def comentar(self, chave, texto, ambiente=os.environ):
        """Comenta no chamado `chave` e devolve o id do comentário."""
        modo = self._ligado(ambiente)
        self.exigir_chave(chave, ambiente)
        if modo == "simulado":
            id_comentario = self.simulados.comentar(chave, texto)
            if id_comentario is None:
                raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira. Nada foi gravado.")
            self.simuladas.guardar(chave, texto)
            return id_comentario
        config = self._configuracao(ambiente)
        url = cliente_http.montar_url(config.url, "rest", "api", "3", "issue", chave, "comment")
        dados = self._escrever("comentar_chamado", url, {"body": adf_do_texto(texto)}, config, MENSAGEM_RECUSA_AO_COMENTAR)
        id_comentario = dados.get("id") if isinstance(dados, dict) else None
        if not isinstance(id_comentario, str) or not PADRAO_ID.fullmatch(id_comentario):
            raise EfeitoIncerto()
        return id_comentario

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        config = self._configuracao(ambiente)
        cabecalhos = self._cabecalhos(config)
        eu = cliente_http.montar_url(config.url, "rest", "api", "3", "myself")
        resposta = self.chamar("testar_conta", lambda: cliente_http.pedir("GET", eu, cabecalhos=cabecalhos))
        if not isinstance(resposta.dados, dict) or not resposta.dados.get("accountId"):
            raise RespostaInvalida("resposta fora do formato")
        linhas = ["O Jira aceitou a conta da plataforma."]
        for projeto in config.projetos:
            url = cliente_http.montar_url(config.url, "rest", "api", "3", "project", projeto)
            achado = self.chamar("testar_projeto", lambda url=url: cliente_http.pedir("GET", url, cabecalhos=cabecalhos))
            if achado.status == 404:
                raise ErroFerramenta(
                    "nao_encontrado",
                    f"Projeto {projeto} não encontrado, ou a conta da plataforma não tem acesso. Confira JIRA_PROJETOS.",
                )
            linhas.append(self._conferir_tipos(config, projeto))
        return " ".join(linhas)

    def _conferir_tipos(self, config, projeto):
        """Os tipos de chamado que o projeto aceita, e qual tipo de `JIRA_TIPOS` não existe nele."""
        url = cliente_http.montar_url(config.url, "rest", "api", "3", "issue", "createmeta", projeto, "issuetypes")
        cabecalhos = self._cabecalhos(config)
        try:
            resposta = self.chamar("testar_tipos", lambda: cliente_http.pedir("GET", url, cabecalhos=cabecalhos))
        except PedidoRecusado as recusa:
            campos = ", ".join(_campos_recusados(recusa.dados)) or "nenhum campo informado"
            return f"{projeto}: o Jira recusou a consulta dos tipos (campos: {campos})."
        dados = resposta.dados if isinstance(resposta.dados, dict) else {}
        lista = dados.get("issueTypes", dados.get("values"))
        if resposta.status == 404 or not isinstance(lista, list):
            return f"{projeto}: não deu para conferir os tipos de chamado."
        existentes = [t["name"] for t in lista if isinstance(t, dict) and isinstance(t.get("name"), str)]
        faltando = [tipo for tipo in config.tipos if tipo not in existentes]
        if faltando:
            return (
                f"{projeto}: o tipo {', '.join(faltando)} não existe neste projeto (abrir chamado vai falhar)."
                f" Tipos do projeto: {', '.join(existentes) or 'nenhum'}. Corrija JIRA_TIPOS."
            )
        return f"{projeto}: ok (tipos {', '.join(config.tipos)})."

    def reiniciar(self):
        super().reiniciar()
        self.simulados.limpar()
        self.simuladas.limpar()


CONECTOR = registrar(ConectorJira())
