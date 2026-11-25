"""Tabelas da plataforma. Os dados sintéticos (lojistas, funcionários) moram no banco do mock."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
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


class Agente(Base):
    """Um agente da plataforma. As ferramentas ficam no código (D10); aqui só os nomes."""

    __tablename__ = "agentes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # letras, dígitos, "_" e "-"
    nome: Mapped[str] = mapped_column(String(120))
    objetivo: Mapped[str] = mapped_column(Text, default="")
    area: Mapped[str | None] = mapped_column(String(32))  # slug; vazio só no agente geral
    # Id de `usuarios`, ou "plataforma" no agente geral (seguranca.DONO_PLATAFORMA).
    dono_id: Mapped[str] = mapped_column(String(32), index=True)
    visibilidade: Mapped[str] = mapped_column(String(16), default="privado")
    ferramentas: Mapped[list] = mapped_column(Json, default=list)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class AgenteConvidado(Base):
    __tablename__ = "agente_convidados"

    agente_id: Mapped[str] = mapped_column(ForeignKey("agentes.id"), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)


class Conversa(Base):
    """Uma conversa de uma pessoa com um agente. Só a dona vê (os outros recebem 404)."""

    __tablename__ = "conversas"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), index=True)
    agente_id: Mapped[str] = mapped_column(ForeignKey("agentes.id"))
    titulo: Mapped[str | None] = mapped_column(String(60))
    # `Turno.estado` do último turno que terminou em "pergunta" (ponto 8 do CLAUDE.md). Fica só no
    # servidor: o cliente nunca manda estado.
    estado: Mapped[dict | None] = mapped_column(Json)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)


class Mensagem(Base):
    __tablename__ = "mensagens"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversa_id: Mapped[str] = mapped_column(ForeignKey("conversas.id"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)  # posição na conversa (desempata horários iguais)
    autor: Mapped[str] = mapped_column(String(10))  # "usuario" ou "agente"
    texto: Mapped[str] = mapped_column(Text)
    # Só do agente: "final", "pergunta" ou "limite" (Turno.tipo); "motivo" no limite.
    tipo: Mapped[str | None] = mapped_column(String(16))
    motivo: Mapped[str | None] = mapped_column(String(32))
    trajetoria: Mapped[list | None] = mapped_column(Json)  # o rastro (ação e nome, sem argumentos)
    uso: Mapped[dict | None] = mapped_column(Json)  # chamadas, tokens, latência e custo do turno
    execucao_id: Mapped[str | None] = mapped_column(String(64))  # liga ao registro das ferramentas
    # Prévia de escrita esperando a pessoa (`Confirmacao`, §4.9): só os campos mascarados que a interface
    # mostra. Os argumentos reais ficam na fila de `ferramentas/confirmacoes.py`, nunca aqui.
    confirmacao: Mapped[dict | None] = mapped_column(Json)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
