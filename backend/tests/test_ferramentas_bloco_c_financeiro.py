"""Ferramentas de leitura e cálculo do financeiro (bloco C): agenda, antecipação, conferência, contestações e acordos."""

import json
from datetime import date
from decimal import Decimal

import pytest
from ferramentas import dados_sinteticos, governanca, lojista
from mock import regras  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.falhas import ligar

from . import gabaritos as g
from .apoio_bloco_c import chamar, resultado, usuario
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

NEGADA = ("erro", "permissao_negada")
BLOQUEADA = ("erro", "ferramenta_inexistente")
INVALIDO = ("erro", "parametro_invalido")
FORA_DO_AR = ("erro", "integracao_indisponivel")
LOJISTAS = [f"M{n:05d}" for n in range(1, 21)]


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


def atendente_pme(engine):
    return usuario_do_diretorio(engine, g.ATENDENTE_PME)


# --- consultar_agenda_recebiveis (cenários 1, 2 e 4) ---------------------------------------------


def test_agenda_do_cenario_4_resume_o_que_vai_cair_e_lista_da_data_mais_proxima(engine):
    resposta = chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA, "limite": 2}, atendente_pme(engine))
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert dados["agenda_futura"]["previsto"]["valor"] == g.C4_AGENDA_FUTURA_TEXTO
    assert dados["agenda_futura"]["antecipado"] == {"quantidade": 0, "valor": "R$ 0,00"}
    datas = [parcela["data_prevista"] for parcela in dados["parcelas"]]
    assert datas == sorted(datas) and datas[0] == g.C4_DATA_DO_CREDITO
    assert dados["truncado"] is True and dados["janela_dias"] == 90


def test_agenda_mostra_o_valor_retido_pelo_chargeback_do_cenario_2(engine):
    argumentos = {"id_cliente": g.C2_LOJISTA, "situacao": "retido"}
    dados = chamar("consultar_agenda_recebiveis", argumentos, usuario(engine, "supervisor_atendimento"))["dados"]
    assert [(p["id_venda"], p["valor"]) for p in dados["parcelas"]] == [(g.C2_VENDA, g.C2_VALOR_RETIDO_TEXTO)]
    assert dados["agenda_futura"]["retido"]["valor"] == g.C2_VALOR_RETIDO_TEXTO


def test_agenda_fora_da_carteira_e_lojista_inexistente_tem_a_mesma_resposta(engine):
    ana = usuario(engine, "atendente_n1")
    fora = chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA}, ana)
    inexistente = chamar("consultar_agenda_recebiveis", {"id_cliente": "M00099"}, ana)
    assert fora == inexistente and resultado(fora) == NEGADA
    assert fora["mensagem"] == g.MENSAGEM_FORA_DA_CARTEIRA


def test_agenda_respeita_a_janela_de_90_dias_do_n1(engine):
    argumentos = {"id_cliente": g.C4_LOJISTA, "data_inicio": "2026-01-01", "data_fim": "2026-03-01"}
    assert resultado(chamar("consultar_agenda_recebiveis", argumentos, atendente_pme(engine))) == NEGADA
    assert resultado(chamar("consultar_agenda_recebiveis", argumentos, usuario(engine, "analista_recebiveis"))) == ("ok", None)


@pytest.mark.parametrize(
    "argumentos",
    [
        {"situacao": "sumido"},
        {"limite": 51},
        {"limite": 0},
        {"data_inicio": "2026-11-01", "data_fim": "2026-10-20"},
        {"data_inicio": "15/10/2026"},
    ],
)
def test_agenda_recusa_parametro_invalido(engine, argumentos):
    resposta = chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA} | argumentos, atendente_pme(engine))
    assert resultado(resposta) == INVALIDO


@pytest.mark.parametrize("cargo", ["analista_disputas", "analista_ouvidoria", "auditor_compliance"])
def test_agenda_nao_aparece_para_quem_nao_ve_agenda(engine, cargo):
    resposta = chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA}, usuario(engine, cargo))
    assert resultado(resposta) == BLOQUEADA


