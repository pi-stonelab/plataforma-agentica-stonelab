"""Quem pode virar `Usuario`: só funcionário ativo (ferramentas/diretorio.py), igual para o terminal e o back-end."""

import pytest
from agentes import terminal
from ferramentas import dados_sinteticos, diretorio
from mock.modelos import Funcionario
from sqlalchemy import update
from sqlalchemy.orm import Session

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    engine.dispose()


def _mudar_situacao(engine, id_funcionario, situacao):
    with Session(engine) as sessao, sessao.begin():
        sessao.execute(update(Funcionario).where(Funcionario.id == id_funcionario).values(situacao=situacao))


def test_funcionario_ativo_vira_usuario_com_o_perfil_do_cargo(engine):
    usuario = diretorio.buscar_usuario(gab.ANA)
    assert usuario.id_usuario == gab.ANA
    assert usuario.cargo == "atendente_n1"


@pytest.mark.parametrize("id_funcionario", [gab.DESLIGADO, gab.AFASTADO])
def test_desligado_e_afastado_do_mock_nao_viram_usuario(engine, id_funcionario):
    assert diretorio.buscar_usuario(id_funcionario) is None


@pytest.mark.parametrize("id_funcionario", ["F9999", "", "F0001' OR '1'='1"])
def test_id_inexistente_ou_malicioso_nao_vira_usuario(engine, id_funcionario):
    assert diretorio.buscar_usuario(id_funcionario) is None


@pytest.mark.parametrize("situacao", ["afastado", "desligado"])
def test_situacao_diferente_de_ativo_no_banco_nao_passa(engine, situacao):
    _mudar_situacao(engine, gab.ANA, situacao)
    assert diretorio.buscar_usuario(gab.ANA) is None


@pytest.mark.parametrize("situacao", ["ferias", "Ativo", "ATIVO", " ativo", "ativo ", "", None])
def test_so_a_situacao_exatamente_ativo_passa(monkeypatch, situacao):
    """O banco só aceita três situações (CHECK), mas a regra não depende disso: nega o que não for `ativo`."""
    funcionario = {"id": gab.ANA, "cargo": "atendente_n1", "carteiras": ["varejo"], "situacao": situacao}
    monkeypatch.setattr(dados_sinteticos, "buscar_funcionario", lambda _: funcionario)
    assert diretorio.buscar_usuario(gab.ANA) is None


def test_quem_e_desligado_depois_deixa_de_ser_aceito(engine):
    assert diretorio.buscar_usuario(gab.ANA) is not None
    _mudar_situacao(engine, gab.ANA, "desligado")
    assert diretorio.buscar_usuario(gab.ANA) is None


def test_diretorio_fora_do_ar_levanta_connection_error_e_nao_devolve_none(monkeypatch, engine):
    def indisponivel(*_, **__):
        raise ConnectionError("integração indisponível")

    monkeypatch.setattr(dados_sinteticos, "buscar_funcionario", indisponivel)
    with pytest.raises(ConnectionError):
        diretorio.buscar_usuario(gab.ANA)


def test_terminal_usa_a_mesma_regra_e_traduz_a_falha_do_diretorio(monkeypatch, engine):
    assert terminal.buscar_usuario_no_diretorio(gab.DESLIGADO) is None
    assert terminal.buscar_usuario_no_diretorio(gab.ANA).id_usuario == gab.ANA

    def indisponivel(*_, **__):
        raise ConnectionError("integração indisponível")

    monkeypatch.setattr(dados_sinteticos, "buscar_funcionario", indisponivel)
    with pytest.raises(ValueError, match="indisponível"):
        terminal.buscar_usuario_no_diretorio(gab.ANA)


def test_terminal_nao_decide_situacao_por_conta_propria():
    """A regra mora em ferramentas/diretorio.py; duplicá-la no terminal é o que deixava o back-end sem ela."""
    assert not hasattr(terminal, "SITUACAO_ATIVA")
