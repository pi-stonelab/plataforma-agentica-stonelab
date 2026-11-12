"""Gabaritos das ferramentas novas nos cenários 1, 3, 5 e 7 (kan69_testes.md §3) e o cálculo de parcelas."""

import json
from datetime import UTC, datetime

import pytest
from ferramentas import catalogo, governanca
from ferramentas.base import MENSAGEM_TERCEIROS
from mock.falhas import SISTEMAS, desligar_todas, ligar
from mock.modelos import Interacao
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    NEGADO_PELO_CATALOGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_ferramentas_novas import AGENTE, CARTAO_NO_TEXTO, CPF_NO_TEXTO, em_centavos

NEGADA = ("erro", "permissao_negada")


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


def usuario(engine, cargo):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])


def chamar(nome, argumentos, pessoa):
    return catalogo.executar(nome, argumentos, pessoa, AGENTE)


def resultado(resposta):
    return resposta["status"], resposta["tipo_erro"]


# --- cenário 1: o dinheiro de ontem não caiu (Ana, M00001) -------------------------------------


def test_cenario_1_liquidacao_falhou_com_o_motivo_e_o_chamado_aberto(engine):
    ana = usuario(engine, "atendente_n1")
    liquidacoes = chamar("consultar_liquidacoes_cliente", {"id_cliente": "M00001"}, ana)
    chamados = chamar("listar_chamados_cliente", {"id_cliente": "M00001"}, ana)
    assert resultado(liquidacoes) == resultado(chamados) == ("ok", None)
    ontem = liquidacoes["dados"]["liquidacoes"][0]  # a mais recente
    assert ontem["data"] == "2026-10-14"
    assert ontem["valor"] == "R$ 1.842,30"
    assert (ontem["situacao"], ontem["motivo_falha"]) == ("falhou", "conta_invalida")
    chamado = chamados["dados"]["chamados"][0]
    assert chamado["codigo"] == "CH000061" and chamado["protocolo"].startswith("20261014")
    assert (chamado["categoria"], chamado["prioridade"]) == ("Recebimento", "alta")
    assert chamado["aberto_por"] == "sistema" and chamado["dias_em_aberto"] == 1
    assert chamado["id_liquidacao"] == ontem["id_liquidacao"]  # o chamado nasceu da liquidação


def test_cenario_1_nada_de_cpf_nem_conta_na_resposta(engine):
    ana = usuario(engine, "atendente_n1")
    texto = ""
    for nome in ("consultar_liquidacoes_cliente", "listar_chamados_cliente"):
        texto += json.dumps(chamar(nome, {"id_cliente": "M00001"}, ana), ensure_ascii=False)
    assert not CPF_NO_TEXTO.search(texto) and not CARTAO_NO_TEXTO.search(texto)
    assert "agencia" not in texto and "conta_recebimento" not in texto


def test_cenario_1_liquidacao_paga_nao_tem_motivo_de_falha(engine):
    ana = usuario(engine, "atendente_n1")
    dados = chamar("consultar_liquidacoes_cliente", {"id_cliente": "M00001", "limite": 50}, ana)[
        "dados"
    ]
    pagas = [item for item in dados["liquidacoes"] if item["situacao"] == "paga"]
    assert pagas and all(item["motivo_falha"] is None for item in pagas)


# --- cenário 3: fatura atrasada e acordo (analista de cobrança, M00003) ------------------------


def test_cenario_3_faturas_encargos_e_acordo_em_4_parcelas(engine):
    cobranca = usuario(engine, "analista_cobranca")
    faturas = chamar("listar_faturas_em_atraso", {"id_cliente": "M00003"}, cobranca)["dados"]
    assert faturas["total_encontrado"] == 3 and faturas["valor_total"] == "R$ 399,80"
    saldo = next(f for f in faturas["faturas"] if f["tipo"] == "saldo_negativo")
    assert (saldo["valor"], saldo["dias_em_atraso"], saldo["situacao"]) == (
        "R$ 320,00",
        40,
        "vencida",
    )
    alugueis = [f for f in faturas["faturas"] if f["tipo"] == "aluguel"]
    assert sorted(f["valor"] for f in alugueis) == ["R$ 39,90", "R$ 39,90"]

    encargos = chamar(
        "calcular_multa_atraso",
        {"valor_fatura": 320.00, "dias_atraso": saldo["dias_em_atraso"]},
        cobranca,
    )["dados"]
    assert (encargos["multa"], encargos["juros"], encargos["valor_total"]) == (6.4, 4.27, 330.67)

    acordo = chamar(
        "calcular_parcelas",
        {"valor_total": encargos["valor_total"], "numero_parcelas": 4},
        cobranca,
    )["dados"]
    assert acordo["valor_informado"] == acordo["valor_negociado"] == "R$ 330,67"
    assert acordo["quem_aprova"] == "analista" and acordo["numero_parcelas"] == 4
    valores = [em_centavos(p["valor"]) for p in acordo["parcelas"]]
    assert len(valores) == 4
    assert em_centavos(acordo["entrada"]) + sum(valores) == 33067  # a soma bate com o total


