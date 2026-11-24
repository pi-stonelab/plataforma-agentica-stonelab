"""O escritório simulado (Google Workspace e Microsoft 365 no modo `simulado`): agenda, planilhas e documentos
inventados, coerentes com o mundo do `mock/` (o "hoje" é o 15/10/2026; os documentos são os artigos públicos da
base de conhecimento; as planilhas trazem só indicadores agregados, nunca dado de lojista nem de pessoa).

Responde no mesmo formato do serviço de verdade (ver `escritorio.py`), sem rede e sem conta ligada. O que a
pessoa cria (evento, planilha, linha) fica na memória, só para ela, e some quando a plataforma reinicia.
"""

import threading
from copy import deepcopy
from datetime import date, timedelta

from mock import base_conhecimento, regras

from ferramentas.base import ErroFerramenta
from ferramentas.integracoes.conector import sem_acento

HOJE = regras.HOJE_DO_MOCK
TIPOS = ("planilha", "documento")
LIMITE_DE_PLANILHAS_POR_PESSOA = 20
LIMITE_DE_EVENTOS_POR_PESSOA = 100


def _evento(titulo, dia, de=None, ate=None, local="", convidados=0):
    """`de` e `ate` em "HH:MM"; sem eles, o evento é de dia inteiro."""
    if de is None:
        return {"titulo": titulo, "inicio": dia.isoformat(), "fim": (dia + timedelta(days=1)).isoformat(),
                "dia_inteiro": True, "local": local, "convidados": convidados}
    return {"titulo": titulo, "inicio": f"{dia.isoformat()}T{de}", "fim": f"{dia.isoformat()}T{ate}",
            "dia_inteiro": False, "local": local, "convidados": convidados}


EVENTOS_DO_TIME = (
    _evento("Daily do time", HOJE - timedelta(days=1), "09:00", "09:30", "Sala Rio", 6),
    _evento("Revisão da fila de chamados", HOJE, "15:00", "15:30", "Videochamada", 4),
    _evento("Treinamento: fluxo de chargeback", HOJE + timedelta(days=1), "10:00", "11:00", "Sala Paulista", 8),
    _evento("Almoço de equipe", HOJE + timedelta(days=1), "12:00", "13:00", "", 6),
    _evento("Alinhamento semanal do time", HOJE + timedelta(days=4), "10:00", "10:30", "Videochamada", 6),
    _evento("Folga compensada do time", HOJE + timedelta(days=5)),
    _evento("Retrospectiva do mês", HOJE + timedelta(days=7), "16:00", "17:00", "Sala Rio", 6),
)

PLANILHAS = {
    "SIM-PLAN-CHAMADOS": {
        "titulo": "Acompanhamento semanal de chamados",
        "modificado_em": (HOJE - timedelta(days=1)).isoformat(),
        "abas": {
            "Semana": [
                ["Semana", "Abertos", "Resolvidos", "Estourados", "Nota média"],
                ["28/09", "132", "128", "6", "4,3"],
                ["05/10", "141", "139", "4", "4,4"],
                ["12/10", "118", "97", "9", "4,1"],
            ],
            "Por fila": [
                ["Fila", "Abertos", "Prazo médio (dias úteis)"],
                ["Recebimento", "61", "1,8"],
                ["Cobrança", "34", "2,2"],
                ["Disputas", "23", "3,1"],
            ],
        },
    },
    "SIM-PLAN-RECEBIVEIS": {
        "titulo": "Fechamento de recebíveis de outubro",
        "modificado_em": HOJE.isoformat(),
        "abas": {
            "Resumo": [
                ["Dia", "Liquidações", "Falhas", "Valor total"],
                ["12/10", "1.204", "3", "R$ 2.340.180,50"],
                ["13/10", "1.311", "5", "R$ 2.512.044,10"],
                ["14/10", "1.287", "2", "R$ 2.478.390,00"],
            ],
        },
    },
}

DOCUMENTOS = {
    f"SIM-DOC-{codigo}": {"titulo": titulo, "texto": texto, "modificado_em": base_conhecimento.DATA_DOS_ARTIGOS.isoformat()}
    for codigo, titulo, _categoria, texto in base_conhecimento.ARTIGOS
}


def _nao_encontrado():
    return ErroFerramenta("nao_encontrado", "Arquivo não encontrado, ou a sua conta não tem acesso a ele.")


