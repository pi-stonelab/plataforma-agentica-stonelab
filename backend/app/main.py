"""Ponto de entrada da API. Rodar de dentro de backend/: uvicorn app.main:app --reload

A interface (frontend/) é servida na mesma origem, em /app (opção A de frontend/CONTRATO_API.md, §3):
abra http://localhost:8000/app/?mock=0 para usar o back-end real.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from ferramentas import catalogo
from seguranca.permissoes import AcessoNegado

from app.auth import segredo_do_token
from app.db import criar_tabelas
from app.llm_client import criar_cliente
from app.rotas import agentes, auth, conversas, ferramentas, saude

PASTA_DO_FRONT = Path(__file__).resolve().parents[2] / "frontend"
MENSAGEM_ACESSO_NEGADO = "Acesso negado."


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    segredo_do_token()  # sem JWT_SEGREDO a API não sobe (melhor que falhar no primeiro login)
    criar_tabelas()
    catalogo.nomes()  # carrega o catálogo na subida (só pelo nome: carregar() é de uso interno)
    # [A FAZER (Marcelo e Isabel, back-end, KAN-60): governanca.adicionar_destino(gravar_execucao)]
    app.state.llm = criar_cliente()
    yield


app = FastAPI(title="Plataforma Agêntica Stonelab", version="0.2.0", lifespan=ciclo_de_vida)


@app.exception_handler(AcessoNegado)
def acesso_negado(_pedido: Request, _erro: AcessoNegado) -> JSONResponse:
    """Ponto 11 do CLAUDE.md: 403 com mensagem fixa, sem nome de pessoa nem de agente."""
    return JSONResponse(status_code=403, content={"detail": MENSAGEM_ACESSO_NEGADO})


app.include_router(saude.router)
app.include_router(auth.router)
app.include_router(agentes.router)
app.include_router(conversas.router)
app.include_router(ferramentas.router)


@app.get("/", include_in_schema=False)
def inicio() -> RedirectResponse:
    return RedirectResponse("/app/")


if PASTA_DO_FRONT.is_dir():
    app.mount("/app", StaticFiles(directory=PASTA_DO_FRONT, html=True), name="frontend")