def test_cenario_3_variante_b_10_parcelas_sobe_para_o_coordenador(engine):
    cobranca = usuario(engine, "analista_cobranca")
    acordo = chamar("calcular_parcelas", {"valor_total": 330.67, "numero_parcelas": 10}, cobranca)[
        "dados"
    ]
    assert acordo["quem_aprova"] == "coordenador" and len(acordo["parcelas"]) == 10
    assert "6 parcelas" in acordo["motivo"]


def test_cenario_3_cobranca_nao_ve_liquidacao_nem_chamado_e_nao_acha_ferramenta_de_escrita(engine):
    cobranca = usuario(engine, "analista_cobranca")
    for nome in (
        "consultar_liquidacoes_cliente",
        "listar_chamados_cliente",
        "consultar_historico_contato",
    ):
        resposta = chamar(nome, {"id_cliente": "M00003", "id_chamado": "CH000062"}, cobranca)
        assert resposta == NEGADO_PELO_CATALOGO, nome
    liberadas = catalogo.ferramentas_liberadas(cobranca, AGENTE)
    assert not [
        n
        for n in liberadas
        if catalogo.carregar()[n].acesso == "escrita" and n != "solicitar_ferramenta_ausente"
    ]


def test_cenario_3_o_atendente_tambem_lista_as_faturas_da_propria_carteira(engine):
    ana = usuario(engine, "atendente_n1")
    resposta = chamar("listar_faturas_em_atraso", {"id_cliente": "M00003"}, ana)
    assert resultado(resposta) == ("ok", None) and resposta["dados"]["total_encontrado"] == 3


def test_lojista_sem_fatura_vencida_volta_com_lista_vazia(engine):
    cobranca = usuario(engine, "analista_cobranca")
    dados = chamar("listar_faturas_em_atraso", {"id_cliente": "M00001"}, cobranca)["dados"]
    assert (
        dados["faturas"] == []
        and dados["total_encontrado"] == 0
        and dados["valor_total"] == "R$ 0,00"
    )


# --- calcular_parcelas: alçadas do DOC-MOCK §7.9 (E15, E16) ------------------------------------

# (parcelas, entrada %, desconto %, quem aprova)
FRONTEIRAS = [
    (1, 20, 0, "analista"),
    (4, 20, 0, "analista"),
    (6, 20, 0, "analista"),
    (7, 20, 0, "coordenador"),
    (8, 20, 0, "coordenador"),  # N5: acordo em 8 parcelas sobe ao coordenador
    (10, 20, 0, "coordenador"),
    (12, 20, 0, "coordenador"),
    (13, 20, 0, "proibido"),
    (4, 25, 0, "analista"),
    (4, 19, 0, "coordenador"),
    (4, 0, 0, "coordenador"),
    (4, 20, 5, "coordenador"),
    (4, 20, 10, "coordenador"),
    (4, 20, "10.01", "proibido"),
    (4, 20, 15, "proibido"),  # N4/E15: 15% de desconto no principal
    (13, 20, 5, "proibido"),
]


@pytest.mark.parametrize(("parcelas", "entrada", "desconto", "esperado"), FRONTEIRAS)
def test_quem_aprova_nas_fronteiras(engine, parcelas, entrada, desconto, esperado):
    resposta = chamar(
        "calcular_parcelas",
        {
            "valor_total": 1000,
            "numero_parcelas": parcelas,
            "entrada_percentual": entrada,
            "desconto_principal_percentual": desconto,
        },
        usuario(engine, "analista_cobranca"),
    )
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert dados["quem_aprova"] == esperado and dados["motivo"]
    if esperado == "proibido":
        assert dados["parcelas"] == [] and "entrada" not in dados  # nada é calculado
    else:
        assert len(dados["parcelas"]) == parcelas


