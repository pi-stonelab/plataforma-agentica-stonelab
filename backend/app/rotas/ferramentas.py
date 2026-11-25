"""GET /ferramentas e GET /integracoes (frontend/CONTRATO_API.md, §4.10 e §6.3; PR 25, KAN-74)."""

from fastapi import APIRouter, HTTPException, status
from ferramentas import catalogo
from ferramentas.integracoes import registro
from seguranca import permissoes as seg

from app.auth import AcessoAtual

router = APIRouter(tags=["ferramentas"])

MENSAGEM_SEM_FERRAMENTAS = "Seu perfil não usa ferramentas."


@router.get("/ferramentas")
def listar_ferramentas(acesso: AcessoAtual) -> list[dict]:
    """O catálogo inteiro, cada ficha marcada para a pessoa (`liberada` e `motivo`).

    Só texto e listas (`catalogo.listar_fichas`); o objeto da ferramenta nunca sai. Admin e Auditor recebem
    as fichas todas como não liberadas; o GestorDeAcessos, que não usa ferramentas, recebe 403.
    """
    if isinstance(acesso.pessoa, seg.GestorDeAcessos):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MENSAGEM_SEM_FERRAMENTAS)
    return catalogo.listar_fichas(acesso.ferramentas)


@router.get("/integracoes")
def listar_integracoes(_acesso: AcessoAtual) -> list[dict]:
    """Uma linha por integração: modo (real, simulado, desligado), se está configurada e a saúde.

    Nunca traz credencial: `estado_integracoes` só diz se ela existe. Qualquer pessoa logada vê (é o que a
    aba de conectores mostra).
    """
    return registro.estado_integracoes()
