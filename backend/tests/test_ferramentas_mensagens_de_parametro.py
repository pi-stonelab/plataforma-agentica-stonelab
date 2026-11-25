"""Valor inválido num parâmetro: a mensagem diz o que a ferramenta espera, com um exemplo (revisão de usuário do
bloco B, 22/11). O agente corrige o pedido sem adivinhar, e nenhuma mensagem repete o valor que veio."""

import pytest
from ferramentas import dados_sinteticos

from .apoio_ferramentas import executar, limpar_estado, mundo_do_mock, usuario_do_diretorio


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    dados_sinteticos.configurar(engine)
    limpar_estado()
    yield
    limpar_estado()


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, "F0001")


@pytest.mark.parametrize(
    ("nome", "argumentos", "mensagem"),
    [
        (
            "calcular_multa_atraso",
            {"valor_fatura": "cem reais", "dias_atraso": 1},
            "O parâmetro valor_fatura deve ser um número, como 1250.00.",
        ),
        (
            "calcular_multa_atraso",
            {"valor_fatura": 100, "dias_atraso": "dez"},
            "O parâmetro dias_atraso deve ser um número inteiro, como 3.",
        ),
        (
            "consultar_cotacao_moeda",
            {"moeda": "USD", "data": "14/10/2026"},
            "O parâmetro data deve ser uma data no formato AAAA-MM-DD, como 2026-10-14.",
        ),
        (
            "consultar_cotacao_moeda",
            {"moeda": "DOLAR"},
            "O parâmetro moeda deve ser um texto de até 3 caracteres.",
        ),
    ],
)
def test_valor_invalido_diz_o_formato_esperado_sem_repetir_o_valor(ana, nome, argumentos, mensagem):
    resposta = executar(nome, argumentos, ana, ferramentas_do_agente=(nome,))
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("parametro_invalido", mensagem)
    for valor in argumentos.values():
        if isinstance(valor, str) and len(valor) > 3:
            assert valor not in resposta["mensagem"]