class MundoSimulado:
    """Estado do escritório simulado, separado por pessoa (`id_usuario`)."""

    def __init__(self):
        self._trava = threading.Lock()
        self._pessoas = {}

    def _da_pessoa(self, id_usuario):
        return self._pessoas.setdefault(id_usuario, {"eventos": [], "planilhas": {}, "linhas": {}, "contador": 0})

    def limpar(self):
        with self._trava:
            self._pessoas.clear()

    def eventos(self, id_usuario, data_inicio, data_fim, limite):
        with self._trava:
            todos = [*EVENTOS_DO_TIME, *self._da_pessoa(id_usuario)["eventos"]]
        no_periodo = [e for e in todos if data_inicio <= date.fromisoformat(e["inicio"][:10]) <= data_fim]
        no_periodo.sort(key=lambda e: e["inicio"])
        return deepcopy(no_periodo[:limite]), len(no_periodo) > limite

    def criar_evento(self, id_usuario, evento):
        with self._trava:
            pessoa = self._da_pessoa(id_usuario)
            if len(pessoa["eventos"]) >= LIMITE_DE_EVENTOS_POR_PESSOA:
                raise ErroFerramenta("parametro_invalido", "O limite de eventos do modo de demonstração acabou.")
            inicio, fim = evento["inicio"], evento["fim"]
            pessoa["eventos"].append(
                {"titulo": evento["titulo"], "inicio": inicio.isoformat(timespec="minutes"),
                 "fim": fim.isoformat(timespec="minutes"), "dia_inteiro": False,
                 "local": evento.get("local", ""), "convidados": len(evento.get("convidados", ()))}
            )
        return {"titulo": evento["titulo"], "inicio": inicio.isoformat(timespec="minutes"),
                "fim": fim.isoformat(timespec="minutes")}

    def arquivos(self, id_usuario, consulta, tipo, limite):
        with self._trava:
            propria = deepcopy(self._da_pessoa(id_usuario)["planilhas"])
        achados = []
        catalogo = (
            *((i, "planilha", p) for i, p in {**PLANILHAS, **propria}.items()),
            *((i, "documento", d) for i, d in DOCUMENTOS.items()),
        )
        for id_arquivo, tipo_do_arquivo, item in catalogo:
            if tipo in TIPOS and tipo != tipo_do_arquivo:
                continue
            if sem_acento(consulta) in sem_acento(item["titulo"]):
                achados.append({"id_arquivo": id_arquivo, "titulo": item["titulo"], "tipo": tipo_do_arquivo,
                                "modificado_em": item["modificado_em"]})
        achados.sort(key=lambda a: (a["modificado_em"], a["id_arquivo"]), reverse=True)
        return achados[:limite]

    def _planilha(self, id_usuario, id_arquivo):
        """Planilha (catálogo ou da pessoa) com as linhas que ela acrescentou. Não achou: `nao_encontrado`."""
        pessoa = self._da_pessoa(id_usuario)
        planilha = pessoa["planilhas"].get(id_arquivo) or PLANILHAS.get(id_arquivo)
        if planilha is None:
            raise _nao_encontrado()
        abas = deepcopy(planilha["abas"])
        for aba, linhas in pessoa["linhas"].get(id_arquivo, {}).items():
            abas[aba].extend(deepcopy(linhas))
        return planilha["titulo"], abas

    def descrever_planilha(self, id_usuario, id_arquivo):
        with self._trava:
            titulo, abas = self._planilha(id_usuario, id_arquivo)
        return {"titulo": titulo, "abas": [{"titulo": a, "linhas": len(l), "colunas": max(map(len, l), default=0)}
                                           for a, l in abas.items()]}

    def ler_planilha(self, id_usuario, id_arquivo, aba, intervalo, limite):
        """`intervalo` já validado pela ferramenta ("A1:F20") ou None (a aba toda, até `limite` linhas)."""
        with self._trava:
            titulo, abas = self._planilha(id_usuario, id_arquivo)
        aba = aba or next(iter(abas))
        if aba not in abas:
            raise ErroFerramenta("nao_encontrado", "Aba não encontrada na planilha.")
        linhas = abas[aba]
        primeira, ultima, primeira_coluna, ultima_coluna = _recorte(intervalo)
        linhas = [linha[primeira_coluna:ultima_coluna] for linha in linhas[primeira:ultima]]
        return {"titulo": titulo, "aba": aba, "intervalo": intervalo or "", "linhas": linhas[:limite],
                "truncado": len(linhas) > limite}

    def adicionar_linha(self, id_usuario, id_arquivo, aba, valores):
        with self._trava:
            _, abas = self._planilha(id_usuario, id_arquivo)
            if aba not in abas:
                raise ErroFerramenta("nao_encontrado", "Aba não encontrada na planilha.")
            pessoa = self._da_pessoa(id_usuario)
            pessoa["linhas"].setdefault(id_arquivo, {}).setdefault(aba, []).append(list(valores))
        return {"linhas_adicionadas": 1}

    def criar_planilha(self, id_usuario, titulo, linhas):
        with self._trava:
            pessoa = self._da_pessoa(id_usuario)
            if len(pessoa["planilhas"]) >= LIMITE_DE_PLANILHAS_POR_PESSOA:
                raise ErroFerramenta("parametro_invalido", "O limite de planilhas do modo de demonstração acabou.")
            pessoa["contador"] += 1
            id_arquivo = f"SIM-PLAN-U{pessoa['contador']:03d}"
            pessoa["planilhas"][id_arquivo] = {
                "titulo": titulo, "modificado_em": HOJE.isoformat(), "abas": {"Planilha1": deepcopy(linhas)},
            }
        return {"id_arquivo": id_arquivo, "titulo": titulo, "link": f"https://simulado.example/planilhas/{id_arquivo}"}

    def documento(self, id_usuario, id_arquivo, limite):
        documento = DOCUMENTOS.get(id_arquivo)
        if documento is None:
            raise _nao_encontrado()
        texto = documento["texto"]
        return {"titulo": documento["titulo"], "texto": texto[:limite], "truncado": len(texto) > limite}


def _recorte(intervalo):
    """(primeira linha, última linha exclusiva, primeira coluna, última coluna exclusiva) de "A1:F20"; sem intervalo, tudo."""
    if not intervalo:
        return 0, None, 0, None
    inicio, _, fim = intervalo.partition(":")
    coluna_a, linha_a = _celula(inicio)
    coluna_b, linha_b = _celula(fim or inicio)
    return linha_a - 1, linha_b, coluna_a, coluna_b + 1


def _celula(texto):
    """("C", 12) -> (2, 12): índice da coluna (A=0) e número da linha."""
    letras = texto.rstrip("0123456789")
    numero = int(texto[len(letras):])
    coluna = 0
    for letra in letras.upper():
        coluna = coluna * 26 + ord(letra) - 64
    return coluna - 1, numero

