"""Ferramentas de indicadores e do dicionário de dados (bloco C): relatório, chamados por fila, taxa de chargeback,
ROI e DataHub, com o mundo do mock de verdade em memória."""

import json
from datetime import date

import pytest
from ferramentas import dados_sinteticos, governanca
from mock import falhas  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)

from . import gabaritos as g
from .apoio_bloco_c import chamar, resultado, usuario
from .apoio_ferramentas import limpar_estado, mundo_do_mock

BLOQUEADA = ("erro", "ferramenta_inexistente")
INVALIDO = ("erro", "parametro_invalido")
FORA_DO_AR = ("erro", "integracao_indisponivel")
NAO_ENCONTRADO = ("erro", "nao_encontrado")
FINANCEIRO = ("analista_cobranca", "analista_disputas", "analista_recebiveis", "coordenador_financeiro")
ATENDIMENTO = ("atendente_n1", "especialista_n2", "supervisor_atendimento", "analista_ouvidoria")
DATAHUB = ("buscar_conjuntos_dados", "consultar_esquema_conjunto", "consultar_responsavel_conjunto",
           "consultar_linhagem_conjunto")


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


# --- resumir_receita_periodo (KAN-14, caso de uso 4) ------------------------------------------


def test_relatorio_da_semana_bate_com_o_gabarito_do_caso_4(engine):
    inicio, fim = g.K4_SEMANA
    resposta = chamar("resumir_receita_periodo", {"data_inicio": inicio, "data_fim": fim},
                      usuario(engine, "coordenador_financeiro"))
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert {chave: dados[chave] for chave in g.K4_RESUMO_DA_SEMANA} == g.K4_RESUMO_DA_SEMANA
    assert (dados["data_inicio"], dados["data_fim"]) == g.K4_SEMANA
    assert "ontem" in dados["aviso"]
    soma_mdr = sum(int(m["receita_mdr"].replace("R$ ", "").replace(".", "").replace(",", ""))
                   for m in dados["vendas_por_modalidade"])
    assert dados["vendas_total"]["receita_mdr"] == dados["receitas"]["mdr"] == dados_sinteticos.reais(soma_mdr)


def test_relatorio_sem_datas_e_a_ultima_semana_ate_ontem(engine):
    dados = chamar("resumir_receita_periodo", {}, usuario(engine, "analista_cobranca"))["dados"]
    assert (dados["data_inicio"], dados["data_fim"]) == g.K4_SEMANA


def test_relatorio_nao_inclui_a_venda_de_hoje_do_cenario_11(engine):
    hoje = dados_sinteticos.HOJE_DO_MOCK.isoformat()
    dados = chamar("resumir_receita_periodo", {"data_inicio": hoje, "data_fim": hoje},
                   usuario(engine, "coordenador_financeiro"))["dados"]
    assert dados["data_corte"] < hoje and dados["vendas_total"]["valor_bruto"] == "R$ 0,00"
    assert g.C11_VENDA_RECENTE_TEXTO not in json.dumps(dados, ensure_ascii=False)


@pytest.mark.parametrize(
    "argumentos",
    [{"data_inicio": "2026-10-14", "data_fim": "2026-10-08"}, {"data_inicio": "2026-06-01", "data_fim": "2026-10-14"}],
)
def test_relatorio_recusa_periodo_invertido_ou_longo_demais(engine, argumentos):
    assert resultado(chamar("resumir_receita_periodo", argumentos, usuario(engine, "coordenador_financeiro"))) == INVALIDO


@pytest.mark.parametrize("cargo", ATENDIMENTO)
def test_relatorio_da_stone_e_so_do_financeiro(engine, cargo):
    assert resultado(chamar("resumir_receita_periodo", {}, usuario(engine, cargo))) == BLOQUEADA


# --- resumir_volume_chamados (cenário 11 e onboarding 4) ---------------------------------------


def test_criticos_fora_do_prazo_na_semana_pela_base_analitica(engine):
    resposta = chamar("resumir_volume_chamados", {"prioridade": "crítica"}, usuario(engine, "supervisor_atendimento"))
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert dados["data_inicio"] == g.C11_INICIO_DA_SEMANA.isoformat()
    assert dados["total"]["quantidade_estourados"] == g.C11_CRITICOS_FORA_DO_PRAZO_NA_BASE
    assert dados["total"]["quantidade_estourados"] < g.C11_CRITICOS_FORA_DO_PRAZO_NO_CRM  # o de hoje só no CRM
    assert "CRM" in dados["aviso"] and dados["data_corte"] == "2026-10-14"


