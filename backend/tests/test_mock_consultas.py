"""Testes do conector do mock (consultas) e da falha "fora do ar"."""

import logging
from datetime import date

import pytest
from mock.banco import criar_engine
from mock.consultas import (
    LIMITE_MAXIMO,
    buscar_chamados,
    buscar_conta_recebimento,
    buscar_contatos,
    buscar_faturas,
    buscar_funcionario,
    buscar_interacoes,
    buscar_liquidacoes,
    buscar_lojista,
    buscar_vendas,
    carteira_do_lojista,
)
from mock.falhas import (
    SISTEMAS,
    SistemaIndisponivel,
    desligar,
    desligar_todas,
    fora_do_ar,
    ligar,
)
from mock.gerar import recriar
from mock.regras import CAMPOS_NAO_RESTRITOS, CLASSIFICACAO_CAMPOS
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def engine():
    engine = criar_engine("sqlite://")
    recriar(engine)
    return engine


@pytest.fixture
def sessao(engine):
    with Session(engine) as sessao_do_teste:
        yield sessao_do_teste


@pytest.fixture(autouse=True)
def sem_falhas(monkeypatch):
    monkeypatch.delenv("MOCK_FALHAS", raising=False)
    desligar_todas()
    yield
    desligar_todas()


# --- teto, colunas e forma -----------------------------------------------------------------


def test_vendas_respeitam_teto_de_50_e_devolvem_o_total(sessao):
    resposta = buscar_vendas(sessao, "M00005", limite=500)  # a média empresa tem 70 vendas
    assert len(resposta["itens"]) == LIMITE_MAXIMO == 50
    assert resposta["total"] == 70
    assert resposta["limite"] == 50


def test_limite_menor_e_respeitado_e_limite_invalido_vira_minimo(sessao):
    assert len(buscar_vendas(sessao, "M00005", limite=3)["itens"]) == 3
    assert len(buscar_vendas(sessao, "M00005", limite=0)["itens"]) == 1
    assert len(buscar_vendas(sessao, "M00005")["itens"]) == 50


def test_vendas_so_devolvem_as_colunas_necessarias(sessao):
    item = buscar_vendas(sessao, "M00001", limite=1)["itens"][0]
    assert set(item) == {
        "codigo", "data_hora", "modalidade", "parcelas", "bandeira", "ultimos4",
        "valor_bruto_centavos", "valor_liquido_centavos", "situacao",
    }
    assert isinstance(item["valor_bruto_centavos"], int)
    assert isinstance(item["data_hora"], str)  # ISO, pronto para JSON


def test_filtro_de_datas_das_vendas_e_inclusivo(sessao):
    inicio, fim = date(2026, 9, 1), date(2026, 9, 30)
    resposta = buscar_vendas(sessao, "M00005", inicio, fim, limite=50)
    assert resposta["total"] > 0
    assert all("2026-09-01" <= v["data_hora"][:10] <= "2026-09-30" for v in resposta["itens"])
    ultimo_dia = buscar_vendas(sessao, "M00005", date(2026, 10, 15), date(2026, 10, 15))
    assert all(v["data_hora"].startswith("2026-10-15") for v in ultimo_dia["itens"])
    assert buscar_vendas(sessao, "M00005", date(2030, 1, 1))["total"] == 0


def test_liquidacoes_do_cenario_1(sessao):
    resposta = buscar_liquidacoes(sessao, "M00001", date(2026, 10, 14), date(2026, 10, 14))
    assert resposta["total"] == 1
    assert set(resposta["itens"][0]) == {
        "id", "data", "valor_total_centavos", "situacao", "motivo_falha"}
    assert resposta["itens"][0]["valor_total_centavos"] == 184230
    assert resposta["itens"][0]["situacao"] == "falhou"


def test_faturas_vencidas_do_cenario_3(sessao):
    todas = buscar_faturas(sessao, "M00003")
    vencidas = buscar_faturas(sessao, "M00003", somente_vencidas=True)
    assert todas["total"] == 7 and vencidas["total"] == 3
    assert {f["tipo"] for f in vencidas["itens"]} == {"aluguel", "saldo_negativo"}
    assert set(vencidas["itens"][0]) == {
        "codigo", "tipo", "mes_referencia", "vencimento", "valor_centavos", "situacao",
        "dias_em_atraso"}
    assert buscar_faturas(sessao, "M00001", somente_vencidas=True) == {
        "itens": [], "total": 0, "limite": 50}


