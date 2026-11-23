"""Conectores das integrações que as ferramentas usam. Cada pasta tem o README do sistema; o código fica em
`conector.py` (base), `http.py` (cliente HTTP comum), `registro.py` (lista e estado) e no `conector.py` de cada
pasta. Importar este pacote registra todos os conectores.
"""

from ferramentas.integracoes import planejados, sistemas_internos
from ferramentas.integracoes.apis_publicas import conector as _apis_publicas
from ferramentas.integracoes.email import conector as _email
from ferramentas.integracoes.registro import conector, estado_integracoes, nomes, reiniciar

__all__ = ["conector", "estado_integracoes", "nomes", "reiniciar"]
del planejados, sistemas_internos, _apis_publicas, _email
