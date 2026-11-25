"""Ponto de entrada da API. Rodar de dentro de backend/: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth import segredo_do_token
from app.db import criar_tabelas
from app.rotas import auth, saude


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    segredo_do_token()  # sem JWT_SEGREDO a API não sobe (melhor que falhar no primeiro login)
    criar_tabelas()
    yield


app = FastAPI(title="Plataforma Agêntica Stonelab", version="0.1.0", lifespan=ciclo_de_vida)
app.include_router(saude.router)
app.include_router(auth.router)
