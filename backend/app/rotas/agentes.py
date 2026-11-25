"""GET /agentes e GET /agentes/{id} (frontend/CONTRATO_API.md, §4.2, §5.4 e §5.5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from seguranca import permissoes as seg
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth import AcessoAtual
from app.datas import iso
from app.db import obter_sessao
from app.orquestrador import configuracao_do_agente
from app.permissoes import Acesso, acoes_permitidas, nome_da_area, plataforma_do_pedido, relacao_com

router = APIRouter(tags=["agentes"])

MENSAGEM_NAO_ENCONTRADO = "Agente não encontrado."
NOME_DA_PLATAFORMA = "Plataforma"


class Dono(BaseModel):
    id: str
    nome: str


class AgenteSaida(BaseModel):
    id: str
    nome: str
    objetivo: str
    area: str | None
    dono: Dono
    ferramentas: list[str]
    ativo: bool
    criado_em: str
    relacao: str
    acoes: list[str]


@router.get("/agentes", response_model=list[AgenteSaida])
def listar_agentes(acesso: AcessoAtual, sessao: Annotated[Session, Depends(obter_sessao)]) -> list[AgenteSaida]:
    """Os agentes que a pessoa pode VER, inclusive os desativados: ativos primeiro, depois por nome."""
    contexto = AgentesDoPedido(sessao, acesso)
    visiveis = [linha for linha in contexto.linhas if contexto.pode(seg.Acao.VER, linha.id)]
    visiveis.sort(key=lambda linha: (not linha.ativo, linha.nome))
    return [contexto.saida(linha) for linha in visiveis]


@router.get("/agentes/{agente_id}", response_model=AgenteSaida)
def obter_agente(
    agente_id: str, acesso: AcessoAtual, sessao: Annotated[Session, Depends(obter_sessao)]
) -> AgenteSaida:
    """Um agente. 404 se não existe ou se a pessoa não pode VER (para não revelar que existe)."""
    contexto = AgentesDoPedido(sessao, acesso, [agente_id])
    linha = contexto.linha_visivel(agente_id)
    return contexto.saida(linha)


class AgentesDoPedido:
    """Agentes lidos do banco e carregados numa `Plataforma` nova, para este pedido só."""

    def __init__(self, sessao: Session, acesso: Acesso, ids: list[str] | None = None):
        consulta = select(models.Agente)
        if ids is not None:
            consulta = consulta.where(models.Agente.id.in_(ids))
        self.sessao = sessao
        self.acesso = acesso
        self.linhas = list(sessao.scalars(consulta))
        convidados: dict[str, set[str]] = {}
        if self.linhas:
            for convite in sessao.scalars(
                select(models.AgenteConvidado).where(
                    models.AgenteConvidado.agente_id.in_([linha.id for linha in self.linhas])
                )
            ):
                convidados.setdefault(convite.agente_id, set()).add(convite.usuario_id)
        self.plataforma, self.agentes = plataforma_do_pedido(acesso, self.linhas, convidados)
        self._por_id = {linha.id: linha for linha in self.linhas}

    def pode(self, acao: seg.Acao, agente_id: str) -> bool:
        agente = self.agentes.get(agente_id)
        return agente is not None and self.acesso.pessoa.pode(acao, agente)

    def linha_visivel(self, agente_id: str) -> models.Agente:
        """A linha do agente, ou 404 se ele não existe ou a pessoa não pode VER."""
        if not self.pode(seg.Acao.VER, agente_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=MENSAGEM_NAO_ENCONTRADO)
        return self._por_id[agente_id]

    def nome_do_dono(self, dono_id: str) -> str:
        if dono_id == seg.DONO_PLATAFORMA:
            return NOME_DA_PLATAFORMA
        dono = self.sessao.get(models.Usuario, dono_id)
        return dono.nome if dono else dono_id

    def ferramentas(self, linha: models.Agente) -> list[str]:
        return list(configuracao_do_agente(self.agentes[linha.id], linha.ferramentas or ())[0])

    def saida(self, linha: models.Agente) -> AgenteSaida:
        agente = self.agentes[linha.id]
        return AgenteSaida(
            id=linha.id,
            nome=linha.nome,
            objetivo=linha.objetivo,
            area=nome_da_area(agente.area),
            dono=Dono(id=linha.dono_id, nome=self.nome_do_dono(linha.dono_id)),
            ferramentas=self.ferramentas(linha),
            ativo=linha.ativo,
            criado_em=iso(linha.criado_em),
            relacao=relacao_com(self.acesso.pessoa, agente),
            acoes=acoes_permitidas(self.acesso.pessoa, agente),
        )