# --- simular_antecipacao (cenário 4) --------------------------------------------------------------


def test_simulacao_do_cenario_4_bate_com_o_gabarito_e_nao_antecipa_nada(engine):
    pme = atendente_pme(engine)
    resposta = chamar("simular_antecipacao", {"id_cliente": g.C4_LOJISTA}, pme)
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert (dados["pode_antecipar"], dados["motivos_de_recusa"]) == (True, [])
    assert dados["simulacao"] == g.C4_SIMULACAO
    assert "especialista N2" in dados["aviso"]
    agenda = chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA}, pme)["dados"]["agenda_futura"]
    assert agenda["antecipado"]["quantidade"] == 0 and agenda["previsto"]["valor"] == g.C4_AGENDA_FUTURA_TEXTO


def test_simulacao_recusada_explica_o_motivo_e_nao_traz_valor(engine):
    resposta = chamar("simular_antecipacao", {"id_cliente": g.C4_LOJISTA_RECUSADO}, usuario(engine, "atendente_n1"))
    dados = resposta["dados"]
    assert (dados["pode_antecipar"], dados["simulacao"]) == (False, None)
    assert dados["motivos_de_recusa"] == [g.C4_MOTIVO_DA_RECUSA_TEXTO]


def test_simulacao_e_recusada_com_conta_de_recebimento_invalida_do_cenario_1(engine):
    for cargo in ("atendente_n1", "analista_recebiveis"):
        dados = chamar("simular_antecipacao", {"id_cliente": g.C1_LOJISTA}, usuario(engine, cargo))["dados"]
        assert (dados["pode_antecipar"], dados["simulacao"]) == (False, None)
        assert dados["motivos_de_recusa"] == ["a conta de recebimento está inválida e o dinheiro fica retido"]


def test_simulacao_com_conta_em_verificacao_continua_recusada_e_a_do_cenario_4_continua_valendo(engine):
    dados = chamar("simular_antecipacao", {"id_cliente": "M00019"}, usuario(engine, "analista_recebiveis"))["dados"]
    assert dados["motivos_de_recusa"] == ["a conta de recebimento está em verificação"]
    assert chamar("simular_antecipacao", {"id_cliente": g.C4_LOJISTA}, atendente_pme(engine))["dados"]["pode_antecipar"]


def test_simulacao_fora_da_carteira_e_negada_e_id_errado_e_invalido(engine):
    ana = usuario(engine, "atendente_n1")
    assert resultado(chamar("simular_antecipacao", {"id_cliente": g.C4_LOJISTA}, ana)) == NEGADA
    assert resultado(chamar("simular_antecipacao", {"id_cliente": "M4"}, ana)) == INVALIDO


# --- conferir_liquidacoes (KAN-14, caso 5; cenário 1) ---------------------------------------------


def test_conferencia_do_cenario_1_aponta_a_liquidacao_que_falhou(engine):
    resposta = chamar("conferir_liquidacoes", {"id_cliente": g.C1_LOJISTA}, usuario(engine, "atendente_n1"))
    assert resultado(resposta) == ("ok", None)
    [divergencia] = resposta["dados"]["divergencias"]
    assert divergencia["data"] == g.C1_LIQUIDACAO_DATA and divergencia["situacao"] == g.C1_LIQUIDACAO_SITUACAO
    assert (divergencia["agenda"], divergencia["pago"]) == (g.C1_LIQUIDACAO_TEXTO, "R$ 0,00")
    assert divergencia["diferenca"] == "-" + g.C1_LIQUIDACAO_TEXTO
    assert divergencia["motivo_falha"] == "conta_invalida" and "N2" in divergencia["explicacao"]


