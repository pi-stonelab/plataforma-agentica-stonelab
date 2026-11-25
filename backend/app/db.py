"""Conexão com o banco: engine, sessão, Base das tabelas e criação das tabelas."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import configuracao


def _criar_engine(url: str):
    if url.startswith("sqlite") and ":memory:" in url:
        # Testes: uma conexão só, compartilhada entre threads. Sem isso a thread da rota (o FastAPI
        # roda rota síncrona numa thread) abriria outro banco em memória, vazio.
        return create_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    return create_engine(url, pool_pre_ping=True)


engine = _criar_engine(configuracao.database_url)
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
