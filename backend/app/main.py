"""Ponto de entrada da API. Rodar de dentro de backend/: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import criar_tabelas
from app.rotas import saude


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(title="Plataforma Agêntica Stonelab", version="0.1.0", lifespan=ciclo_de_vida)
app.include_router(saude.router)