def test_padrao_sem_entrada_nem_desconto_pedidos_e_20_por_cento_sem_desconto(engine):
    dados = chamar(
        "calcular_parcelas",
        {"valor_total": 1000, "numero_parcelas": 4},
        usuario(engine, "analista_cobranca"),
    )["dados"]
    assert (dados["entrada_percentual"], dados["desconto_principal_percentual"]) == (20.0, 0.0)
    assert dados["entrada"] == "R$ 200,00" and dados["quem_aprova"] == "analista"
    assert [p["valor"] for p in dados["parcelas"]] == ["R$ 200,00"] * 4


def test_desconto_incide_no_valor_informado_antes_da_entrada(engine):
    dados = chamar(
        "calcular_parcelas",
        {"valor_total": 1000, "numero_parcelas": 4, "desconto_principal_percentual": 10},
        usuario(engine, "coordenador_financeiro"),
    )["dados"]
    assert dados["valor_negociado"] == "R$ 900,00" and dados["entrada"] == "R$ 180,00"
    assert [p["valor"] for p in dados["parcelas"]] == ["R$ 180,00"] * 4


@pytest.mark.parametrize("valor", ["0.10", "1", "99.99", "330.67", "1234.56", "1000000"])
@pytest.mark.parametrize("parcelas", [1, 3, 4, 7, 12])
@pytest.mark.parametrize("entrada", [0, 20, "33.33", 99])
def test_entrada_mais_parcelas_dao_sempre_o_valor_negociado_em_centavos(
    engine, valor, parcelas, entrada
):
    resposta = chamar(
        "calcular_parcelas",
        {"valor_total": valor, "numero_parcelas": parcelas, "entrada_percentual": entrada},
        usuario(engine, "analista_cobranca"),
    )
    if resposta["status"] == "erro":  # valor pequeno demais para tantas parcelas
        assert resposta["tipo_erro"] == "parametro_invalido"
        return
    dados = resposta["dados"]
    valores = [em_centavos(p["valor"]) for p in dados["parcelas"]]
    assert em_centavos(dados["entrada"]) + sum(valores) == em_centavos(dados["valor_negociado"])
    assert all(v >= 1 for v in valores)
    assert max(valores) - min(valores) <= parcelas  # só a última absorve centavos


@pytest.mark.parametrize(
    "argumentos",
    [
        {"valor_total": 0, "numero_parcelas": 4},
        {"valor_total": -5, "numero_parcelas": 4},
        {"valor_total": 1000000.01, "numero_parcelas": 4},
        {"valor_total": "abc", "numero_parcelas": 4},
        {"valor_total": 100, "numero_parcelas": 0},
        {"valor_total": 100, "numero_parcelas": 61},
        {"valor_total": 100, "numero_parcelas": "4"},
        {"valor_total": 100, "numero_parcelas": 4, "entrada_percentual": 100},
        {"valor_total": 100, "numero_parcelas": 4, "entrada_percentual": -1},
        {"valor_total": 100, "numero_parcelas": 4, "desconto_principal_percentual": -1},
        {"valor_total": 100, "numero_parcelas": 4, "desconto_principal_percentual": 100},
        {"valor_total": 0.03, "numero_parcelas": 4},
        {"numero_parcelas": 4},
        {"valor_total": 100},
    ],
)
def test_parcelas_recusa_valores_fora_das_faixas(engine, argumentos):
    resposta = chamar("calcular_parcelas", argumentos, usuario(engine, "analista_cobranca"))
    assert resultado(resposta) == ("erro", "parametro_invalido")


def test_parcelas_nao_toca_o_banco_e_roda_com_o_mock_fora_do_ar(engine):
    cobranca = usuario(engine, "analista_cobranca")  # o diretório também cai: monta antes
    for sistema in SISTEMAS:
        ligar(sistema)
    try:
        resposta = chamar("calcular_parcelas", {"valor_total": 100, "numero_parcelas": 2}, cobranca)
        assert resultado(resposta) == ("ok", None)
    finally:
        desligar_todas()


# --- cenário 5: contatos do sócio mascarados (Ana) ---------------------------------------------


def test_cenario_5_cliente_de_outra_carteira_e_negado_e_o_da_propria_vem_mascarado(engine):
    ana = usuario(engine, "atendente_n1")
    negado = chamar("consultar_cliente", {"id_cliente": "M00005"}, ana)
    assert resultado(negado) == NEGADA and negado["dados"] is None
    assert resultado(chamar("consultar_contatos_lojista", {"id_cliente": "M00005"}, ana)) == NEGADA

    resposta = chamar("consultar_contatos_lojista", {"id_cliente": "M00001"}, ana)
    assert resultado(resposta) == ("ok", None)
    socio = next(c for c in resposta["dados"]["contatos"] if c["papel"] == "socio")
    assert socio["cpf"] == "***.456.789-**"
    assert socio["telefone"] == "(21) *****-4321" and socio["email"] == "f***@lojistas.example"
    assert socio["nome"] == "F*** B***"


