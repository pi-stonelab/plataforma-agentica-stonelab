"""Jira Cloud (REST API v3): ler, abrir e comentar chamados internos da Stone, pela conta de serviço da plataforma.

Configuração (.env): `JIRA_URL` (o site, como https://empresa.atlassian.net), `JIRA_EMAIL` e `JIRA_TOKEN` (conta
de serviço e token de API, autenticação Basic), `JIRA_PROJETOS` (chaves liberadas, como `KAN,PLAT`) e
`JIRA_TIPOS` (tipos de chamado liberados para abrir, como `Tarefa,Bug`; o primeiro é o padrão). Preencher o
`JIRA_TOKEN` liga a integração; `JIRA_MODO` força `real`, `simulado` ou `desligado`.

O modelo nunca escolhe site nem projeto fora da lista: a chave do chamado tem de ser de um projeto liberado,
inclusive para ler. Descrição e comentários chegam do Jira em ADF (`adf.py`) e saem daqui em texto simples,
sem e-mail nem nome de ninguém. No modo simulado, os chamados ficam em memória (`ChamadosSimulados`) e toda
resposta diz isso em `fonte`.

Pedidos (documentação oficial: https://developer.atlassian.com/cloud/jira/platform/rest/v3/):
- GET  /rest/api/3/issue/{chave}?fields=...          (404: não existe ou a conta não vê)
- GET  /rest/api/3/issue/{chave}/comment?orderBy=-created&maxResults=N
- POST /rest/api/3/issue            {"fields": {project, issuetype, summary, description}}  → 201 {"key"}
- POST /rest/api/3/issue/{chave}/comment  {"body": ADF}                                   → 201 {"id"}
- GET  /rest/api/3/myself e /rest/api/3/project/{chave}   (só o `testar`)
"""

import base64
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http
from ferramentas.integracoes.cliente_http import RespostaInvalida
from ferramentas.integracoes.conector import (
    Conector,
    ConfiguracaoInvalida,
    DestinoNaoPermitido,
    ler_lista,
)
from ferramentas.integracoes.jira.adf import adf_do_texto, texto_do_adf
from ferramentas.integracoes.registro import registrar
from mock import falhas

PADRAO_PROJETO = re.compile(r"[A-Z][A-Z0-9_]{1,9}")
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
TIPOS_SIMULADOS = ("Tarefa",)
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
        with self._trava:
            self._semear(projeto)
            chave = f"{projeto}-{self._proximo[projeto]}"
            self._proximo[projeto] += 1
            self._chamados[chave] = {
                "chave_jira": chave, "resumo": resumo, "situacao": "Aberto", "tipo": tipo, "prioridade": "Média",
                "criado_em": None, "atualizado_em": None, "texto": descricao, "comentarios": [],
            }
            return chave

    def comentar(self, chave, texto):
        with self._trava:
            self._semear(PADRAO_CHAVE.fullmatch(chave).group(1))
            chamado = self._chamados.get(chave)
            if chamado is None:
                return None
            chamado["comentarios"].insert(0, {"criado_em": None, "texto": texto})
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
        "JIRA_EMAIL": "JIRA_EMAIL inválido: use o e-mail da conta de serviço que criou o token.",
        "JIRA_TOKEN": "JIRA_TOKEN inválido: crie um token de API em id.atlassian.com (Segurança > Tokens de API).",
        "JIRA_PROJETOS": "JIRA_PROJETOS inválida: as chaves dos projetos separadas por vírgula, como KAN,PLAT.",
        "JIRA_TIPOS": "JIRA_TIPOS inválida: os tipos de chamado separados por vírgula, como Tarefa,Bug.",
    }

    def __init__(self):
        super().__init__()
        self.simulados = ChamadosSimulados()

    def _listas(self, ambiente):
        projetos = ler_lista(ambiente, "JIRA_PROJETOS", PADRAO_PROJETO)
        tipos = ler_lista(ambiente, "JIRA_TIPOS", PADRAO_TIPO)
        return tuple(projetos), tuple(tipos)

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

    def fora_do_ar(self):
        return falhas.fora_do_ar("jira")

    def _ligado(self, ambiente):
        modo = self.exigir_ligado(ambiente)
        if self.fora_do_ar():
            raise ConnectionError("jira fora do ar (falha simulada)")
        return modo

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
            return self.simulados.abrir(projeto, tipo, resumo, descricao)
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
        for projeto in config.projetos:
            url = cliente_http.montar_url(config.url, "rest", "api", "3", "project", projeto)
            achado = self.chamar("testar_projeto", lambda url=url: cliente_http.pedir("GET", url, cabecalhos=cabecalhos))
            if achado.status == 404:
                raise ErroFerramenta(
                    "nao_encontrado",
                    f"Projeto {projeto} não encontrado, ou a conta de serviço não tem acesso. Confira JIRA_PROJETOS.",
                )
        return f"O Jira aceitou a conta de serviço. Projetos liberados encontrados: {', '.join(config.projetos)}."

    def reiniciar(self):
        super().reiniciar()
        self.simulados.limpar()


CONECTOR = registrar(ConectorJira())