def test_volume_soma_as_filas_e_recusa_prioridade_desconhecida(engine):
    supervisor = usuario(engine, "supervisor_atendimento")
    dados = chamar("resumir_volume_chamados", {}, supervisor)["dados"]
    for chave in ("quantidade_abertos", "quantidade_resolvidos", "quantidade_estourados"):
        assert dados["total"][chave] == sum(fila[chave] for fila in dados["filas"])
    assert resultado(chamar("resumir_volume_chamados", {"prioridade": "urgente"}, supervisor)) == INVALIDO


@pytest.mark.parametrize(("cargo", "alcanca"), [
    ("supervisor_atendimento", True), ("especialista_n2", True), ("atendente_n1", False),
    ("analista_ouvidoria", False), ("coordenador_financeiro", False),
])
def test_volume_de_chamados_e_do_n2_do_atendimento(engine, cargo, alcanca):
    esperado = ("ok", None) if alcanca else BLOQUEADA
    assert resultado(chamar("resumir_volume_chamados", {}, usuario(engine, cargo))) == esperado


# --- consultar_taxa_contestacao_mensal ------------------------------------------------------


def test_taxa_mensal_traz_os_ultimos_seis_meses_e_o_limite(engine):
    resposta = chamar("consultar_taxa_contestacao_mensal", {}, usuario(engine, "coordenador_financeiro"))
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert [m["mes"] for m in dados["meses"]] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert all(isinstance(m["taxa_chargeback_percentual"], float) for m in dados["meses"])


def test_taxa_mensal_e_so_o_total_da_stone_e_nao_a_do_lojista_do_cenario_2(engine):
    mes, pontos_do_lojista = g.C2_TAXA_DE_CHARGEBACK_DO_MES_DA_VENDA
    dados = chamar("consultar_taxa_contestacao_mensal", {"mes_inicio": mes, "mes_fim": mes},
                   usuario(engine, "coordenador_financeiro"))["dados"]
    assert dados["meses"][0]["taxa_chargeback_percentual"] != dados_sinteticos.taxa_percentual(pontos_do_lojista)
    assert "id_cliente" not in json.dumps(dados) and "M000" not in json.dumps(dados)


@pytest.mark.parametrize(
    "argumentos",
    [{"mes_fim": "2026-13"}, {"mes_inicio": "10/2026"}, {"mes_inicio": "2026-10", "mes_fim": "2026-05"},
     {"mes_inicio": "2023-01", "mes_fim": "2026-10"}],
)
def test_taxa_mensal_recusa_mes_fora_do_formato_invertido_ou_longo(engine, argumentos):
    resposta = chamar("consultar_taxa_contestacao_mensal", argumentos, usuario(engine, "coordenador_financeiro"))
    assert resultado(resposta) == INVALIDO


@pytest.mark.parametrize("cargo", ("analista_cobranca", "analista_disputas", "analista_recebiveis", "supervisor_atendimento"))
def test_taxa_mensal_e_so_do_coordenador(engine, cargo):
    assert resultado(chamar("consultar_taxa_contestacao_mensal", {}, usuario(engine, cargo))) == BLOQUEADA


# --- base analítica fora do ar ou desatualizada ------------------------------------------------


@pytest.mark.parametrize(("nome", "cargo"), [
    ("resumir_receita_periodo", "coordenador_financeiro"),
    ("resumir_volume_chamados", "supervisor_atendimento"),
    ("consultar_taxa_contestacao_mensal", "coordenador_financeiro"),
])
def test_base_analitica_fora_do_ar(engine, nome, cargo):
    falhas.ligar("analitica")
    assert resultado(chamar(nome, {}, usuario(engine, cargo))) == FORA_DO_AR


def test_base_desatualizada_mostra_o_corte_atrasado(engine):
    falhas.ligar("analitica", falhas.DESATUALIZADO)
    dados = chamar("resumir_receita_periodo", {}, usuario(engine, "coordenador_financeiro"))["dados"]
    assert dados["data_corte"] == "2026-10-11"


# --- calcular_roi ------------------------------------------------------------------------------


