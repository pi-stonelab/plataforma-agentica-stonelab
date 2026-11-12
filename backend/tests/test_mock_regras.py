"""Testes das regras por cargo, da classificação de campos e do banco do mock."""

import threading

import pytest
from mock.banco import apagar_tabelas, criar_engine, criar_tabelas
from mock.modelos import BaseMock, Lojista
from mock.regras import (
    CAMPOS_NAO_RESTRITOS,
    CARGOS,
    CATEGORIAS_DADO,
    CLASSIFICACAO_CAMPOS,
    HOJE_DO_MOCK,
    area_do_cargo,
    mdr_pontos_base,
    regra_do_cargo,
)
from sqlalchemy import Column, Integer, MetaData, String, Table, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

CARGOS_DO_MOCK = {
    "atendente_n1", "especialista_n2", "supervisor_atendimento", "analista_ouvidoria",
    "analista_cobranca", "analista_disputas", "analista_recebiveis", "coordenador_financeiro",
    "auditor_compliance", "admin_plataforma",
}


def test_hoje_do_mock_e_fixo():
    assert HOJE_DO_MOCK.isoformat() == "2026-10-15"
    assert HOJE_DO_MOCK.weekday() == 3  # quinta-feira (DOC-MOCK §11.1)


def test_os_dez_cargos_com_identificadores_exatos():
    assert set(CARGOS) == CARGOS_DO_MOCK


def test_atendente_n1_regra_do_doc_mock():
    regra = regra_do_cargo("atendente_n1")
    assert (regra.area, regra.perfil_padrao, regra.nivel_ferramenta) == (
        "atendimento", "Colaborador", "N1")
    assert regra.escopo_lojistas == "carteiras_do_time"
    assert regra.janela_dias == 90
    assert "liquidacao" in regra.categorias_dado  # decisão O4: cenário 1 exige


def test_so_o_atendente_n1_tem_janela():
    com_janela = {c for c, r in CARGOS.items() if r.janela_dias is not None}
    assert com_janela == {"atendente_n1"}


def test_admin_e_auditor_nao_tem_ferramenta_de_dado():
    for cargo, perfil in (("admin_plataforma", "AdminGlobal"), ("auditor_compliance", "Auditor")):
        regra = regra_do_cargo(cargo)
        assert regra.perfil_padrao == perfil
        assert regra.area is None and regra.nivel_ferramenta is None
        assert regra.escopo_lojistas == "nenhum"
        assert regra.categorias_dado == frozenset()


def test_valores_das_regras_sao_validos():
    for regra in CARGOS.values():
        assert regra.area in ("atendimento", "financeiro", None)
        assert regra.perfil_padrao in ("Colaborador", "Supervisor", "AdminGlobal", "Auditor")
        assert regra.nivel_ferramenta in ("N1", "N2", None)
        assert regra.escopo_lojistas in ("carteiras_do_time", "todas", "nenhum")
        assert regra.categorias_dado <= set(CATEGORIAS_DADO)


def test_escopo_financeiro_e_segregacao_de_funcoes():
    # Cobrança não vê liquidação (E6); recebíveis não vê conta de recebimento (§8.1).
    assert "liquidacao" not in CARGOS["analista_cobranca"].categorias_dado
    assert "conta_recebimento" not in CARGOS["analista_recebiveis"].categorias_dado
    for cargo in ("analista_cobranca", "analista_disputas", "analista_recebiveis"):
        assert CARGOS[cargo].escopo_lojistas == "todas"
        assert CARGOS[cargo].area == "financeiro"


@pytest.mark.parametrize("cargo", [None, "", "ATENDENTE_N1", "estagiario", 123, ["atendente_n1"]])
def test_cargo_desconhecido_devolve_none(cargo):
    assert regra_do_cargo(cargo) is None
    assert area_do_cargo(cargo) is None


def test_mdr_do_plano_essencial():
    assert mdr_pontos_base("essencial", "debito", 1) == 199
    assert mdr_pontos_base("essencial", "parcelado", 3) == 429
    assert mdr_pontos_base("essencial", "parcelado", 10) == 499
    assert mdr_pontos_base("essencial", "pix", 1) == 0


def test_classificacao_de_campos_aponta_para_colunas_reais():
    colunas = {coluna.name for tabela in BaseMock.metadata.sorted_tables for coluna in tabela.columns}
    assert set(CLASSIFICACAO_CAMPOS) <= colunas
    assert set(CLASSIFICACAO_CAMPOS.values()) <= {
        "nome", "cpf", "telefone", "email", "conta", "cartao", "texto_livre"}
    exigidos = {
        "nome": "nome", "cpf": "cpf", "telefone": "telefone", "email": "email",
        "conta": "conta", "agencia": "conta", "ultimos4": "cartao", "texto": "texto_livre",
        "resumo": "texto_livre",
    }
    assert CLASSIFICACAO_CAMPOS == exigidos


def test_nome_de_campo_restrito_nao_se_repete_com_campo_livre():
    # A chave é só o nome do campo: não pode haver coluna livre com o mesmo nome.
    assert not set(CLASSIFICACAO_CAMPOS) & CAMPOS_NAO_RESTRITOS


# --- banco -------------------------------------------------------------------------------


def test_engine_oculta_parametros_nos_erros():
    engine = criar_engine("sqlite://")
    criar_tabelas(engine)
    with pytest.raises(IntegrityError) as erro, engine.begin() as conexao:
        conexao.execute(
            Lojista.__table__.insert().values(
                codigo="M99999", nome_fantasia="VALOR-SECRETO-123", segmento="x", porte="ME",
                cidade="x", uf="RJ", carteira="varejo", situacao="situacao-invalida",
                data_entrada=HOJE_DO_MOCK,
            )
        )
    assert "VALOR-SECRETO-123" not in str(erro.value)


def test_sqlite_em_memoria_usa_pool_unico_e_serve_outra_thread():
    engine = criar_engine("sqlite://")
    assert isinstance(engine.pool, StaticPool)
    criar_tabelas(engine)
    resultado = []

    def contar():
        with engine.connect() as conexao:
            resultado.append(conexao.execute(select(Lojista.codigo)).all())

    thread = threading.Thread(target=contar)
    thread.start()
    thread.join()
    assert resultado == [[]]  # a outra thread enxerga as tabelas (não dá "no such table")


def test_apagar_tabelas_nao_toca_tabela_que_nao_e_do_mock():
    engine = criar_engine("sqlite://")
    outra_base = MetaData()
    usuarios = Table("usuarios", outra_base, Column("id", Integer, primary_key=True),
                     Column("login", String(20)))
    outra_base.create_all(engine)
    criar_tabelas(engine)
    with engine.begin() as conexao:
        conexao.execute(usuarios.insert().values(id=1, login="alguem"))

    apagar_tabelas(engine)

    nomes = set(inspect(engine).get_table_names())
    assert nomes == {"usuarios"}  # as do mock sumiram, a outra ficou
    with engine.connect() as conexao:
        assert conexao.execute(text("SELECT login FROM usuarios")).scalar_one() == "alguem"


def test_criar_tabelas_cria_so_as_tabelas_do_mock():
    engine = criar_engine("sqlite://")
    criar_tabelas(engine)
    assert set(inspect(engine).get_table_names()) == {
        "times", "funcionarios", "lojistas", "contatos_lojista", "contas_recebimento",
        "vendas", "liquidacoes", "faturas", "chamados", "interacoes",
    }
