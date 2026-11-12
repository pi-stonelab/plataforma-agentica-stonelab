"""Apoio dos testes do agente: funcionários do diretório do mock, ferramentas do agente e limpeza."""

import importlib

from ferramentas import dados_sinteticos
from mock.banco import criar_engine
from mock.gerar import recriar

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    TODAS_ATIVAS,
    limpar_estado,
    usuario_do_diretorio,
)

AGENTE_COMPLETO = TODAS_ATIVAS
_MUNDO = {}


def mundo():
    """Mock em memória, criado uma vez e religado às ferramentas a cada chamada."""
    if "engine" not in _MUNDO:
        _MUNDO["engine"] = criar_engine("sqlite://")
        recriar(_MUNDO["engine"])
    dados_sinteticos.configurar(_MUNDO["engine"])
    return _MUNDO["engine"]


def usuario_do_cargo(cargo):
    """O funcionário de exemplo do cargo (FUNCIONARIO_DO_CARGO), montado pelo diretório do mock."""
    return usuario_do_diretorio(mundo(), FUNCIONARIO_DO_CARGO[cargo])


def atendente_n1():
    """Ana (F0001), carteira varejo; vê só os lojistas do varejo."""
    return usuario_do_cargo("atendente_n1")


def coordenador_financeiro():
    """Renata (F0011), N2 do financeiro; vê todos os lojistas e tem a categoria venda."""
    return usuario_do_cargo("coordenador_financeiro")


def analista_cobranca():
    """Diego (F0008), N1 do financeiro; não tem a categoria de dado venda."""
    return usuario_do_cargo("analista_cobranca")


def pedidos():
    nome = "ferramentas.plataforma.solicitar_ferramenta_ausente.func"
    return importlib.import_module(nome).PEDIDOS


def limpar():
    """Religa o mock e zera registros, destinos, falhas e pedidos de ferramenta entre os testes."""
    mundo()
    limpar_estado()