def test_roi_com_a_conta_feita_a_mao(engine):
    argumentos = {"horas_economizadas_por_mes": "40", "custo_hora": "50", "custo_mensal_agente": "300",
                  "custo_implantacao": "2000"}
    dados = chamar("calcular_roi", argumentos, usuario(engine, "atendente_n1"))["dados"]
    # economia 40 h x R$ 50 = R$ 2.000/mês; custo 12 x R$ 300 + R$ 2.000 = R$ 5.600; ganho 12 x R$ 2.000 = R$ 24.000
    assert dados == {
        "meses": 12, "economia_mensal": "R$ 2.000,00", "custo_mensal": "R$ 300,00",
        "ganho_liquido_mensal": "R$ 1.700,00", "ganho_total": "R$ 24.000,00", "custo_total": "R$ 5.600,00",
        "roi_percentual": 328.6, "payback_meses": 2, "se_paga": True,
    }


def test_roi_que_nunca_se_paga_e_custo_zero(engine):
    ana = usuario(engine, "atendente_n1")
    caro = chamar("calcular_roi", {"horas_economizadas_por_mes": "2", "custo_hora": "30", "custo_mensal_agente": "500",
                                   "custo_implantacao": "1000"}, ana)["dados"]
    assert (caro["payback_meses"], caro["se_paga"]) == (None, False) and caro["roi_percentual"] < 0
    gratis = chamar("calcular_roi", {"horas_economizadas_por_mes": "10", "custo_hora": "40",
                                     "custo_mensal_agente": "0"}, ana)["dados"]
    assert (gratis["roi_percentual"], gratis["payback_meses"], gratis["se_paga"]) == (None, 0, True)


@pytest.mark.parametrize("argumentos", [
    {"horas_economizadas_por_mes": "-1", "custo_hora": "50", "custo_mensal_agente": "300"},
    {"horas_economizadas_por_mes": "10", "custo_hora": "50", "custo_mensal_agente": "300", "meses": 61},
    {"horas_economizadas_por_mes": "10", "custo_hora": "20000000", "custo_mensal_agente": "300"},
    {"horas_economizadas_por_mes": "10", "custo_hora": "50"},
])
def test_roi_recusa_valores_fora_das_faixas_e_parametro_faltando(engine, argumentos):
    assert resultado(chamar("calcular_roi", argumentos, usuario(engine, "analista_ouvidoria"))) == INVALIDO


# --- dicionário de dados (DataHub) -------------------------------------------------------------


def test_busca_de_conjuntos_por_termo_e_por_sistema(engine):
    ana = usuario(engine, "atendente_n1")
    dados = chamar("buscar_conjuntos_dados", {"termo": "chargeback"}, ana)["dados"]
    tabelas = {c["tabela"] for c in dados["conjuntos"]}
    assert "chargebacks" in tabelas and "analitica_contestacoes_mensais" in tabelas
    disputas = chamar("buscar_conjuntos_dados", {"sistema": "disputas"}, ana)["dados"]["conjuntos"]
    assert {c["tabela"] for c in disputas} == {"chargebacks", "casos_pix"}
    assert all(c["nome_do_sistema"] == "Disputas" for c in disputas)
    assert resultado(chamar("buscar_conjuntos_dados", {"sistema": "bigquery"}, ana)) == INVALIDO


def test_esquema_marca_as_colunas_restritas_e_nao_le_dado(engine):
    dados = chamar("consultar_esquema_conjunto", {"conjunto": "contatos_lojista"}, usuario(engine, "atendente_n1"))["dados"]
    restritas = {c["coluna"] for c in dados["colunas"] if c["restrita"]}
    assert {"nome", "cpf", "telefone", "email"} <= restritas
    assert "***" not in json.dumps(dados, ensure_ascii=False)  # o dicionário não sai mascarado


def test_responsavel_e_o_sistema_dono(engine):
    dados = chamar("consultar_responsavel_conjunto", {"conjunto": "faturas"}, usuario(engine, "analista_cobranca"))["dados"]
    assert (dados["sistema"], dados["nome_do_sistema"]) == ("cobranca", "Cobrança")


def test_linhagem_tem_origem_e_derivados_coerentes(engine):
    ana = usuario(engine, "atendente_n1")
    vendas = chamar("consultar_linhagem_conjunto", {"conjunto": "vendas"}, ana)["dados"]
    assert vendas["origem"] == [] and "analitica_vendas_diarias" in vendas["derivados"]
    diaria = chamar("consultar_linhagem_conjunto", {"conjunto": "analitica_vendas_diarias"}, ana)["dados"]
    assert "vendas" in diaria["origem"]


@pytest.mark.parametrize("nome", DATAHUB[1:])
def test_conjunto_inexistente_e_nao_encontrado(engine, nome):
    assert resultado(chamar(nome, {"conjunto": "tabela_que_nao_existe"}, usuario(engine, "atendente_n1"))) == NAO_ENCONTRADO


