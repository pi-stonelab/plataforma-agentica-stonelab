"""Apoio dos testes das seis ferramentas de leitura da B2b (cenários 1, 3, 5 e 7)."""

import re

from .apoio_ferramentas import TODAS_ATIVAS

NOVAS = (
    "consultar_liquidacoes_cliente",
    "listar_chamados_cliente",
    "consultar_historico_contato",
    "listar_faturas_em_atraso",
    "calcular_parcelas",
    "consultar_contatos_lojista",
)
AGENTE = TODAS_ATIVAS + NOVAS

# Escrito à mão a partir de DOC-MOCK §8.2 (o que cada cargo vê) e de mock/regras.py (O4: liquidação
# também para o atendimento). Quem tem a categoria de dado da ficha de cada ferramenta.
ATENDIMENTO = {"atendente_n1", "especialista_n2", "supervisor_atendimento"}
CARGOS_DA_FERRAMENTA = {
    "consultar_liquidacoes_cliente": ATENDIMENTO
    | {"analista_recebiveis", "coordenador_financeiro"},
    "listar_chamados_cliente": ATENDIMENTO | {"analista_ouvidoria"},
    "consultar_historico_contato": ATENDIMENTO | {"analista_ouvidoria"},
    "listar_faturas_em_atraso": ATENDIMENTO | {"analista_cobranca", "coordenador_financeiro"},
    "consultar_contatos_lojista": ATENDIMENTO
    | {"analista_ouvidoria", "analista_cobranca", "coordenador_financeiro"},
}
# Cálculo puro: todos os cargos que usam ferramenta.
CARGOS_DO_CALCULO = ATENDIMENTO | {
    "analista_ouvidoria",
    "analista_cobranca",
    "analista_disputas",
    "analista_recebiveis",
    "coordenador_financeiro",
}

CPF_NO_TEXTO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CARTAO_NO_TEXTO = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")


def argumentos_de(nome, codigo):
    """Argumentos mínimos de cada ferramenta para o lojista `codigo` (chamado do cenário 7)."""
    if nome == "consultar_historico_contato":
        return {"id_cliente": codigo, "id_chamado": "CH000062"}
    return {"id_cliente": codigo}


def em_centavos(texto):
    """ "R$ 1.842,30" vira 184230."""
    return int(re.sub(r"\D", "", texto))
