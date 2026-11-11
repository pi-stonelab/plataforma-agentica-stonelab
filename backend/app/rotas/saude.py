from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import obter_sessao

router = APIRouter(tags=["saúde"])


@router.get("/health")
def saude(sessao: Annotated[Session, Depends(obter_sessao)]) -> dict:
    """Diz se a API está no ar e se o banco responde."""
    try:
        sessao.execute(text("SELECT 1"))
        banco = "ok"
    except SQLAlchemyError:
        banco = "indisponivel"
    return {"status": "ok", "banco": banco}
