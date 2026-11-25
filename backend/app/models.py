"""Tabelas da plataforma. Os dados sintéticos (lojistas, funcionários) moram no banco do mock."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# JSONB no Postgres; JSON simples no SQLite dos testes.
Json = JSON().with_variant(JSONB(), "postgresql")


def agora() -> datetime:
    return datetime.now(UTC)


class Usuario(Base):
    """Quem entra na plataforma.

    Cargo, carteiras e situação NÃO ficam aqui: vêm do diretório do mock a cada pedido
    (`id_funcionario`), para não haver duas fontes. `id_funcionario` vazio só para perfis sem
    funcionário no mock (hoje, o GestorDeAcessos), que nunca usam ferramentas.
    """

    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # o `sub` do token
    id_funcionario: Mapped[str | None] = mapped_column(String(32), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # sempre minúsculo
    senha_hash: Mapped[str] = mapped_column(String(100))
    # Nome da classe de `seguranca/` (AdminGlobal, Supervisor, Colaborador, Auditor, GestorDeAcessos).
    perfil: Mapped[str] = mapped_column(String(32))
    # Slug da área (`atendimento`/`financeiro`) só para quem não está no diretório do mock; para os
    # demais a área vem do cargo.
    area: Mapped[str | None] = mapped_column(String(32))
    areas_extras: Mapped[list] = mapped_column(Json, default=list)  # slugs, só do Supervisor
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
