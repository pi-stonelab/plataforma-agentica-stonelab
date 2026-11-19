"""Gera frontend/js/mock/ferramentas.js a partir do catálogo real (ferramentas/).

Rodar da raiz do repositório: python frontend/scripts/gerar_catalogo_mock.py
Só é usado pelo modo mock. Com o back-end real, o front lê GET /ferramentas.
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from ferramentas import catalogo  # noqa: E402


def descricao(area, nome):
    """Primeira frase do agents.md. Ferramentas planejadas ainda têm '[preencher: ... Sugestão: X]':
    nesse caso usa a sugestão, sem o marcador."""
    texto = (RAIZ / "ferramentas" / area / nome / "agents.md").read_text(encoding="utf-8")
    linhas = [linha.strip() for linha in texto.splitlines()]
    corpo = [linha for linha in linhas if linha and not linha.startswith("#")]
    primeira = corpo[0] if corpo else ""
    sugestao = re.search(r"Sugest[ãa]o:\s*([^\]]+)", primeira)
    if primeira.startswith("[") and sugestao:
        frase = sugestao.group(1).strip().rstrip(".")
        return frase[0].upper() + frase[1:] + "."
    return re.sub(r"\s*\[(?:aqui conectamos|preencher)[^\]]*\]", "", primeira).strip()


fichas = []
for nome, f in sorted(catalogo.carregar().items()):
    fichas.append(
        {
            "nome": f.nome,
            "area": f.area,
            "descricao": descricao(f.area, f.nome),
            "acesso": f.acesso,
            "nivel_minimo": f.nivel_minimo,
            "areas_permitidas": list(f.areas_permitidas),
            "sensibilidade": f.sensibilidade,
            "status": f.status,
            "integracoes": list(f.integracoes),
        }
    )

destino = RAIZ / "frontend" / "js" / "mock" / "ferramentas.js"
destino.write_text(
    "// Gerado por frontend/scripts/gerar_catalogo_mock.py. Não editar à mão.\n"
    "export const CATALOGO = "
    + json.dumps(fichas, ensure_ascii=False, indent=2)
    + ";\n",
    encoding="utf-8",
)
print(f"{len(fichas)} ferramentas em {destino.relative_to(RAIZ)}")
