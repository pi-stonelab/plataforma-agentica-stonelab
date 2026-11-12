"""Peças compartilhadas pelos testes de seguranca/. Cada teste recebe uma plataforma nova."""

import pytest

from seguranca.permissoes import AtendimentoCliente, Colaborador, Financeiro, Plataforma


@pytest.fixture
def plataforma():
    return Plataforma()


@pytest.fixture
def maria(plataforma):
    return plataforma.cadastrar(Colaborador("Maria", AtendimentoCliente()))


@pytest.fixture
def joao(plataforma):
    return plataforma.cadastrar(Colaborador("João", Financeiro()))


@pytest.fixture
def triagem(plataforma, maria):
    """Agente da Maria, registrado na plataforma. João não é dono nem convidado."""
    return maria.criar_agente("Triagem", plataforma)
