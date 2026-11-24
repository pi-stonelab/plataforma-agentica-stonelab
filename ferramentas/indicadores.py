"""Regras comuns das ferramentas que leem a base analítica: o período pedido e os meses no formato AAAA-MM."""

import re
from datetime import timedelta

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta

DIAS_MAXIMOS = 92  # um trimestre: relatório, não extrato
PADRAO_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def ontem():
    """Último dia que a base analítica pode ter (ela corta em ontem)."""
    return dados_sinteticos.HOJE_DO_MOCK - timedelta(days=1)


def periodo_pedido(argumentos, dias_padrao):
    """(data_inicio, data_fim) do pedido; sem datas, os últimos `dias_padrao` dias até ontem."""
    fim = argumentos.get("data_fim", ontem())
    inicio = argumentos.get("data_inicio", fim - timedelta(days=dias_padrao - 1))
    if inicio > fim:
        raise ErroFerramenta("parametro_invalido", "A data_inicio deve ser igual ou anterior à data_fim.")
    if (fim - inicio).days + 1 > DIAS_MAXIMOS:
        raise ErroFerramenta("parametro_invalido", f"O período pode ter no máximo {DIAS_MAXIMOS} dias.")
    return inicio, fim


def mes_menos(mes, quantidade):
    """O mês `quantidade` meses antes de `mes` (AAAA-MM)."""
    ano, numero = map(int, mes.split("-"))
    indice = ano * 12 + numero - 1 - quantidade
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def meses_entre(inicio, fim):
    """Quantos meses vão de `inicio` a `fim`, contando os dois (AAAA-MM); zero ou menos se estão invertidos."""
    ano_inicio, mes_inicio = map(int, inicio.split("-"))
    ano_fim, mes_fim = map(int, fim.split("-"))
    return (ano_fim - ano_inicio) * 12 + mes_fim - mes_inicio + 1


def periodo_em_meses(argumentos, meses_padrao, meses_maximos):
    """(mes_inicio, mes_fim) do pedido, em AAAA-MM; sem meses, os últimos `meses_padrao` até o mês do mock."""
    fim = argumentos.get("mes_fim", dados_sinteticos.HOJE_DO_MOCK.strftime("%Y-%m"))
    inicio = argumentos.get("mes_inicio", mes_menos(fim, meses_padrao - 1) if PADRAO_MES.fullmatch(fim) else fim)
    if not (PADRAO_MES.fullmatch(inicio) and PADRAO_MES.fullmatch(fim)):
        raise ErroFerramenta("parametro_invalido", "Use o mês no formato AAAA-MM, como 2026-09.")
    meses = meses_entre(inicio, fim)
    if meses < 1:
        raise ErroFerramenta("parametro_invalido", "O mes_inicio deve ser igual ou anterior ao mes_fim.")
    if meses > meses_maximos:
        raise ErroFerramenta("parametro_invalido", f"O período pode ter no máximo {meses_maximos} meses.")
    return inicio, fim
