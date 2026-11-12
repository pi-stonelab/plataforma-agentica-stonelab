"""Conexão com o banco: engine, sessão, Base das tabelas e criação das tabelas."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import configuracao

engine = create_engine(configuracao.database_url, pool_pre_ping=True)
SessaoLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Toda tabela herda desta classe (ver models.py)."""


def criar_tabelas() -> None:
    """Cria as tabelas que ainda não existem. Sem Alembic na Sprint 2."""
    from app import models  # noqa: F401  (registra as tabelas na Base)

    Base.metadata.create_all(engine)


def obter_sessao() -> Iterator[Session]:
    """Dependência do FastAPI: abre uma sessão por requisição e fecha no fim."""
    with SessaoLocal() as sessao:
        yield sessao