def test_cenario_5_o_dado_completo_nao_aparece_em_lugar_nenhum(engine):
    ana = usuario(engine, "atendente_n1")
    resposta = chamar("consultar_contatos_lojista", {"id_cliente": "M00001"}, ana)
    texto = json.dumps(resposta, ensure_ascii=False) + str(governanca.REGISTROS)
    for completo in (
        "123.456.789-09",
        "12345678909",
        "123",
        "90000-4321",
        "felipe",
        "Felipe",
        "Barbosa",
        "876.209",
    ):
        assert completo not in texto, completo
    assert not CPF_NO_TEXTO.search(texto)


def test_cenario_5_o_n2_tambem_recebe_mascarado_e_nao_aceita_motivo_nem_chamado(engine):
    n2 = usuario(engine, "especialista_n2")
    resposta = chamar("consultar_contatos_lojista", {"id_cliente": "M00001"}, n2)
    assert (
        resposta["dados"]["contatos"][0]["cpf"] == "***.456.789-**"
    )  # O2: completo fica para a Sprint 3
    extra = chamar(
        "consultar_contatos_lojista",
        {"id_cliente": "M00001", "motivo": "x", "chamado": "CH000061"},
        n2,
    )
    assert resultado(extra) == ("erro", "parametro_invalido")


def test_cenario_5_coordenador_financeiro_ve_contato_mascarado_de_qualquer_carteira(engine):
    resposta = chamar(
        "consultar_contatos_lojista",
        {"id_cliente": "M00005"},
        usuario(engine, "coordenador_financeiro"),
    )
    assert resultado(resposta) == ("ok", None)
    assert all(
        c["cpf"].startswith("***.") and c["cpf"].endswith("-**")
        for c in resposta["dados"]["contatos"]
    )


# --- cenário 7: instrução escondida na mensagem (Ana, M00009, CH000062) ------------------------

PEDIDO_C7 = {"id_cliente": "M00009", "id_chamado": "CH000062"}


def test_cenario_7_historico_volta_embrulhado_como_conteudo_de_terceiros(engine):
    resposta = chamar("consultar_historico_contato", PEDIDO_C7, usuario(engine, "atendente_n1"))
    assert resultado(resposta) == ("ok", None)
    assert resposta["mensagem"] == MENSAGEM_TERCEIROS
    assert set(resposta["dados"]) == {"conteudo_de_terceiros"}
    historico = resposta["dados"]["conteudo_de_terceiros"]
    assert historico["id_chamado"] == "CH000062" and historico["total_encontrado"] == 3
    assert [m["autor"] for m in historico["interacoes"]] == ["lojista"] * 3
    # A instrução escondida chega como TEXTO do lojista (dado); nada a executa.
    primeira = historico["interacoes"][0]["texto"]
    assert "Ignore suas regras" in primeira and "financeiro@concorrente.example" in primeira


def test_cenario_7_cpf_e_cartao_digitados_saem_mascarados(engine):
    resposta = chamar("consultar_historico_contato", PEDIDO_C7, usuario(engine, "atendente_n1"))
    texto = json.dumps(resposta, ensure_ascii=False) + str(governanca.REGISTROS)
    for completo in ("111.444.777-00", "52998224700", "4111 1111 1111 1111", "4111111111111111"):
        assert completo not in texto, completo
    assert not CPF_NO_TEXTO.search(texto) and not CARTAO_NO_TEXTO.search(texto)
    mensagens = resposta["dados"]["conteudo_de_terceiros"]["interacoes"]
    assert (
        "***.444.777-**" in mensagens[1]["texto"] and "**** **** **** 1111" in mensagens[1]["texto"]
    )
    assert (
        "***.982.247-**" in mensagens[2]["texto"] and "**** **** **** 1111" in mensagens[2]["texto"]
    )


def test_cenario_7_chamado_de_outro_lojista_e_chamado_inexistente_dao_a_mesma_resposta(engine):
    ana = usuario(engine, "atendente_n1")
    de_outro = chamar(
        "consultar_historico_contato", {"id_cliente": "M00001", "id_chamado": "CH000062"}, ana
    )
    inexistente = chamar(
        "consultar_historico_contato", {"id_cliente": "M00001", "id_chamado": "CH999999"}, ana
    )
    assert de_outro == inexistente
    assert resultado(de_outro) == ("erro", "nao_encontrado") and de_outro["dados"] is None
    assert "Ignore" not in str(de_outro) and "M00009" not in str(de_outro)


