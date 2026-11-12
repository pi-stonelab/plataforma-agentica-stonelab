"""Engine e criação das tabelas do mock. Mexe só na metadata do mock (`BaseMock`)."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from . import modelos

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
    """SQLite local em dados_locais/ na raiz do repo (a pasta é criada).

    Não usa `DATABASE_URL`: essa variável aponta para o banco da plataforma, e recriar o mock
    apaga tabelas (ALTO-2 da auditoria A1-A3). Outro banco só com `--url` e a flag explícita.
    """
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
