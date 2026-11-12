"""Engine e criação das tabelas do mock. Mexe só na metadata do mock (`BaseMock`)."""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from . import modelos

URL_LOCAL_PADRAO = "sqlite:///dados_locais/mock.sqlite"


def _sqlite_em_memoria(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url in ("sqlite://", "sqlite:///"))


def criar_engine(url: str) -> Engine:
    """Cria o engine. `hide_parameters` impede que valores apareçam em mensagens de erro."""
    opcoes: dict = {"hide_parameters": True}
    if _sqlite_em_memoria(url):
        # Um só banco em memória compartilhado entre threads (senão cada conexão vê um vazio).
        opcoes["poolclass"] = StaticPool
        opcoes["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **opcoes)


def url_padrao() -> str:
    """`DATABASE_URL` do ambiente ou, sem ela, o SQLite local em dados_locais/ (pasta criada)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    Path("dados_locais").mkdir(exist_ok=True)
    return URL_LOCAL_PADRAO


def criar_tabelas(engine: Engine) -> None:
    """Cria as tabelas do mock que ainda não existem."""
    modelos.BaseMock.metadata.create_all(engine)


def apagar_tabelas(engine: Engine) -> None:
    """Apaga só as tabelas do mock. Tabelas de outras bases ficam intactas."""
    modelos.BaseMock.metadata.drop_all(engine)
