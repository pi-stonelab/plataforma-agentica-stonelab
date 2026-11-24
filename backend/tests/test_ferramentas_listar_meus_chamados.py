"""listar_meus_chamados pelo catálogo e por cargo: a fila é só de quem pergunta e dentro da carteira do cargo."""

import pytest
from ferramentas import catalogo

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

TODAS = tuple(catalogo.nomes())


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def fila(engine, id_funcionario, /, **argumentos):
    return catalogo.executar("listar_meus_chamados", argumentos, usuario_do_diretorio(engine, id_funcionario), TODAS)


def test_ana_ve_so_os_chamados_abertos_dela_com_o_prazo(engine):
    resposta = fila(engine, gab.ANA)
    assert resposta["status"] == "ok"
    chamados = resposta["dados"]["chamados"]
    assert chamados and all(c["situacao"] not in ("resolvido", "fechado") for c in chamados)
    assert {"codigo", "protocolo", "id_cliente", "prazo_em", "prazo_estourado", "dias_em_aberto"} <= set(chamados[0])
    assert [c["prazo_em"] for c in chamados] == sorted(c["prazo_em"] for c in chamados)
    assert resposta["dados"]["atrasados"] == sum(c["prazo_estourado"] for c in chamados)


def test_a_fila_de_uma_pessoa_nao_traz_a_de_outra(engine):
    da_ana = {c["codigo"] for c in fila(engine, gab.ANA)["dados"]["chamados"]}
    do_bruno = {c["codigo"] for c in fila(engine, "F0002")["dados"]["chamados"]}
    assert da_ana and do_bruno and not da_ana & do_bruno


def test_o_argumento_nao_troca_de_pessoa(engine):
    resposta = fila(engine, gab.ANA, **{"id_funcionario": "F0002"})
    assert resposta["tipo_erro"] == "parametro_invalido"


def test_limite_corta_e_marca_truncado(engine):
    total = fila(engine, "F0002")["dados"]["total_encontrado"]
    cortada = fila(engine, "F0002", limite=1)["dados"]
    assert len(cortada["chamados"]) == 1 and cortada["truncado"] == (total > 1)


def test_o_texto_do_chamado_nao_sai(engine):
    chamado = fila(engine, gab.ANA)["dados"]["chamados"][0]
    assert "resumo" not in chamado


@pytest.mark.parametrize("id_funcionario", [gab.COBRANCA, gab.DISPUTAS, "F0010", gab.COORDENADOR_FINANCEIRO])
def test_o_financeiro_nao_alcanca_a_ferramenta(engine, id_funcionario):
    assert fila(engine, id_funcionario)["tipo_erro"] == "ferramenta_inexistente"
