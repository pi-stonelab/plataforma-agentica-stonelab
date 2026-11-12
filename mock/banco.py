"""Engine e criação das tabelas do mock. Mexe só na metadata do mock (`BaseMock`)."""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from . import modelos

VARIAVEL_DO_BANCO = "MOCK_DATABASE_URL"
VARIAVEL_DA_PLATAFORMA = "DATABASE_URL"

# Relativo à raiz do repositório (não ao diretório onde o comando roda).
RAIZ_DO_REPO = Path(__file__).resolve().parent.parent
PASTA_LOCAL = RAIZ_DO_REPO / "dados_locais"
CAMINHO_LOCAL_PADRAO = PASTA_LOCAL / "mock.sqlite"


def sqlite_em_memoria(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url in ("sqlite://", "sqlite:///"))


def criar_engine(url: str) -> Engine:
    """Cria o engine. `hide_parameters` impede que valores apareçam em mensagens de erro."""
    opcoes: dict = {"hide_parameters": True}
    if sqlite_em_memoria(url):
        # Um só banco em memória compartilhado entre threads (senão cada conexão vê um vazio).
        opcoes["poolclass"] = StaticPool
        opcoes["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **opcoes)


def url_padrao() -> str:
    """URL do banco do mock: a variável `MOCK_DATABASE_URL`, se declarada; senão o SQLite local.

    O SQLite local fica em dados_locais/ na raiz do repo (a pasta é criada). `DATABASE_URL` nunca é
    lida: ela aponta para o banco da plataforma, e recriar o mock apaga tabelas (ALTO-2 da auditoria
    A1-A3). Por isso a URL declarada não pode ser igual à da plataforma. Um banco que não é SQLite
    ainda exige `--permitir-banco-externo` no gerador (`mock.gerar`). Uma fonte só: o gerador, a
    fachada das ferramentas e o diretório de funcionários usam esta função.
    """
    declarada = os.environ.get(VARIAVEL_DO_BANCO, "").strip()
    if declarada:
        if declarada == os.environ.get(VARIAVEL_DA_PLATAFORMA, "").strip():
            raise ValueError(f"{VARIAVEL_DO_BANCO} não pode ser o banco da plataforma.")
        return declarada
    PASTA_LOCAL.mkdir(exist_ok=True)
    return f"sqlite:///{CAMINHO_LOCAL_PADRAO.as_posix()}"


def eh_sqlite(url: str) -> bool:
    """True se a URL é de SQLite. URL malformada levanta `ValueError` sem repetir o texto dela."""
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except ArgumentError:  # a mensagem do SQLAlchemy pode trazer a URL (e a senha) inteira
        raise ValueError("URL de banco inválida.") from None


def criar_tabelas(engine: Engine) -> None:
    """Cria as tabelas do mock que ainda não existem."""
    modelos.BaseMock.metadata.create_all(engine)


def apagar_tabelas(engine: Engine) -> None:
    """Apaga só as tabelas do mock. Tabelas de outras bases ficam intactas."""
    modelos.BaseMock.metadata.drop_all(engine)
