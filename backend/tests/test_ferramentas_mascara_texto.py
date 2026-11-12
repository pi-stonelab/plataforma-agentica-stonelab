"""Máscara de CPF e cartão em texto livre (ALTO-1 da auditoria B): separadores livres, Unicode, sem ReDoS."""

import re
import time

import pytest
from ferramentas import mascara

CPF = "***.444.777-**"
CPF_2 = "***.982.247-**"
CARTAO = "**** **** **** 1111"


def livre(texto):
    return mascara.mascarar({"texto": texto}, ("interacao",))["texto"]


CASOS_DE_CPF = [
    # Achados da auditoria (todos saíam sem máscara).
    ("CPF 111 444 777 00", f"CPF {CPF}"),
    ("111 444 777-00", CPF),
    ("111.444.777 - 00", CPF),
    ("cpf52998224700 fim", f"cpf{CPF_2} fim"),
    ("x52998224700", f"x{CPF_2}"),
    ("cpf_52998224700", f"cpf_{CPF_2}"),
    ("529\u200b982\u200b247\u200b00", CPF_2),  # zero-width space
    ("529⁠982﻿247‍00", CPF_2),  # word joiner, BOM, zero-width joiner
    ("111.444\n777-00", CPF),
    ("111.444\r\n777-00", CPF),
    ("111/444/777/00", CPF),
    ("ＣＰＦ １１１．４４４．７７７－００", f"CPF {CPF}"),  # largura total
    ("５２９９８２２４７００", CPF_2),
    ("٥٢٩٩٨٢٢٤٧٠٠", CPF_2),  # dígitos árabe-índicos
    ("111 444 777 00", CPF),  # NBSP
    ("111　444　777　00", CPF),  # espaço ideográfico
    ("111 444 777 00", CPF),  # espaço fino
    ("111–444–777—00", CPF),  # traços longos
    ("111 . 444 . 777 - 00", CPF),
    # Formatos que já funcionavam e o cenário 7.
    ("111.444.777-00", CPF),
    ("52998224700", CPF_2),
    ("CPF 111.444.777-00.", f"CPF {CPF}."),
    ("O CPF do sócio é 111.444.777-00 e foi só.", f"O CPF do sócio é {CPF} e foi só."),
    ("Caso não aceite com pontos: CPF 52998224700, cartão", f"Caso não aceite com pontos: CPF {CPF_2}, cartão"),
    # Falso positivo aceito: celular de 11 dígitos vira CPF mascarado.
    ("21999991234", "***.999.912-**"),
]

CASOS_DE_CARTAO = [
    ("4111 1111 1111 1111", CARTAO),
    ("4111-1111-1111-1111", CARTAO),
    ("4111111111111111", CARTAO),
    ("4111  1111  1111  1111", CARTAO),
    ("4111.1111.1111.1111", CARTAO),
    ("4111 1111 1111 1111", CARTAO),
    ("4111\u200b1111\u200b1111\u200b1111", CARTAO),
    ("４１１１　１１１１　１１１１　１１１１", CARTAO),
    ("4111\n1111\n1111\n1111", CARTAO),
    ("4111 - 1111 - 1111 - 1111", CARTAO),
    ("cartao4111111111111111x", f"cartao{CARTAO}x"),
    ("cartão: 4111 1111 1111 1111.", f"cartão: {CARTAO}."),
    ("3782 822463 10005", "**** **** **** 0005"),  # Amex 4-6-5
    ("378282246310005", "**** **** **** 0005"),  # Amex corrido, 15 dígitos
    ("4111 1111 1111 1", "**** **** **** 1111"),  # 13 dígitos
    ("4111 1111 1111 1111 111", "**** **** **** 1111"),  # 19 dígitos
]


@pytest.mark.parametrize(("entrada", "esperado"), CASOS_DE_CPF + CASOS_DE_CARTAO)
def test_numero_em_texto_livre_sai_mascarado_e_a_mascara_e_idempotente(entrada, esperado):
    assert livre(entrada) == esperado
    assert livre(esperado) == esperado


@pytest.mark.parametrize(("entrada", "_"), CASOS_DE_CPF + CASOS_DE_CARTAO)
def test_nenhum_numero_completo_sobra_na_saida(entrada, _):
    digitos = re.sub(r"\D", "", livre(entrada))
    assert len(digitos) <= 6


@pytest.mark.parametrize(
    "entrada",
    [
        "1 2 3 4 5 6 7 8 9 0 1 2",  # 12 dígitos: nem CPF nem cartão, na dúvida mascara
        "4111 1111 1111 1111 4111 1111 1111 1111",  # dois cartões juntos: mais de 19
        "111.444.777-00 529.982.247-00",  # dois CPFs colados por espaço
    ],
)
def test_na_duvida_mascara_tudo(entrada):
    assert livre(entrada) == "***"


@pytest.mark.parametrize(
    "texto",
    [
        "Chamado CH000062 aberto em 2026-10-14T09:10:00 pelo canal WhatsApp.",
        "Valor R$ 1.842,30 e multa de R$ 320,00 em 14/10/2026.",
        "Ligue 0800 123 e peça o ramal 4567.",  # 10 dígitos separados por palavra e espaços
        "M00001 e M00009 na carteira 3.",
        "Acentuação já normalizada: ação, côco, ç.",
    ],
)
def test_texto_comum_nao_muda(texto):
    assert livre(texto) == texto


def test_dois_numeros_separados_por_palavra_ou_virgula_sao_mascarados_cada_um():
    assert livre("CPF 111.444.777-00, cartão 4111 1111 1111 1111 e CPF 52998224700") == (
        f"CPF {CPF}, cartão {CARTAO} e CPF {CPF_2}"
    )


def test_separador_demais_entre_os_digitos_nao_junta_numeros():
    # Cinco ou mais separadores seguidos: são dois números distintos (decisão documentada).
    assert livre("12345     6789012") == "12345     6789012"


def test_protocolo_do_chamado_so_passa_se_o_valor_inteiro_tem_o_formato():
    assert mascara.mascarar({"protocolo": "20261014-000001"}, ("chamado",)) == {
        "protocolo": "20261014-000001"
    }
    assert mascara.mascarar({"protocolo": "20261014-000001 4111"}, ("chamado",)) != {
        "protocolo": "20261014-000001 4111"
    }
    assert livre("protocolo 20261014-000001") == "protocolo **** **** **** 0001"


def test_numero_dentro_de_estrutura_aninhada_tambem_e_mascarado():
    dados = {"itens": [{"texto": "cpf 111 444 777 00"}, {"texto": ["4111  1111  1111  1111"]}]}
    saida = mascara.mascarar(dados, ("interacao",))
    assert saida == {"itens": [{"texto": f"cpf {CPF}"}, {"texto": [CARTAO]}]}


@pytest.mark.parametrize(
    "bloco",
    ["1", "1 ", "12 ", "4111 ", "1.", "1\n", "1-", "1\u200b", "１ "],
)
def test_um_megabyte_de_digitos_e_separadores_termina_rapido(bloco):
    texto = bloco * (1_000_000 // len(bloco))
    inicio = time.perf_counter()
    saida = livre(texto)
    assert time.perf_counter() - inicio < 5
    assert saida  # sobrou alguma coisa e nada travou


def test_um_megabyte_de_numeros_com_separador_de_cinco_nao_trava():
    texto = "12345678901" + " " * 5 + ("0" * 11 + " " * 5) * 80_000
    inicio = time.perf_counter()
    livre(texto)
    assert time.perf_counter() - inicio < 5