def test_conferencia_do_kan_14_caso_5_acha_o_deposito_15_reais_abaixo(engine):
    resposta = chamar("conferir_liquidacoes", {"id_cliente": g.K14C5_LOJISTA}, usuario(engine, "analista_recebiveis"))
    [divergencia] = resposta["dados"]["divergencias"]
    assert divergencia["data"] == g.K14C5_DIA and divergencia["situacao"] == "paga"
    assert (divergencia["agenda"], divergencia["pago"]) == (g.K14C5_AGENDA_DO_DIA_TEXTO, g.K14C5_LIQUIDACAO_TEXTO)
    assert divergencia["diferenca"] == "-" + dados_sinteticos.reais(g.K14C5_DIFERENCA_CENTAVOS)
    assert "chamado de Recebimento" in divergencia["explicacao"]


def test_conferencia_de_lojista_sem_divergencia_devolve_lista_vazia(engine):
    dados = chamar("conferir_liquidacoes", {"id_cliente": g.C4_LOJISTA}, atendente_pme(engine))["dados"]
    assert dados["dias_conferidos"] > 0
    assert (dados["divergencias"], dados["total_de_divergencias"], dados["truncado"]) == ([], 0, False)


def test_conferencia_no_mundo_inteiro_acha_so_as_tres_divergencias_plantadas(engine):
    coordenador = usuario(engine, "coordenador_financeiro")
    periodo = {"data_inicio": "2026-01-01", "data_fim": "2026-10-14"}
    achadas = set()
    for codigo in LOJISTAS:
        dados = chamar("conferir_liquidacoes", {"id_cliente": codigo, "limite": 50} | periodo, coordenador)["dados"]
        achadas |= {(codigo, d["data"], d["diferenca"]) for d in dados["divergencias"]}
    assert achadas == {
        (g.C1_LOJISTA, g.C1_LIQUIDACAO_DATA, "-R$ 1.842,30"),
        (g.C9_LOJISTA, "2026-09-04", "-R$ 3,00"),
        (g.K14C5_LOJISTA, g.K14C5_DIA, "-R$ 15,00"),
    }


def test_conferencia_nunca_confere_o_dia_de_hoje(engine):
    argumentos = {"id_cliente": g.C1_LOJISTA, "data_inicio": "2026-10-15", "data_fim": "2026-10-15"}
    dados = chamar("conferir_liquidacoes", argumentos, usuario(engine, "analista_recebiveis"))["dados"]
    assert (dados["dias_conferidos"], dados["divergencias"]) == (0, [])


def test_conferencia_respeita_janela_e_ordem_das_datas(engine):
    ana = usuario(engine, "atendente_n1")
    antes_da_janela = {"id_cliente": g.C1_LOJISTA, "data_inicio": "2026-01-01"}
    assert resultado(chamar("conferir_liquidacoes", antes_da_janela, ana)) == NEGADA
    invertido = {"id_cliente": g.C1_LOJISTA, "data_inicio": "2026-10-10", "data_fim": "2026-10-01"}
    assert resultado(chamar("conferir_liquidacoes", invertido, ana)) == INVALIDO


@pytest.mark.parametrize("cargo", ["analista_cobranca", "analista_disputas", "analista_ouvidoria"])
def test_conferencia_e_so_de_quem_ve_agenda_e_liquidacao(engine, cargo):
    resposta = chamar("conferir_liquidacoes", {"id_cliente": g.C1_LOJISTA}, usuario(engine, cargo))
    assert resultado(resposta) == BLOQUEADA


# --- listar_contestacoes_cliente (cenários 2 e 10) ------------------------------------------------


def test_contestacao_do_cenario_2_traz_prazo_documentos_e_valor_retido(engine):
    resposta = chamar("listar_contestacoes_cliente", {"id_cliente": g.C2_LOJISTA}, usuario(engine, "analista_disputas"))
    assert resultado(resposta) == ("ok", None)
    [chargeback] = resposta["dados"]["chargebacks"]
    assert chargeback["codigo"] == g.C2_CHARGEBACK and chargeback["motivo"] == g.C2_MOTIVO_TEXTO
    assert (chargeback["prazo_defesa"], chargeback["dias_para_o_prazo"]) == (g.C2_PRAZO_DA_DEFESA, g.C2_DIAS_PARA_O_PRAZO)
    assert (chargeback["valor"], chargeback["valor_retido"]) == (g.C2_VALOR_TEXTO, g.C2_VALOR_RETIDO_TEXTO)
    assert tuple(chargeback["documentos_exigidos"]) == g.C2_DOCUMENTOS_EXIGIDOS
    assert resposta["dados"]["casos_pix"] == []


