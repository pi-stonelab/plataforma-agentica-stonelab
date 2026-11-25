from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth import AcessoAtual
from app.datas import iso
from app.db import obter_sessao
from app.permissoes import plataforma_do_pedido

router = APIRouter(tags=["auditoria"])

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


class EventoSaida(BaseModel):
    id: int
    quando: str
    id_usuario: str
    acao: str
    alvo: str
    permitido: bool
    execucao_id: str | None


@router.get("/auditoria", response_model=list[EventoSaida])
def ler_auditoria(
    acesso: AcessoAtual,
    sessao: Annotated[Session, Depends(obter_sessao)],
    id_usuario: Annotated[str | None, Query(max_length=32)] = None,
    execucao_id: Annotated[str | None, Query(max_length=64)] = None,
    permitido: bool | None = None,
    antes_de: Annotated[int | None, Query(ge=1)] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_PADRAO,
) -> list[EventoSaida]:
    plataforma, _ = plataforma_do_pedido(acesso, [], {})
    plataforma.autorizar_leitura_auditoria(acesso.pessoa)

    consulta = select(models.Auditoria).order_by(models.Auditoria.id.desc()).limit(limite)
    if id_usuario is not None:
        consulta = consulta.where(models.Auditoria.id_usuario == id_usuario)
    if execucao_id is not None:
        consulta = consulta.where(models.Auditoria.execucao_id == execucao_id)
    if permitido is not None:
        consulta = consulta.where(models.Auditoria.permitido == permitido)
    if antes_de is not None:
        consulta = consulta.where(models.Auditoria.id < antes_de)
    return [
        EventoSaida(
            id=linha.id,
            quando=iso(linha.quando),
            id_usuario=linha.id_usuario,
            acao=linha.acao,
            alvo=linha.alvo,
            permitido=linha.permitido,
            execucao_id=linha.execucao_id,
        )
        for linha in sessao.scalars(consulta)
    ]
