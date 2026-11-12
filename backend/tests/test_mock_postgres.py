"""O mesmo mundo do mock no Postgres e no SQLite.

Só roda com `MOCK_TESTE_POSTGRES_URL` apontando para um banco só do mock (ver `mock/CLAUDE.md`).
Sem a variável, os testes são pulados e a suíte normal segue no SQLite em memória.
"""

import pytest
from mock.banco import criar_engine
from mock.gerar import recriar, verificar
from sqlalchemy.orm import Session

from .apoio_ferramentas import url_do_postgres_de_teste
from .test_mock_gerar import _conteudo_do_banco

URL_POSTGRES = url_do_postgres_de_teste()

pytestmark = pytest.mark.skipif(URL_POSTGRES is None, reason="MOCK_TESTE_POSTGRES_URL não declarada")


@pytest.fixture(scope="module")
def engine_postgres():
    engine = criar_engine(URL_POSTGRES)
    recriar(engine)
    yield engine
    engine.dispose()


def test_banco_de_teste_e_postgres(engine_postgres):
    assert engine_postgres.dialect.name == "postgresql"


def test_checagens_do_doc_mock_passam_no_postgres(engine_postgres):
    with Session(engine_postgres) as sessao:
        assert verificar(sessao) == []


def test_conteudo_no_postgres_e_igual_ao_do_sqlite(engine_postgres):
    sqlite = criar_engine("sqlite://")
    recriar(sqlite)
    no_sqlite = _conteudo_do_banco(sqlite)
    no_postgres = _conteudo_do_banco(engine_postgres)
    assert no_postgres.keys() == no_sqlite.keys()
    for tabela, linhas in no_sqlite.items():
        assert no_postgres[tabela] == linhas, tabela


def test_recriar_no_postgres_da_o_mesmo_mundo(engine_postgres):
    antes = _conteudo_do_banco(engine_postgres)
    recriar(engine_postgres)
    assert _conteudo_do_banco(engine_postgres) == antes