def test_chamados_e_interacoes(sessao):
    chamados = buscar_chamados(sessao, "M00001")
    assert chamados["total"] >= 3
    abertos_pelo_sistema = [c for c in chamados["itens"] if c["aberto_por"] == "sistema"]
    assert len(abertos_pelo_sistema) == 1
    assert abertos_pelo_sistema[0]["categoria"] == "Recebimento"
    chamado_7 = buscar_chamados(sessao, "M00009")["itens"]
    interacoes = buscar_interacoes(sessao, "M00009", chamado_7[0]["codigo"])
    assert set(interacoes["itens"][0]) == {"id", "autor", "canal", "data_hora", "texto"}
    assert "teste_seguranca" not in interacoes["itens"][0]  # só colunas pedidas


def test_contatos_e_conta_de_recebimento_chegam_em_claro_para_a_mascara_depois(sessao):
    contatos = buscar_contatos(sessao, "M00001")["itens"]
    assert set(contatos[0]) == {"id", "nome", "cpf", "papel", "telefone", "email"}
    assert contatos[0]["cpf"] == "123.456.789-09"
    conta = buscar_conta_recebimento(sessao, "M00001")
    assert set(conta) == {"banco", "agencia", "conta", "situacao"}
    assert conta["situacao"] == "invalida"


def test_lojista_e_carteira(sessao):
    lojista = buscar_lojista(sessao, "M00005")
    assert lojista["carteira"] == "contas_chave" and lojista["id_responsavel"] == "F0003"
    assert set(lojista) == {
        "codigo", "nome_fantasia", "segmento", "porte", "cidade", "uf", "carteira", "situacao",
        "data_entrada", "id_responsavel"}
    assert carteira_do_lojista(sessao, "M00001") == {
        "codigo": "M00001", "carteira": "varejo", "id_responsavel": None}


def test_funcionario_sem_nome_nem_email(sessao):
    ana = buscar_funcionario(sessao, "F0001")
    assert ana == {"id": "F0001", "cargo": "atendente_n1", "area": "atendimento",
                   "carteiras": ["varejo"], "situacao": "ativo"}
    assert buscar_funcionario(sessao, "F0013")["area"] is None  # admin: transversal
    assert buscar_funcionario(sessao, "F0013")["carteiras"] == []
    assert buscar_funcionario(sessao, "F0014")["situacao"] == "desligado"
    assert buscar_funcionario(sessao, "F0015")["situacao"] == "afastado"


def test_inexistentes_devolvem_none_ou_lista_vazia(sessao):
    assert buscar_lojista(sessao, "M99999") is None
    assert carteira_do_lojista(sessao, "M99999") is None
    assert buscar_conta_recebimento(sessao, "M99999") is None
    assert buscar_funcionario(sessao, "F9999") is None
    assert buscar_vendas(sessao, "M99999") == {"itens": [], "total": 0, "limite": 50}


def test_codigo_malicioso_e_so_um_valor(sessao):
    assert buscar_lojista(sessao, "M00001' OR '1'='1") is None
    assert buscar_vendas(sessao, "' OR 1=1 --")["total"] == 0


def test_aceita_engine_no_lugar_da_sessao(engine):
    assert buscar_lojista(engine, "M00001")["nome_fantasia"] == "Padaria Pão da Vila"
    assert buscar_funcionario(engine, "F0001")["cargo"] == "atendente_n1"


# --- falha "fora do ar" -------------------------------------------------------------------

CONSULTAS_POR_SISTEMA = [
    ("cadastro", lambda s: buscar_lojista(s, "M00001")),
    ("cadastro", lambda s: carteira_do_lojista(s, "M00001")),
    ("cadastro", lambda s: buscar_contatos(s, "M00001")),
    ("cadastro", lambda s: buscar_conta_recebimento(s, "M00001")),
    ("core", lambda s: buscar_vendas(s, "M00001")),
    ("core", lambda s: buscar_liquidacoes(s, "M00001")),
    ("cobranca", lambda s: buscar_faturas(s, "M00003")),
    ("crm", lambda s: buscar_chamados(s, "M00001")),
    ("crm", lambda s: buscar_interacoes(s, "M00001", "CH000001")),
    ("diretorio", lambda s: buscar_funcionario(s, "F0001")),
]


@pytest.mark.parametrize(("sistema", "consulta"), CONSULTAS_POR_SISTEMA)
def test_consulta_levanta_quando_o_sistema_esta_fora_do_ar(sessao, sistema, consulta):
    consulta(sessao)  # funciona antes
    ligar(sistema)
    with pytest.raises(SistemaIndisponivel) as erro:
        consulta(sessao)
    assert erro.value.sistema == sistema
    desligar(sistema)
    consulta(sessao)  # volta a funcionar


def test_falha_de_um_sistema_nao_afeta_os_outros(sessao):
    ligar("core")
    assert buscar_lojista(sessao, "M00001") is not None
    assert buscar_faturas(sessao, "M00003")["total"] > 0
    with pytest.raises(SistemaIndisponivel):
        buscar_vendas(sessao, "M00001")


