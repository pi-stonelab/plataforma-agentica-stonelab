"""Integrações que as fichas já citam, mas que ainda não têm conector: aparecem desligadas no estado.

[A FAZER (Pedro, ferramentas, bloco E): trocar cada linha abaixo pelo conector de verdade (Jira, Slack,
Telegram, Google Workspace, Microsoft 365 e anexos do chat), com a mesma base `Conector`]
"""

from ferramentas.integracoes.conector import Conector
from ferramentas.integracoes.registro import registrar


class ConectorPlanejado(Conector):
    modo_padrao = "desligado"

    def __init__(self, nome, rotulo):
        self.nome = nome
        self.rotulo = rotulo
        super().__init__()


JIRA = registrar(ConectorPlanejado("jira", "Jira"))
SLACK = registrar(ConectorPlanejado("slack", "Slack"))
TELEGRAM = registrar(ConectorPlanejado("telegram", "Telegram"))
GOOGLE_WORKSPACE = registrar(ConectorPlanejado("google_workspace", "Google Workspace"))
MICROSOFT_365 = registrar(ConectorPlanejado("microsoft_365", "Microsoft 365"))
ANEXOS = registrar(ConectorPlanejado("anexos", "Anexos do chat"))
