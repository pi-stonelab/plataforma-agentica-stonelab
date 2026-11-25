"""API da plataforma.

O back-end importa as pastas da raiz do repositório (`agentes/`, `ferramentas/`, `mock/`, `seguranca/`).
Os testes acham essas pastas pelo `pythonpath` do pytest; `uvicorn app.main:app` e `python -m app.seed`,
rodados de dentro de `backend/`, precisam da raiz no caminho de importação, e ela entra aqui.
"""

import sys
from pathlib import Path

_RAIZ_DO_REPOSITORIO = str(Path(__file__).resolve().parents[2])
if _RAIZ_DO_REPOSITORIO not in sys.path:
    sys.path.append(_RAIZ_DO_REPOSITORIO)