def test_contestacao_do_cenario_10_traz_o_caso_de_pix(engine):
    dados = chamar("listar_contestacoes_cliente", {"id_cliente": g.C10_LOJISTA}, usuario(engine, "analista_disputas"))["dados"]
    [caso] = dados["casos_pix"]
    assert (caso["codigo"], caso["id_venda"], caso["valor"]) == (g.C10_CASO_PIX, g.C10_VENDA, g.C10_VALOR_TEXTO)
    assert (caso["data_abertura"], caso["prazo_contestacao"]) == (g.C10_ABERTURA, g.C10_PRAZO_PARA_CONTESTAR)


@pytest.mark.parametrize("cargo", ["atendente_n1", "analista_cobranca", "analista_recebiveis", "analista_ouvidoria"])
def test_contestacao_e_so_de_quem_ve_disputa(engine, cargo):
    resposta = chamar("listar_contestacoes_cliente", {"id_cliente": g.C2_LOJISTA}, usuario(engine, cargo))
    assert resultado(resposta) == BLOQUEADA


def test_contestacao_do_n2_fica_na_carteira_do_time(engine):
    n2 = usuario(engine, "especialista_n2")
    fora = next(c for c in LOJISTAS if dados_sinteticos.carteira_do_lojista(c)["carteira"] not in n2.carteiras)
    assert resultado(chamar("listar_contestacoes_cliente", {"id_cliente": fora}, n2)) == NEGADA


# --- listar_acordos (onboarding 8) ----------------------------------------------------------------


def test_acordos_pendentes_do_onboarding_8_do_maior_para_o_menor(engine):
    argumentos = {"situacao": "pendente_aprovacao"}
    resposta = chamar("listar_acordos", argumentos, usuario(engine, "coordenador_financeiro"))
    assert resultado(resposta) == ("ok", None)
    acordos = resposta["dados"]["acordos"]
    assert tuple(a["codigo"] for a in acordos) == g.O8_PENDENTES_DO_MAIOR_PARA_O_MENOR
    assert tuple(a["valor_renegociado"] for a in acordos) == g.O8_VALORES_RENEGOCIADOS
    assert tuple(a["alcada"] for a in acordos) == g.O8_ALCADAS
    assert {a["id_aprovador"] for a in acordos} == {None}


def test_acordos_de_um_lojista_e_situacao_invalida(engine):
    cobranca = usuario(engine, "analista_cobranca")
    codigo, alcada, situacao = g.O8_ACORDO_NA_ALCADA_DA_ANALISTA
    todos = chamar("listar_acordos", {}, cobranca)["dados"]["acordos"]
    lojista_do_acordo = next(a["id_cliente"] for a in todos if a["codigo"] == codigo)
    do_lojista = chamar("listar_acordos", {"id_cliente": lojista_do_acordo}, cobranca)["dados"]["acordos"]
    assert {a["id_cliente"] for a in do_lojista} == {lojista_do_acordo}
    assert (codigo, alcada, situacao) in {(a["codigo"], a["alcada"], a["situacao"]) for a in do_lojista}
    assert resultado(chamar("listar_acordos", {"situacao": "aprovado"}, cobranca)) == INVALIDO


@pytest.mark.parametrize("cargo", ["atendente_n1", "supervisor_atendimento", "analista_disputas", "analista_recebiveis"])
def test_acordos_sao_so_da_cobranca_e_do_coordenador(engine, cargo):
    assert resultado(chamar("listar_acordos", {}, usuario(engine, cargo))) == BLOQUEADA