def test_falha_pela_variavel_de_ambiente(sessao, monkeypatch):
    monkeypatch.setenv("MOCK_FALHAS", "crm, diretorio")
    assert fora_do_ar("crm") and fora_do_ar("diretorio") and not fora_do_ar("core")
    with pytest.raises(SistemaIndisponivel):
        buscar_chamados(sessao, "M00001")
    with pytest.raises(SistemaIndisponivel):
        buscar_funcionario(sessao, "F0001")
    assert buscar_vendas(sessao, "M00001")["total"] > 0


def test_nome_desconhecido_no_ambiente_e_ignorado_com_aviso(monkeypatch, caplog):
    monkeypatch.setenv("MOCK_FALHAS", "naoexiste")
    with caplog.at_level(logging.WARNING, logger="mock.falhas"):
        assert not any(fora_do_ar(s) for s in SISTEMAS)
    assert "desconhecido" in caplog.text


def test_ligar_sistema_desconhecido_e_erro():
    with pytest.raises(ValueError, match="desconhecido"):
        ligar("naoexiste")


def test_ligar_e_desligar_registram_horario_sem_conteudo(caplog):
    with caplog.at_level(logging.INFO, logger="mock.falhas"):
        ligar("core")
        desligar("core")
    mensagens = [r.getMessage() for r in caplog.records]
    assert len(mensagens) == 2
    assert "ligada" in mensagens[0] and "sistema=core" in mensagens[0]
    assert "desligada" in mensagens[1]
    assert all("horario=20" in m for m in mensagens)  # horário ISO (ano 20xx)


def test_mensagem_da_falha_nao_tem_detalhe_tecnico():
    ligar("cadastro")
    with pytest.raises(SistemaIndisponivel) as erro:
        buscar_lojista(None, "M00001")  # nem chega a tocar na sessão
    assert str(erro.value) == "sistema indisponível: cadastro"


# --- B1/B3 da crítica: interação amarrada ao lojista, motivo da falha, dias já calculados ---


def test_interacao_de_chamado_de_outro_lojista_nao_vem(sessao):
    chamado = buscar_chamados(sessao, "M00009")["itens"][0]["codigo"]
    assert buscar_interacoes(sessao, "M00009", chamado)["total"] >= 1
    assert buscar_interacoes(sessao, "M00001", chamado) == {"itens": [], "total": 0, "limite": 50}


def test_liquidacao_que_falhou_traz_o_motivo(sessao):
    itens = buscar_liquidacoes(sessao, "M00001")["itens"]
    falhou = [i for i in itens if i["situacao"] == "falhou"]
    assert [i["motivo_falha"] for i in falhou] == ["conta_invalida"]
    assert all(i["motivo_falha"] is None for i in itens if i["situacao"] == "paga")


def test_faturas_e_chamados_trazem_os_dias_calculados_a_partir_de_hoje_do_mock(sessao):
    faturas = buscar_faturas(sessao, "M00003")["itens"]
    saldo = next(f for f in faturas if f["tipo"] == "saldo_negativo")
    assert saldo["dias_em_atraso"] == 40  # vencido em 05/09/2026, hoje do mock 15/10/2026
    assert all(f["dias_em_atraso"] is None for f in faturas if f["situacao"] == "paga")
    chamado = buscar_chamados(sessao, "M00001")["itens"][0]
    assert chamado["aberto_por"] == "sistema" and chamado["dias_em_aberto"] == 1
    fechados = [c for c in buscar_chamados(sessao, "M00001")["itens"] if c["situacao"] == "fechado"]
    assert fechados and all(c["dias_em_aberto"] is None for c in fechados)


def test_todo_campo_devolvido_pelas_consultas_esta_classificado(sessao):
    """Contrato da máscara: campo devolvido é restrito (CLASSIFICACAO_CAMPOS) ou liberado."""
    chamado = buscar_chamados(sessao, "M00009")["itens"][0]["codigo"]
    respostas = [
        buscar_lojista(sessao, "M00001"), carteira_do_lojista(sessao, "M00001"),
        buscar_conta_recebimento(sessao, "M00001"), buscar_funcionario(sessao, "F0001"),
        *buscar_contatos(sessao, "M00001")["itens"], *buscar_vendas(sessao, "M00001")["itens"],
        *buscar_liquidacoes(sessao, "M00001")["itens"], *buscar_faturas(sessao, "M00003")["itens"],
        *buscar_chamados(sessao, "M00001")["itens"],
        *buscar_interacoes(sessao, "M00009", chamado)["itens"],
    ]
    devolvidos = {campo for resposta in respostas for campo in resposta}
    nao_classificados = devolvidos - set(CLASSIFICACAO_CAMPOS) - CAMPOS_NAO_RESTRITOS
    assert not nao_classificados, sorted(nao_classificados)
    assert not set(CLASSIFICACAO_CAMPOS) & CAMPOS_NAO_RESTRITOS
