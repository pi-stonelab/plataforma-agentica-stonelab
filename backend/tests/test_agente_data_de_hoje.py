"""A data de hoje no prompt (F3): o modelo não tem relógio. Simulado: o "hoje" do mock; real: o dia de Brasília."""

from datetime import datetime

import pytest
from agentes.agente_atendimento import agente as atendimento
from agentes.agente_geral import agente as geral
from ferramentas import catalogo, integracoes
from ferramentas.integracoes.apis_publicas.conector import FUSO_DA_COTACAO

from .apoio_agente import modelo_roteirizado, usuario_do_cargo

SIMULADO = {"APIS_PUBLICAS_MODO": "simulado"}
REAL = {"APIS_PUBLICAS_MODO": "real"}


def test_simulado_o_hoje_e_o_do_mock_com_a_hora():
    assert catalogo.data_de_hoje(SIMULADO) == "Hoje é 15/10/2026, 21h (horário de Brasília)."


def test_real_o_hoje_e_o_de_brasilia_e_o_prompt_separa_do_dia_dos_dados_de_lojista(monkeypatch):
    relogio = lambda: datetime(2026, 11, 24, 9, 30, tzinfo=FUSO_DA_COTACAO)
    monkeypatch.setattr(integracoes.conector("apis_publicas"), "agora_real", relogio)
    assert catalogo.data_de_hoje(REAL) == (
        "Hoje é 24/11/2026 (horário de Brasília). Os dados de lojistas são sintéticos e valem para 15/10/2026."
    )


def test_real_no_mesmo_dia_do_mock_nao_repete_a_data():
    # a suíte congela o relógio real em 15/10/2026
    assert catalogo.data_de_hoje(REAL) == "Hoje é 15/10/2026 (horário de Brasília)."


def test_google_real_tambem_liga_o_relogio_de_verdade(monkeypatch):
    relogio = lambda: datetime(2026, 12, 1, 8, 0, tzinfo=FUSO_DA_COTACAO)
    monkeypatch.setattr(integracoes.conector("google_workspace"), "agora_real", relogio)
    assert catalogo.data_de_hoje({**SIMULADO, "GOOGLE_MODO": "real"}).startswith("Hoje é 01/12/2026")


@pytest.mark.parametrize("sistema", [atendimento.SISTEMA, geral.SISTEMA])
def test_os_dois_prompts_mandam_dizer_a_data_da_cotacao_e_da_consulta(sistema):
    assert "diga sempre a data a que ele se refere" in sistema


def test_a_data_vai_antes_da_pergunta_em_todo_turno_dos_dois_agentes():
    usuario = usuario_do_cargo("atendente_n1")
    for rodar in (
        lambda modelo, historico: atendimento.rodar_turno(
            "quanto está o dólar?", usuario, atendimento.FERRAMENTAS_DO_AGENTE, modelo, historico
        ),
        lambda modelo, historico: geral.rodar_turno_geral("quanto está o dólar?", usuario, modelo, historico),
    ):
        prompts = []
        rodar(modelo_roteirizado(["FINAL: ok"], prompts), [("oi", "olá")])
        esperado = catalogo.data_de_hoje()
        assert esperado in prompts[0]
        assert prompts[0].endswith(f"{esperado}\n\nPergunta do funcionário: quanto está o dólar?")