def test_acordos_sem_lojista_exigem_quem_ve_todas_as_carteiras(engine, monkeypatch):
    monkeypatch.setattr(lojista, "carteiras_do_escopo", lambda usuario: ("varejo",))
    resposta = chamar("listar_acordos", {}, usuario(engine, "analista_cobranca"))
    assert resultado(resposta) == INVALIDO and "id_cliente" in resposta["mensagem"]


# --- regras comuns: fora do ar e registro sem conteúdo --------------------------------------------


@pytest.mark.parametrize(
    ("sistema", "nome", "argumentos", "cargo"),
    [
        ("core", "consultar_agenda_recebiveis", {"id_cliente": g.C2_LOJISTA}, "coordenador_financeiro"),
        ("core", "conferir_liquidacoes", {"id_cliente": g.C1_LOJISTA}, "coordenador_financeiro"),
        ("disputas", "listar_contestacoes_cliente", {"id_cliente": g.C2_LOJISTA}, "coordenador_financeiro"),
        ("cobranca", "listar_acordos", {}, "coordenador_financeiro"),
    ],
)
def test_sistema_fora_do_ar_responde_integracao_indisponivel(engine, sistema, nome, argumentos, cargo):
    ligar(sistema)
    assert resultado(chamar(nome, argumentos, usuario(engine, cargo))) == FORA_DO_AR


def test_registro_nao_guarda_valor_nem_motivo_das_consultas(engine):
    coordenador = usuario(engine, "coordenador_financeiro")
    chamar("conferir_liquidacoes", {"id_cliente": g.C1_LOJISTA}, coordenador)
    chamar("simular_antecipacao", {"id_cliente": g.C4_LOJISTA}, coordenador)
    chamar("listar_contestacoes_cliente", {"id_cliente": g.C2_LOJISTA}, coordenador)
    registros = json.dumps(governanca.REGISTROS, ensure_ascii=False, default=str)
    assert len(governanca.REGISTROS) == 3
    for conteudo in ("R$", "conta_invalida", g.C2_CHARGEBACK, "2,99%"):
        assert conteudo not in registros, conteudo


# --- reais e calcular_parcelas (alçada pela regra do mock) ----------------------------------------


@pytest.mark.parametrize(("centavos", "texto"), [(184230, "R$ 1.842,30"), (-1500, "-R$ 15,00"), (0, "R$ 0,00"), (-7, "-R$ 0,07")])
def test_reais_escreve_negativo_com_o_sinal_antes(centavos, texto):
    assert dados_sinteticos.reais(centavos) == texto


def parcelas(engine, **argumentos):
    return chamar("calcular_parcelas", argumentos, usuario(engine, "analista_cobranca"))


def test_parcelas_acima_de_dez_mil_pedem_dupla_aprovacao(engine):
    dados = parcelas(engine, valor_total="12663.60", numero_parcelas=6)["dados"]
    assert dados["quem_aprova"] == "dupla_aprovacao" and "quem pede nunca aprova" in dados["motivo"]
    assert dados["entrada"] == "R$ 2.532,72" and len(dados["parcelas"]) == 6


def test_perdao_em_divida_acima_de_dois_mil_vai_para_o_coordenador(engine):
    dados = parcelas(
        engine, valor_total="2600", valor_principal="2400", perdao_encargos="200",
        numero_parcelas=4,
    )["dados"]
    assert dados["quem_aprova"] == "coordenador" and "perdoa multa e juros" in dados["motivo"]
    assert dados["valor_negociado"] == "R$ 2.400,00"
    pequena = parcelas(
        engine, valor_total="1900", valor_principal="1800", perdao_encargos="100",
        numero_parcelas=4,
    )["dados"]
    assert pequena["quem_aprova"] == "analista"


@pytest.mark.parametrize(
    "argumentos",
    [
        {"valor_principal": "2000"},  # acima do valor_total
        {"perdao_encargos": "50"},  # sem multa e juros para perdoar
        {"valor_principal": "900", "perdao_encargos": "150"},  # perdoa mais do que os encargos
    ],
)
def test_parcelas_recusam_principal_e_perdao_incoerentes(engine, argumentos):
    resposta = parcelas(engine, valor_total="1000", numero_parcelas=2, **argumentos)
    assert resultado(resposta) == INVALIDO


