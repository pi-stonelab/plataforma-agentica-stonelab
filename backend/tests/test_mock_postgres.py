"""O mesmo mundo do mock no Postgres e no SQLite, e o SQL pronto de mock/sql/postgres/.

Só roda com `MOCK_TESTE_POSTGRES_URL` (dono de um banco só do mock, ver `mock/CLAUDE.md`). O teste do
papel só de leitura pede também `MOCK_TESTE_POSTGRES_LEITURA_URL`: um banco montado como o Docker
monta (os três arquivos de mock/sql/postgres/), que este teste nunca altera.
Sem as variáveis, os testes são pulados e a suíte normal segue no SQLite em memória.
"""

import os
from datetime import datetime

import pytest
from mock import exportar  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import apagar_tabelas, criar_engine
from mock.gerar import recriar, verificar
from mock.modelos import Interacao
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from .apoio_ferramentas import url_do_postgres_de_teste
from .test_mock_gerar import _conteudo_do_banco

URL_POSTGRES = url_do_postgres_de_teste()
URL_LEITURA = os.environ.get("MOCK_TESTE_POSTGRES_LEITURA_URL", "").strip() or None

pytestmark = pytest.mark.skipif(URL_POSTGRES is None, reason="MOCK_TESTE_POSTGRES_URL não declarada")


@pytest.fixture(scope="module")
def engine_postgres():
    engine = criar_engine(URL_POSTGRES)
    recriar(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def mundo_do_codigo():
    engine = criar_engine("sqlite://")
    recriar(engine)
    return _conteudo_do_banco(engine)


def _carregar_sql_pronto(engine) -> None:
    """Faz o que o Docker faz na primeira subida: roda 01_esquema.sql e 02_dados.sql."""
    apagar_tabelas(engine)
    conexao = engine.raw_connection()
    try:
        cursor = conexao.cursor()
        for nome in (exportar.ARQUIVO_ESQUEMA, exportar.ARQUIVO_DADOS):
            cursor.execute((exportar.PASTA_SQL / "postgres" / nome).read_text(encoding="utf-8"))
        conexao.commit()
    finally:
        conexao.close()


def test_banco_de_teste_e_postgres(engine_postgres):
    assert engine_postgres.dialect.name == "postgresql"


def test_checagens_do_doc_mock_passam_no_postgres(engine_postgres):
    with Session(engine_postgres) as sessao:
        assert verificar(sessao) == []


def test_conteudo_no_postgres_e_igual_ao_do_sqlite(engine_postgres, mundo_do_codigo):
    no_postgres = _conteudo_do_banco(engine_postgres)
    assert no_postgres.keys() == mundo_do_codigo.keys()
    for tabela, linhas in mundo_do_codigo.items():
        assert no_postgres[tabela] == linhas, tabela


def test_recriar_no_postgres_da_o_mesmo_mundo(engine_postgres):
    antes = _conteudo_do_banco(engine_postgres)
    recriar(engine_postgres)
    assert _conteudo_do_banco(engine_postgres) == antes


def test_sql_pronto_no_postgres_e_igual_ao_mundo_do_codigo(engine_postgres, mundo_do_codigo):
    try:
        _carregar_sql_pronto(engine_postgres)
        assert _conteudo_do_banco(engine_postgres) == mundo_do_codigo
        with Session(engine_postgres) as sessao:  # a sequência do id continua depois do maior
            nova = Interacao(id_chamado="CH000001", autor="lojista", canal="chat",
                             data_hora=datetime(2026, 10, 15, 10, 0), texto="nova")
            sessao.add(nova)
            sessao.flush()
            assert nova.id == len(mundo_do_codigo["interacoes"]) + 1
            sessao.rollback()
        with engine_postgres.connect() as conexao:
            comentario = conexao.scalar(text("SELECT col_description('contatos_lojista'::regclass, 4)"))
        assert comentario.startswith("RESTRITO")
    finally:
        recriar(engine_postgres)


@pytest.mark.skipif(URL_LEITURA is None, reason="MOCK_TESTE_POSTGRES_LEITURA_URL não declarada")
@pytest.mark.parametrize(
    "comando",
    [
        "INSERT INTO times (nome, area) VALUES ('x', 'financeiro')",
        "UPDATE lojistas SET carteira = 'pme'",
        "DELETE FROM interacoes",
        "TRUNCATE vendas",
        "DROP TABLE vendas",
        "CREATE TABLE intrusa (a integer)",
    ],
)
def test_papel_de_leitura_nao_altera_nada(comando):
    engine = criar_engine(URL_LEITURA)
    try:
        with engine.connect() as conexao:
            assert conexao.scalar(text("SELECT count(*) FROM lojistas")) == 20
            with pytest.raises(ProgrammingError):
                conexao.execute(text(comando))
    finally:
        engine.dispose()
