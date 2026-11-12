"""Falha "fora do ar" controlável por sistema simulado (DOC-MOCK §10).

Liga pela variável de ambiente `MOCK_FALHAS` (nomes separados por vírgula, ex.: "core,crm")
ou pelas funções `ligar` e `desligar` (para testes). Toda consulta do sistema ligado levanta
`SistemaIndisponivel`. O registro (log) guarda só o sistema e o horário, nunca conteúdo.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SISTEMAS = ("cadastro", "core", "cobranca", "crm", "diretorio")

_ligadas_por_codigo: set[str] = set()


class SistemaIndisponivel(Exception):
    """O sistema simulado está fora do ar. A mensagem não traz detalhe técnico."""

    def __init__(self, sistema: str) -> None:
        super().__init__(f"sistema indisponível: {sistema}")
        self.sistema = sistema


def _validar(sistema: str) -> None:
    if sistema not in SISTEMAS:
        raise ValueError(f"sistema desconhecido: {sistema}")


def _registrar(acao: str, sistema: str) -> None:
    horario = datetime.now(timezone.utc).isoformat(timespec="seconds")
    logger.info("falha %s: sistema=%s horario=%s", acao, sistema, horario)


def _ligadas_pelo_ambiente() -> set[str]:
    nomes = {nome.strip() for nome in os.environ.get("MOCK_FALHAS", "").split(",")}
    nomes.discard("")
    desconhecidos = nomes - set(SISTEMAS)
    if desconhecidos:
        logger.warning("MOCK_FALHAS tem %d nome(s) desconhecido(s); ignorados", len(desconhecidos))
    return nomes & set(SISTEMAS)


def ligar(sistema: str) -> None:
    """Coloca o sistema fora do ar."""
    _validar(sistema)
    _ligadas_por_codigo.add(sistema)
    _registrar("ligada", sistema)


def desligar(sistema: str) -> None:
    """Tira o sistema do modo falha (não desfaz o que veio de MOCK_FALHAS)."""
    _validar(sistema)
    _ligadas_por_codigo.discard(sistema)
    _registrar("desligada", sistema)


def desligar_todas() -> None:
    """Remove todas as falhas ligadas por código. Útil no fim de um teste."""
    for sistema in sorted(_ligadas_por_codigo):
        desligar(sistema)


def fora_do_ar(sistema: str) -> bool:
    """True se o sistema está em falha, por código ou por MOCK_FALHAS."""
    _validar(sistema)
    return sistema in _ligadas_por_codigo or sistema in _ligadas_pelo_ambiente()


def verificar(sistema: str) -> None:
    """Chamada no início de cada consulta: levanta `SistemaIndisponivel` se estiver em falha."""
    if fora_do_ar(sistema):
        raise SistemaIndisponivel(sistema)
