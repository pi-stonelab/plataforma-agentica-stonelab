"""Matriz cargo x ferramenta x lojista, janela de 90 dias e lojista inexistente (B1)."""

import pytest
from ferramentas import governanca
from mock.regras import CARGOS, HOJE_DO_MOCK

from .apoio_ferramentas import (
    CARGOS_COM_FERRAMENTA,
    CARGOS_TRANSVERSAIS,
    FUNCIONARIO_DO_CARGO,
    NEGADO_PELO_CATALOGO,
    executar,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

# Lojistas do mock: M00001 e M00003 são varejo, M00002 é pme, M00005 é contas_chave.
VAREJO, PME, CONTAS_CHAVE = "M00001", "M00002", "M00005"
NEGADA = ("erro", "permissao_negada")
OK = ("ok", None)


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


def resultado(resposta):
    return resposta["status"], resposta["tipo_erro"]


# Escrita à mão a partir de DOC-MOCK §8.2 (escopo) e do que o atendente N1 vê (KAN-69).
# Cada lista é o que o cargo recebe dos lojistas (varejo, pme, contas_chave) em consultar_cliente.
CLIENTE_ESPERADO = {
    "atendente_n1": (OK, NEGADA, NEGADA),  # time Varejo
    "especialista_n2": (OK, NEGADA, NEGADA),  # F0002 está no time Varejo
    "supervisor_atendimento": (OK, OK, OK),
    "analista_ouvidoria": (OK, OK, OK),
    "analista_cobranca": (OK, OK, OK),
    "analista_disputas": (OK, OK, OK),
    "analista_recebiveis": (OK, OK, OK),
    "coordenador_financeiro": (OK, OK, OK),
}
# consultar_transacoes_cliente exige a categoria "venda": cobrança, recebíveis e ouvidoria não têm.
COM_VENDA = {
    "atendente_n1", "especialista_n2", "supervisor_atendimento", "analista_disputas",
    "coordenador_financeiro",
}


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_consultar_cliente_por_cargo_e_lojista(engine, cargo):
    for codigo, esperado in zip((VAREJO, PME, CONTAS_CHAVE), CLIENTE_ESPERADO[cargo], strict=True):
        resposta = executar("consultar_cliente", {"id_cliente": codigo}, usuario(engine, cargo))
        assert resultado(resposta) == esperado, (cargo, codigo)


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_consultar_transacoes_por_cargo_e_lojista(engine, cargo):
    for codigo, esperado in zip((VAREJO, PME, CONTAS_CHAVE), CLIENTE_ESPERADO[cargo], strict=True):
        resposta = executar(
            "consultar_transacoes_cliente", {"id_cliente": codigo}, usuario(engine, cargo)
        )
        if cargo in COM_VENDA:
            assert resultado(resposta) == esperado, (cargo, codigo)
        else:
            assert resposta == NEGADO_PELO_CATALOGO, (cargo, codigo)


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_ferramentas_sem_dado_de_lojista_servem_a_todos_os_cargos_com_ferramenta(engine, cargo):
    u = usuario(engine, cargo)
    assert executar("calcular_multa_atraso", {"valor_fatura": 320, "dias_atraso": 40}, u)["status"] == "ok"
    assert executar("consultar_endereco_cep", {"cep": "01310-100"}, u)["status"] == "ok"
    pedido = {"nome_sugerido": "ferramenta_nova", "descricao": "d"}
    assert executar("solicitar_ferramenta_ausente", pedido, u)["status"] == "ok"


@pytest.mark.parametrize("cargo", CARGOS_TRANSVERSAIS)
def test_auditor_e_admin_nao_usam_nenhuma_ferramenta_de_dado(engine, cargo):
    u = usuario(engine, cargo)
    for nome in ("consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso"):
        assert executar(nome, {"id_cliente": VAREJO}, u) == NEGADO_PELO_CATALOGO


def test_especialista_de_contas_chave_ve_a_carteira_do_time_dele(engine):
    u = governanca.usuario_do_cargo("F0003", "especialista_n2", ("contas_chave",))
    assert resultado(executar("consultar_cliente", {"id_cliente": CONTAS_CHAVE}, u)) == OK
    assert resultado(executar("consultar_cliente", {"id_cliente": VAREJO}, u)) == NEGADA


def test_cargo_com_escopo_de_time_e_time_sem_carteira_nao_ve_ninguem(engine):
    sem_carteira = governanca.usuario_do_cargo("F0001", "atendente_n1", ())
    assert resultado(executar("consultar_cliente", {"id_cliente": VAREJO}, sem_carteira)) == NEGADA


def test_carteira_do_usuario_vem_do_diretorio_do_mock(engine):
    assert usuario(engine, "atendente_n1").carteiras == ("varejo",)
    assert usuario(engine, "coordenador_financeiro").carteiras == ()
    assert set(CARGOS) == set(FUNCIONARIO_DO_CARGO)


# --- lojista inexistente == fora do escopo (A-15, O13) ----------------------------------------


@pytest.mark.parametrize("ferramenta", ["consultar_cliente", "consultar_transacoes_cliente"])
def test_lojista_inexistente_e_fora_do_escopo_dao_a_mesma_resposta(engine, ferramenta):
    ana = usuario(engine, "atendente_n1")
    fora = executar(ferramenta, {"id_cliente": CONTAS_CHAVE}, ana)
    inexistente = executar(ferramenta, {"id_cliente": "M99999"}, ana)
    assert fora == inexistente
    assert resultado(fora) == NEGADA
    # a resposta não revela nada do lojista fora do escopo
    assert "Clínica" not in str(fora)


def test_quem_ve_todas_as_carteiras_recebe_nao_encontrado_para_codigo_inexistente(engine):
    coordenador = usuario(engine, "coordenador_financeiro")
    resposta = executar("consultar_cliente", {"id_cliente": "M99999"}, coordenador)
    assert resultado(resposta) == ("erro", "nao_encontrado")


@pytest.mark.parametrize(
    "codigo",
    ["M00001'; DROP TABLE lojistas;--", "M00001' OR '1'='1", "M0000%", "m00001", "M0000_", ""],
)
def test_codigo_malformado_e_recusado_antes_de_tocar_o_banco(engine, codigo):
    ana = usuario(engine, "atendente_n1")
    resposta = executar("consultar_cliente", {"id_cliente": codigo}, ana)
    assert resultado(resposta) == ("erro", "parametro_invalido")


# --- janela de 90 dias (KAN-69), com HOJE_DO_MOCK = 15/10/2026 --------------------------------


def test_janela_de_90_dias_so_vale_para_o_atendente_n1(engine):
    assert HOJE_DO_MOCK.isoformat() == "2026-10-15"
    comecou = {cargo: governanca.inicio_da_janela(usuario(engine, cargo)) for cargo in CARGOS_COM_FERRAMENTA}
    assert comecou["atendente_n1"].isoformat() == "2026-07-17"
    assert [cargo for cargo, inicio in comecou.items() if inicio is not None] == ["atendente_n1"]


def test_janela_dia_90_passa_e_dia_91_e_negado_e_nao_vira_lista_vazia(engine):
    ana = usuario(engine, "atendente_n1")
    pedido = {"id_cliente": VAREJO}
    dia_90 = executar("consultar_transacoes_cliente", {**pedido, "data_inicio": "2026-07-17"}, ana)
    dia_91 = executar("consultar_transacoes_cliente", {**pedido, "data_inicio": "2026-07-16"}, ana)
    fim_fora = executar("consultar_transacoes_cliente", {**pedido, "data_fim": "2026-07-16"}, ana)
    assert resultado(dia_90) == OK
    assert resultado(dia_91) == NEGADA and dia_91["dados"] is None
    assert resultado(fim_fora) == NEGADA


def test_sem_data_inicio_o_atendente_n1_recebe_so_a_janela(engine):
    ana = usuario(engine, "atendente_n1")
    dados = executar("consultar_transacoes_cliente", {"id_cliente": VAREJO, "limite": 50}, ana)["dados"]
    datas = [venda["data_hora"][:10] for venda in dados["transacoes"]]
    assert datas and min(datas) >= "2026-07-17"
    assert dados["janela_dias"] == 90


def test_supervisor_nao_tem_janela(engine):
    supervisor = usuario(engine, "supervisor_atendimento")
    resposta = executar(
        "consultar_transacoes_cliente",
        {"id_cliente": VAREJO, "data_inicio": "2026-01-01", "data_fim": "2026-06-30"},
        supervisor,
    )
    assert resultado(resposta) == OK and resposta["dados"]["janela_dias"] is None
    assert resposta["dados"]["total_encontrado"] > 0


def test_janela_usa_hoje_do_mock_e_nao_a_data_do_sistema(engine, monkeypatch):
    monkeypatch.setattr("mock.regras.HOJE_DO_MOCK", HOJE_DO_MOCK.replace(day=14))
    ana = usuario(engine, "atendente_n1")
    assert governanca.inicio_da_janela(ana).isoformat() == "2026-07-16"