@pytest.mark.parametrize("cargo", ATENDIMENTO + FINANCEIRO)
def test_dicionario_e_roi_valem_para_todo_cargo_com_area(engine, cargo):
    pessoa = usuario(engine, cargo)
    assert resultado(chamar("buscar_conjuntos_dados", {}, pessoa)) == ("ok", None)
    roi = {"horas_economizadas_por_mes": "1", "custo_hora": "1", "custo_mensal_agente": "1"}
    assert resultado(chamar("calcular_roi", roi, pessoa)) == ("ok", None)


@pytest.mark.parametrize("cargo", ("auditor_compliance", "admin_plataforma"))
def test_quem_nao_usa_ferramentas_nao_alcanca_nenhuma_do_grupo(engine, cargo):
    pessoa = usuario(engine, cargo)
    for nome in (*DATAHUB, "calcular_roi", "resumir_receita_periodo"):
        assert resultado(chamar(nome, {}, pessoa))[0] == "erro"


def test_registro_das_consultas_nao_guarda_valor_nem_nome_de_tabela(engine):
    chamar("resumir_receita_periodo", {}, usuario(engine, "coordenador_financeiro"))
    chamar("consultar_esquema_conjunto", {"conjunto": "contatos_lojista"}, usuario(engine, "atendente_n1"))
    registros = json.dumps(governanca.REGISTROS, ensure_ascii=False, default=str)
    assert len(governanca.REGISTROS) == 2
    for conteudo in ("R$", "contatos_lojista", g.K4_RESUMO_DA_SEMANA["resultado"]):
        assert conteudo not in registros, conteudo


def test_hoje_do_mock_e_o_que_as_datas_padrao_usam():
    assert dados_sinteticos.HOJE_DO_MOCK == date(2026, 10, 15)


# --- consultar_taxa_contestacao_cliente (limite de 1% é por lojista, DOC-MOCK §7.6) ---------------------


def taxa_do_lojista(engine, cargo, **argumentos):
    return chamar("consultar_taxa_contestacao_cliente", argumentos, usuario(engine, cargo))


def test_taxa_do_lojista_aponta_o_mes_acima_do_limite_do_cenario_2(engine):
    resposta = taxa_do_lojista(engine, "analista_disputas", id_cliente=g.C2_LOJISTA, mes_inicio="2026-09", mes_fim="2026-09")
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert dados["limite_de_monitoramento_percentual"] == 1.0 and dados["meses_acima_do_limite"] == ["2026-09"]
    assert dados["meses"] == [
        {"mes": "2026-09", "quantidade_vendas_cartao": 5, "quantidade_chargebacks": 1,
         "taxa_chargeback_percentual": 20.0, "acima_do_limite": True}
    ]


def test_taxa_do_lojista_sem_chargeback_nao_passa_do_limite(engine):
    dados = taxa_do_lojista(engine, "analista_disputas", id_cliente="M00004")["dados"]
    assert dados["meses_acima_do_limite"] == [] and not any(mes["acima_do_limite"] for mes in dados["meses"])


def test_taxa_do_lojista_respeita_a_carteira_do_n2(engine):
    n2 = usuario(engine, "especialista_n2")
    fora = next(c for c in (f"M{n:05d}" for n in range(1, 21)) if dados_sinteticos.carteira_do_lojista(c)["carteira"] not in n2.carteiras)
    resposta = chamar("consultar_taxa_contestacao_cliente", {"id_cliente": fora}, n2)
    assert resultado(resposta) == ("erro", "permissao_negada")
    inexistente = chamar("consultar_taxa_contestacao_cliente", {"id_cliente": "M00099"}, n2)
    assert resposta == inexistente


@pytest.mark.parametrize("cargo", ["atendente_n1", "analista_cobranca", "analista_recebiveis", "analista_ouvidoria"])
def test_taxa_do_lojista_e_so_de_quem_ve_disputa(engine, cargo):
    assert resultado(taxa_do_lojista(engine, cargo, id_cliente=g.C2_LOJISTA)) == BLOQUEADA


def test_taxa_da_stone_nao_traz_limite_nem_diz_que_passou_dele(engine):
    dados = chamar("consultar_taxa_contestacao_mensal", {}, usuario(engine, "coordenador_financeiro"))["dados"]
    texto = json.dumps(dados)
    assert "limite" not in texto and "acima" not in texto
    assert dados["tendencia"] in {"subindo", "caindo", "estavel"}
    assert all(isinstance(mes["taxa_chargeback_percentual"], float) for mes in dados["meses"])
