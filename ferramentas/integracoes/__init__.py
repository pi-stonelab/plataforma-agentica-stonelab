"""Conectores das integrações que as ferramentas usam. Cada pasta tem o README do sistema; o código fica em
`conector.py` (base), `cliente_http.py` (cliente HTTP comum), `registro.py` (lista e estado) e no `conector.py` de cada
pasta. Importar este pacote registra todos os conectores.
"""

from ferramentas.integracoes import sistemas_internos
from ferramentas.integracoes.anexos import conector as _anexos
from ferramentas.integracoes.apis_publicas import conector as _apis_publicas
from ferramentas.integracoes.email import conector as _email
from ferramentas.integracoes.email_leitura import conector as _email_leitura
from ferramentas.integracoes.google_workspace import conector as _google_workspace
from ferramentas.integracoes.jira import conector as _jira
from ferramentas.integracoes.microsoft_365 import conector as _microsoft_365
from ferramentas.integracoes.registro import conector, estado_integracoes, nomes, reiniciar
from ferramentas.integracoes.slack import conector as _slack
from ferramentas.integracoes.telegram import conector as _telegram

__all__ = ["conector", "estado_integracoes", "nomes", "reiniciar"]
del sistemas_internos, _anexos, _apis_publicas, _email, _email_leitura, _google_workspace, _jira, _microsoft_365, _slack, _telegram
