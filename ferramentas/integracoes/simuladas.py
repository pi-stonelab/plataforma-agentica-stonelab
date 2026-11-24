"""Caixa de saída do modo simulado: o que as integrações de escrita "mandariam" se estivessem ligadas de verdade.

Uma caixa por integração (Slack, Telegram, Jira), em memória e só com as últimas `LIMITE` mensagens: serve para os
testes e a demo conferirem o que teria saído (a caixa vive no processo do back-end).
O texto já passou pela máscara de texto que sai da plataforma, então não há dado restrito aqui.
"""

import threading
from collections import deque

LIMITE = 50
CAIXAS = {}
_TRAVA_DAS_CAIXAS = threading.Lock()


class CaixaDeSaidaSimulada:
    def __init__(self, integracao, limite=LIMITE):
        self.integracao = integracao
        self._trava = threading.Lock()
        self._itens = deque(maxlen=limite)
        self._contador = 0

    def guardar(self, destino, texto):
        """Guarda o que sairia e devolve um id de demonstração (`SIM-1`, `SIM-2`...)."""
        with self._trava:
            self._contador += 1
            id_simulado = f"SIM-{self._contador}"
            self._itens.append({"id": id_simulado, "destino": destino, "texto": texto})
            return id_simulado

    def listar(self):
        with self._trava:
            return [dict(item) for item in self._itens]

    def limpar(self):
        with self._trava:
            self._itens.clear()
            self._contador = 0


def caixa(integracao):
    """A caixa da `integracao` (criada no primeiro uso)."""
    with _TRAVA_DAS_CAIXAS:
        if integracao not in CAIXAS:
            CAIXAS[integracao] = CaixaDeSaidaSimulada(integracao)
        return CAIXAS[integracao]

