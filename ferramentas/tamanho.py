"""Teto de tamanho do que uma ferramenta devolve ao agente.

O agente corta cada resultado em 6000 caracteres (`MAX_CHARS_MD`, em `agentes/`), e um JSON cortado no meio
engana o modelo. Por isso o corte é nosso: tira itens do FIM da maior lista e avisa, em campos que o modelo lê.
"""

import json

TETO_DE_CARACTERES = 5000  # deixa folga para o envelope (status, mensagem) dentro dos 6000 do agente
AVISO_DE_TAMANHO = "A resposta foi cortada para caber. Peça um período menor, um limite menor ou um filtro."


def _tamanho(dados):
    return len(json.dumps(dados, ensure_ascii=False, default=str))


def _maior_lista(dados):
    """A chave da lista mais longa (em caracteres) no primeiro nível de `dados`, ou None."""
    listas = {chave: valor for chave, valor in dados.items() if isinstance(valor, list) and valor}
    return max(listas, key=lambda chave: _tamanho(listas[chave]), default=None)


def limitar(dados, teto=None):
    """`dados` dentro do teto: se passar, tira itens do fim da maior lista e marca `truncado`.

    Acrescenta `cortados_por_tamanho` (quantos itens saíram) e `aviso_de_tamanho`. Os totais que a ferramenta
    já devolve (`total_encontrado`, `total_de_...`) continuam contando tudo. Sem lista para encurtar, devolve
    `dados` como está (o corte do agente ainda vale).
    """
    teto = TETO_DE_CARACTERES if teto is None else teto
    if not isinstance(dados, dict) or _tamanho(dados) <= teto:
        return dados
    chave = _maior_lista(dados)
    if chave is None:
        return dados
    cortado = {**dados, "truncado": True, "cortados_por_tamanho": 0, "aviso_de_tamanho": AVISO_DE_TAMANHO}
    cortado[chave] = list(dados[chave])
    while cortado[chave] and _tamanho(cortado) > teto:
        cortado[chave].pop()
        cortado["cortados_por_tamanho"] += 1
    return cortado
