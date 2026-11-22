"""Falhas controláveis por sistema simulado (DOC-MOCK §10): "fora do ar" e "dado desatualizado".

Liga pela variável de ambiente `MOCK_FALHAS` (nomes separados por vírgula, ex.: "core,crm"; o tipo vai
depois de dois-pontos, ex.: "analitica:desatualizado") ou pelas funções `ligar` e `desligar` (para
testes). Fora do ar: toda consulta do sistema levanta `SistemaIndisponivel`. Desatualizado (só a base
analítica, como no §10.1): as consultas respondem, mas com mais dias de atraso que o normal. O registro
(log) guarda só o sistema, o tipo e o horário, nunca conteúdo.

Os outros tipos do §10.1 (lento, intermitente, limite de pedidos e resposta malformada) ainda não
existem no mock.
"""

import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

SISTEMAS = ("cadastro", "core", "cobranca", "crm", "diretorio", "email", "disputas", "analitica")
FORA_DO_AR = "fora_do_ar"
DESATUALIZADO = "desatualizado"
TIPOS = (FORA_DO_AR, DESATUALIZADO)
SISTEMAS_QUE_DESATUALIZAM = ("analitica",)

_ligadas_por_codigo: dict[str, set[str]] = {tipo: set() for tipo in TIPOS}


class SistemaIndisponivel(ConnectionError):
    """O sistema simulado está fora do ar. A mensagem não traz detalhe técnico.

    É um `ConnectionError`, como uma queda de verdade: as ferramentas já tratam esse tipo
    como `integracao_indisponivel` (MED-1 da auditoria A1-A3).
    """

    def __init__(self, sistema: str) -> None:
        super().__init__(f"sistema indisponível: {sistema}")
        self.sistema = sistema


def _validar(sistema: str, tipo: str = FORA_DO_AR) -> None:
    if sistema not in SISTEMAS:
        raise ValueError(f"sistema desconhecido: {sistema}")
    if tipo not in TIPOS:
        raise ValueError(f"tipo de falha desconhecido: {tipo}")
    if tipo == DESATUALIZADO and sistema not in SISTEMAS_QUE_DESATUALIZAM:
        raise ValueError(f"falha desconhecida para o sistema {sistema}: {tipo}")


def _registrar(acao: str, sistema: str, tipo: str) -> None:
    horario = datetime.now(UTC).isoformat(timespec="seconds")
    if tipo == FORA_DO_AR:
        logger.info("falha %s: sistema=%s horario=%s", acao, sistema, horario)
    else:
        logger.info("falha %s: sistema=%s tipo=%s horario=%s", acao, sistema, tipo, horario)


def _ligadas_pelo_ambiente(tipo: str) -> set[str]:
    """Sistemas com a falha `tipo` em MOCK_FALHAS. Nome sem tipo vale como "fora do ar"."""
    pedidas, desconhecidas = set(), 0
    for item in os.environ.get("MOCK_FALHAS", "").split(","):
        sistema, _, tipo_pedido = (parte.strip() for parte in item.partition(":"))
        if not sistema:
            continue
        try:
            _validar(sistema, tipo_pedido or FORA_DO_AR)
        except ValueError:
            desconhecidas += 1
            continue
        if (tipo_pedido or FORA_DO_AR) == tipo:
            pedidas.add(sistema)
    if desconhecidas:
        logger.warning("MOCK_FALHAS tem %d nome(s) desconhecido(s); ignorados", desconhecidas)
    return pedidas


def ligar(sistema: str, tipo: str = FORA_DO_AR) -> None:
    """Coloca o sistema em falha (por padrão, fora do ar)."""
    _validar(sistema, tipo)
    _ligadas_por_codigo[tipo].add(sistema)
    _registrar("ligada", sistema, tipo)


def desligar(sistema: str, tipo: str = FORA_DO_AR) -> None:
    """Tira o sistema da falha (não desfaz o que veio de MOCK_FALHAS)."""
    _validar(sistema, tipo)
    _ligadas_por_codigo[tipo].discard(sistema)
    _registrar("desligada", sistema, tipo)


def desligar_todas() -> None:
    """Remove todas as falhas ligadas por código. Útil no fim de um teste."""
    for tipo in TIPOS:
        for sistema in sorted(_ligadas_por_codigo[tipo]):
            desligar(sistema, tipo)


def fora_do_ar(sistema: str) -> bool:
    """True se o sistema está fora do ar, por código ou por MOCK_FALHAS."""
    _validar(sistema)
    return sistema in _ligadas_por_codigo[FORA_DO_AR] or sistema in _ligadas_pelo_ambiente(FORA_DO_AR)


def desatualizado(sistema: str) -> bool:
    """True se o sistema está com a falha "dado desatualizado", por código ou por MOCK_FALHAS."""
    _validar(sistema, DESATUALIZADO)
    return sistema in _ligadas_por_codigo[DESATUALIZADO] or sistema in _ligadas_pelo_ambiente(DESATUALIZADO)


def verificar(sistema: str) -> None:
    """Chamada no início de cada consulta: levanta `SistemaIndisponivel` se estiver fora do ar."""
    if fora_do_ar(sistema):
        raise SistemaIndisponivel(sistema)
