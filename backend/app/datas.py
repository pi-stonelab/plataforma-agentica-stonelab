"""Datas no formato do contrato: ISO 8601 com o fuso de Brasília."""

from datetime import UTC, datetime, timedelta, timezone

# Brasília sem horário de verão desde 2019. Fuso fixo para não depender do pacote tzdata no Windows.
BRASILIA = timezone(timedelta(hours=-3), "America/Sao_Paulo")


def iso(momento: datetime) -> str:
    """`2026-11-12T14:03:00-03:00`. O SQLite devolve sem fuso: ali o valor gravado é UTC."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(BRASILIA).isoformat(timespec="seconds")
