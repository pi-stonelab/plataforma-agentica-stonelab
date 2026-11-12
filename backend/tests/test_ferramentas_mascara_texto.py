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
    ("3782 822463 10006", "**** **** **** 0006"),  # Amex 4-6-5
    ("378282246310006", "**** **** **** 0006"),  # Amex corrido, 15 dígitos
    ("4111 1111 1111 1", "**** **** **** 1111"),  # 13 dígitos
    ("4111 1111 1111 1111 111", "**** **** **** 1111"),  # 19 dígitos
]


CPF_DE_12345678901 = "***.456.789-**"
CPF_FORMATOS_NOVOS = [
    # MED-1 da auditoria C: separadores fora da lista, mais de 4 separadores, tags e invisíveis.
    ("111,444,777,00", CPF),
    ("111:444:777:00", CPF),
    ("111|444|777|00", CPF),
    ("111;444;777;00", CPF),
    ("(111)444(777)00", f"({CPF}"),
    ("[111][444][777][00]", f"[{CPF}]"),
    ("111*444*777*00", CPF),
    ("111~444~777~00", CPF),
    ("111•444•777•00", CPF),
    ("111·444·777·00", CPF),
    ("111'444'777'00", CPF),
    ('111"444"777"00', CPF),
    ("111“444”777‘’00", CPF),  # aspas tipográficas
    ("111«444»777«00", CPF),
    ("111<444>777<00", CPF),
    ("111–444—777―00", CPF),  # en dash, em dash, barra horizontal
    ("111     444     777     00", CPF),  # cinco espaços
    ("111 - - 444 - - 777 - - 00", CPF),
    ((" " * 5).join("11144477700"), CPF),
    ("111<b></b>444<b></b>777<b></b>00", CPF),
    ("111<br/>444<br/>777<br>00", CPF),
    ("111</span>444<i>777</i>00", CPF),
    ("1️⃣1️⃣1️⃣ 4️⃣4️⃣4️⃣ 77700", CPF),  # keycap
    ("1️1️1️ 444 777 00", CPF),  # seletor de variação
    ("1́ 1́ 1́ 444 777 00", CPF),  # acento combinante
    ("111󠀠444󠀠777󠀠00", CPF),  # caracteres tag do Unicode
    ("CPF: 111,444,777,00.", f"CPF: {CPF}."),
]
CARTAO_FORMATOS_NOVOS = [
    ("4111'1111'1111'1111", CARTAO),
    ("4111,1111,1111,1111", CARTAO),
    ("4111|1111|1111|1111", CARTAO),
    ("4111:1111:1111:1111", CARTAO),
    ("4111*1111*1111*1111", CARTAO),
    ("4111 • 1111 • 1111 • 1111", CARTAO),
    ("4111<b>1111</b>1111<b>1111", CARTAO),
    ("4111      1111      1111      1111", CARTAO),
]


@pytest.mark.parametrize(
    ("entrada", "esperado"), CPF_FORMATOS_NOVOS + CARTAO_FORMATOS_NOVOS
)
def test_formatos_novos_de_separador_saem_mascarados(entrada, esperado):
    assert livre(entrada) == esperado
    assert livre(esperado) == esperado
    assert len(re.sub(r"\D", "", livre(entrada))) <= 6


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
    # Nove ou mais separadores seguidos: são dois números distintos (limite de 8, decisão documentada).
    assert livre("12345" + " " * 9 + "6789012") == "12345" + " " * 9 + "6789012"
    assert livre("12345" + " " * 8 + "678901") == CPF_DE_12345678901


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


def test_tag_longa_ou_com_atributo_nao_e_separador():
    # Tag curta (nome de até 10 letras, sem atributos) é separador; o resto quebra o número.
    assert livre('111<a href="x">444<a href="x">777<a href="x">00') != CPF
    assert livre("111<tagcomnomemuitolongo>444") == "111<tagcomnomemuitolongo>444"


def test_falsos_positivos_aceitos_do_lado_seguro_estao_documentados_em_teste():
    assert livre("14:30:00 15/10/2026") == "**** **** **** 2026"  # hora colada em data
    assert livre("R$ 1.842,30; R$ 320,00") == "R$ 1.842,30; R$ 320,00"  # a letra R$ separa
    assert livre("1.842,30;14/10/2026") == "**** **** **** 2026"


def test_protocolo_no_campo_protocolo_e_valor_em_reais_nos_campos_de_valor_nao_sao_mascarados():
    dados = {
        "protocolo": "20261014-000001",
        "valor": "R$ 12.345.678.900,00",
        "valor_bruto": "R$ 1.842,30",
        "valor_liquido": "R$ 123.456.789,01",
        "valor_total": "R$ 0,99",
    }
    assert mascara.mascarar(dados, ("chamado",)) == dados
    assert mascara.mascarar({"itens": [dados]}, ("chamado",)) == {"itens": [dados]}


def test_valor_fora_do_formato_ou_em_outro_campo_continua_mascarado():
    assert mascara.mascarar({"valor": "R$ 12.345.678.900,00 e 4111 1111"}, ("transacao",)) != {
        "valor": "R$ 12.345.678.900,00 e 4111 1111"
    }
    assert mascara.mascarar({"valor": "52998224700"}, ("transacao",)) == {"valor": CPF_2}
    assert livre("R$ 12.345.678.900,00") != "R$ 12.345.678.900,00"  # texto livre: mascara


def test_numero_dividido_entre_dois_campos_ou_mensagens_e_limitacao_conhecida():
    # Só o filtro de saída da resposta final (KAN-63) resolve; a máscara vê um texto por vez.
    assert livre("CPF 111.444") == "CPF 111.444"
    assert livre("777-00") == "777-00"


@pytest.mark.parametrize(
    "bloco",
    ["1,", "1:", "1|", "1;", "1*", "1~", "1\u2022", "1\ufe0f", "1\u0301", "1<b>", "1 - - - ", "1" + " " * 8],
)
def test_um_megabyte_com_os_separadores_novos_termina_rapido(bloco):
    texto = bloco * (1_000_000 // len(bloco))
    inicio = time.perf_counter()
    assert livre(texto)
    assert time.perf_counter() - inicio < 5


def test_um_megabyte_de_numeros_separados_por_nove_espacos_nao_trava():
    texto = ("0" * 11 + " " * 9) * 50_000
    inicio = time.perf_counter()
    livre(texto)
    assert time.perf_counter() - inicio < 5


def test_um_megabyte_de_tags_abertas_nao_trava():
    texto = "1" + "<b" * 500_000
    inicio = time.perf_counter()
    livre(texto)
    assert time.perf_counter() - inicio < 5