@pytest.mark.parametrize("numero_parcelas", [1, 6, 7, 12, 13])
@pytest.mark.parametrize("entrada_percentual", [Decimal(10), Decimal(20)])
@pytest.mark.parametrize("desconto", [Decimal(0), Decimal(5), Decimal(11)])
@pytest.mark.parametrize("valor_total", [Decimal("330.67"), Decimal(2500), Decimal(10500)])
def test_quem_aprova_e_sempre_a_regra_do_mock_e_o_motivo_nunca_vem_vazio(
    engine, numero_parcelas, entrada_percentual, desconto, valor_total
):
    dados = parcelas(
        engine, valor_total=str(valor_total), numero_parcelas=numero_parcelas,
        entrada_percentual=str(entrada_percentual), desconto_principal_percentual=str(desconto),
    )["dados"]
    total = int(valor_total * 100)
    desconto_centavos = int(total * desconto / 100)  # para baixo, como a ferramenta
    negociado = total - desconto_centavos
    entrada = -(-negociado * int(entrada_percentual) // 100)  # para cima, como a ferramenta
    esperado = regras.alcada_do_acordo(total, negociado, numero_parcelas, entrada, 0, desconto_centavos)
    assert dados["quem_aprova"] == esperado
    assert dados["motivo"] and not dados["motivo"].endswith(": .")


# --- período padrão: só data_fim, e a chamada sem argumento em qualquer dia da semana -----------------

SEMANA_DE_HOJES = [date(2026, 10, dia) for dia in range(12, 19)]  # segunda a domingo


def test_conferencia_so_com_data_fim_antiga_conta_30_dias_ate_ela(engine):
    argumentos = {"id_cliente": g.C4_LOJISTA, "data_fim": "2026-08-31"}
    resposta = chamar("conferir_liquidacoes", argumentos, usuario(engine, "analista_recebiveis"))
    assert resultado(resposta) == ("ok", None)
    assert resposta["dados"]["dias_conferidos"] > 0


def test_agenda_so_com_data_fim_no_passado_traz_os_30_dias_ate_ela(engine):
    argumentos = {"id_cliente": g.C4_LOJISTA, "data_fim": "2026-09-30", "limite": 30}
    resposta = chamar("consultar_agenda_recebiveis", argumentos, usuario(engine, "analista_recebiveis"))
    assert resultado(resposta) == ("ok", None)
    datas = [parcela["data_prevista"] for parcela in resposta["dados"]["parcelas"]]
    assert datas and min(datas) >= "2026-09-01" and max(datas) <= "2026-09-30"


def test_agenda_so_com_data_fim_no_futuro_continua_comecando_hoje(engine):
    argumentos = {"id_cliente": g.C4_LOJISTA, "data_fim": "2026-12-31", "limite": 30}
    datas = [p["data_prevista"] for p in chamar("consultar_agenda_recebiveis", argumentos, atendente_pme(engine))["dados"]["parcelas"]]
    assert datas and min(datas) >= regras.HOJE_DO_MOCK.isoformat()


@pytest.mark.parametrize("hoje", SEMANA_DE_HOJES, ids=lambda dia: dia.strftime("%a"))
def test_chamada_sem_argumento_nao_falha_em_nenhum_dia_da_semana(engine, monkeypatch, hoje):
    monkeypatch.setattr(dados_sinteticos, "HOJE_DO_MOCK", hoje)
    recebiveis = usuario(engine, "analista_recebiveis")
    assert resultado(chamar("conferir_liquidacoes", {"id_cliente": g.C4_LOJISTA}, recebiveis)) == ("ok", None)
    assert resultado(chamar("consultar_agenda_recebiveis", {"id_cliente": g.C4_LOJISTA}, recebiveis)) == ("ok", None)
    assert resultado(chamar("resumir_volume_chamados", {}, usuario(engine, "supervisor_atendimento"))) == ("ok", None)
