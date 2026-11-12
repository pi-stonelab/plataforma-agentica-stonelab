"""Apoio dos testes do agente: funcionários de exemplo, ferramentas do agente e limpeza dos registros."""

import importlib

from ferramentas import governanca

AGENTE_COMPLETO = (
    "consultar_cliente",
    "consultar_transacoes_cliente",
    "calcular_multa_atraso",
    "consultar_endereco_cep",
    "solicitar_ferramenta_ausente",
)


def n1_atendimento():
    return governanca.Usuario("USR-0001", "N1", "atendimento", ("CLI-0001",))


def n1_dados():
    return governanca.Usuario("USR-0002", "N1", "dados", ())


def n2_financeiro():
    return governanca.Usuario("USR-0003", "N2", "financeiro", ())


def pedidos():
    nome = "ferramentas.plataforma.solicitar_ferramenta_ausente.func"
    return importlib.import_module(nome).PEDIDOS


def limpar():
    """Zera os registros da governança e os pedidos de ferramenta entre um teste e outro."""
    del governanca.REGISTROS[:]
    pedidos().clear()
