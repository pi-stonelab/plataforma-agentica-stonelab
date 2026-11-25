"""POST /auth/login e GET /me (frontend/CONTRATO_API.md, §5.2 e §5.3)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    MENSAGEM_LOGIN,
    AcessoAtual,
    autenticar,
    criar_token,
    diretorio_fora,
    nao_autorizado,
)
from app.db import obter_sessao
from app.permissoes import AcessoRecusado, DiretorioIndisponivel, nome_da_area

router = APIRouter(tags=["login"])


class PedidoLogin(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    senha: str = Field(min_length=1, max_length=128)


class RespostaLogin(BaseModel):
    token: str
    tipo: str = "bearer"


class UsoMes(BaseModel):
    gasto: float
    limite: float


class Perfil(BaseModel):
    """Objeto `Usuario` do contrato (§4.1)."""

    id: str
    nome: str
    email: str
    perfil: str
    area: str | None
    areas_extras: list[str]
    carteira: list[str]
    uso_mes: UsoMes | None = None  # Sprint 3 (limite de gasto)


@router.post("/auth/login", response_model=RespostaLogin)
def entrar(pedido: PedidoLogin, sessao: Annotated[Session, Depends(obter_sessao)]) -> RespostaLogin:
    """Troca e-mail e senha por um token. A mesma mensagem para e-mail inexistente e senha errada."""
    try:
        acesso = autenticar(sessao, pedido.email, pedido.senha)
    except AcessoRecusado:
        raise nao_autorizado(MENSAGEM_LOGIN) from None
    except DiretorioIndisponivel:
        raise diretorio_fora() from None
    return RespostaLogin(token=criar_token(acesso.conta.id))


@router.get("/me", response_model=Perfil)
def eu(acesso: AcessoAtual) -> Perfil:
    """Quem está logado, com perfil e área lidos agora (banco + diretório do mock)."""
    pessoa = acesso.pessoa
    extras = getattr(pessoa, "areas", {pessoa.area}) - {pessoa.area}
    return Perfil(
        id=acesso.conta.id,
        nome=acesso.conta.nome,
        email=acesso.conta.email,
        perfil=type(pessoa).__name__,
        area=nome_da_area(pessoa.area),
        areas_extras=sorted(nome_da_area(area) for area in extras),
        # Nomes das carteiras do time (ex.: ["varejo"]); vazio para quem vê todos ou nenhum.
        carteira=list(acesso.ferramentas.carteiras) if acesso.ferramentas else [],
    )