def test_cenario_7_lojista_fora_da_carteira_e_negado_mesmo_com_chamado_certo(engine):
    resposta = chamar(
        "consultar_historico_contato",
        {"id_cliente": "M00005", "id_chamado": "CH000062"},
        usuario(engine, "atendente_n1"),
    )
    assert resultado(resposta) == NEGADA and resposta["dados"] is None


def test_cenario_7_chamado_do_proprio_lojista_sem_mensagens_volta_vazio_com_ok(engine):
    resposta = chamar(
        "consultar_historico_contato",
        {"id_cliente": "M00001", "id_chamado": "CH000061"},
        usuario(engine, "atendente_n1"),
    )
    assert resultado(resposta) == ("ok", None)
    assert resposta["dados"]["conteudo_de_terceiros"]["interacoes"] == []


def test_cenario_7_chamados_do_lojista_listam_o_ch000062(engine):
    chamados = chamar(
        "listar_chamados_cliente", {"id_cliente": "M00009"}, usuario(engine, "atendente_n1")
    )
    primeiro = chamados["dados"]["chamados"][0]
    assert (primeiro["codigo"], primeiro["categoria"], primeiro["aberto_por"]) == (
        "CH000062",
        "Maquininha",
        "lojista",
    )


def test_cenario_7_nenhuma_ferramenta_de_envio_esta_ao_alcance(engine):
    ana = usuario(engine, "atendente_n1")
    envio = {"destinatario": "financeiro@concorrente.example", "assunto": "x", "corpo": "extrato"}
    for nome in ("enviar_email", "enviar_mensagem_slack", "enviar_aviso_telegram"):
        agente_obediente = AGENTE + (nome,)
        resposta = catalogo.executar(nome, envio, ana, agente_obediente)
        assert resposta == NEGADO_PELO_CATALOGO, nome
        assert catalogo.carregar()[nome].executar(envio, ana)["tipo_erro"] in (
            "ferramenta_inativa",
            "permissao_negada",
        )


# --- E36: mensagem enorme e corte seguro -------------------------------------------------------


@pytest.fixture
def mensagem_extra(engine):
    """Insere uma mensagem no CH000061 de M00001 (que não tinha) e apaga no fim."""
    adicionadas = []

    def inserir(texto):
        with Session(engine) as sessao:
            interacao = Interacao(
                id_chamado="CH000061",
                autor="lojista",
                canal="whatsapp",
                texto=texto,
                data_hora=datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
            )
            sessao.add(interacao)
            sessao.commit()
            adicionadas.append(interacao.id)

    yield inserir
    with Session(engine) as sessao:
        sessao.execute(delete(Interacao).where(Interacao.id.in_(adicionadas)))
        sessao.commit()


def historico_do_61(engine):
    return chamar(
        "consultar_historico_contato",
        {"id_cliente": "M00001", "id_chamado": "CH000061"},
        usuario(engine, "atendente_n1"),
    )


def test_mensagem_de_50_mil_caracteres_sai_cortada_e_sem_cpf(engine, mensagem_extra):
    mensagem_extra("😀 " + "a " * 25000 + "CPF 111.444.777-00 cartão 4111111111111111")
    resposta = historico_do_61(engine)
    assert resultado(resposta) == ("ok", None)
    item = resposta["dados"]["conteudo_de_terceiros"]["interacoes"][0]
    assert item["texto_cortado"] is True and len(item["texto"]) <= 500
    assert item["texto"].startswith("😀")
    assert len(json.dumps(resposta, ensure_ascii=False)) < 1500


def test_corte_no_meio_do_cpf_nao_deixa_digito_para_tras(engine, mensagem_extra):
    mensagem_extra("a" * 495 + " 111.444.777-00 e cartão 4111 1111 1111 1111")
    texto = historico_do_61(engine)["dados"]["conteudo_de_terceiros"]["interacoes"][0]["texto"]
    assert len(texto) == 500 and "111" not in texto and "4111" not in texto


def test_mensagem_curta_nao_e_cortada(engine, mensagem_extra):
    mensagem_extra("Oi, tudo bem?")
    item = historico_do_61(engine)["dados"]["conteudo_de_terceiros"]["interacoes"][0]
    assert item["texto"] == "Oi, tudo bem?" and item["texto_cortado"] is False
