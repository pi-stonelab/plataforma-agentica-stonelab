"""Conversas e mensagens (frontend/CONTRATO_API.md, §4.3 a §4.8 e §5.6 a §5.9).

Uma conversa é só da pessoa que a abriu: a consulta já filtra pelo id do token, e a conversa de outra
pessoa responde 404 (inclusive para o admin).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from ferramentas import confirmacoes
from pydantic import BaseModel
from seguranca import permissoes as seg
from seguranca.permissoes import AcessoNegado
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth import AcessoAtual
from app.config import configuracao
from app.datas import iso
from app.db import obter_sessao
from app.llm_client import RespostaLLM
from app.orquestrador import Uso, configuracao_do_agente, executar_agente
from app.registro import gravar_uso
from app.rotas.agentes import AgentesDoPedido

router = APIRouter(tags=["conversas"])

MENSAGEM_CONVERSA = "Conversa não encontrada."
MENSAGEM_DESATIVADO = "Este agente foi desativado e só pode ser consultado."
MENSAGEM_VAZIA = "Escreva uma mensagem."
MENSAGEM_LONGA = "Mensagem muito longa (máximo 2.000 caracteres)."
MENSAGEM_MODELO = "O modelo não respondeu. Tente de novo."
MENSAGEM_REGISTRO_DE_USO = "Não foi possível registrar o uso do modelo. Tente de novo em instantes."
MENSAGEM_CONFIRMACAO = "Confirmação não encontrada."
MENSAGEM_JA_DECIDIDA = "Esta ação já foi confirmada ou cancelada."
LIMITE_DO_TEXTO = 2000
TAMANHO_DO_TITULO = 60
# Turno que terminou porque o modelo não respondeu: vira 504 e nada é gravado, para a pessoa
# reenviar o mesmo texto sem duplicar a conversa.
MOTIVOS_DE_MODELO = {"modelo_indisponivel", "tempo"}


class NovaConversa(BaseModel):
    agente_id: str


class NovaMensagem(BaseModel):
    texto: str


class Decisao(BaseModel):
    aprovar: bool


def obter_llm(request: Request):
    """O LLMClient criado na subida da API (main.ciclo_de_vida). Os testes trocam por um roteiro."""
    return request.app.state.llm


def novo_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex}"


# ---------------------------------------------------------------- rotas
@router.get("/conversas")
def listar_conversas(acesso: AcessoAtual, sessao: Annotated[Session, Depends(obter_sessao)]) -> list[dict]:
    """As conversas da pessoa, da mais recente para a mais antiga."""
    linhas = sessao.execute(
        select(models.Conversa, models.Agente.nome)
        .join(models.Agente, models.Agente.id == models.Conversa.agente_id)
        .where(models.Conversa.usuario_id == acesso.conta.id)
        .order_by(models.Conversa.atualizada_em.desc())
    ).all()
    return [
        {
            "id": conversa.id,
            "agente": {"id": conversa.agente_id, "nome": nome_do_agente},
            "titulo": conversa.titulo,
            "criada_em": iso(conversa.criada_em),
            "atualizada_em": iso(conversa.atualizada_em),
        }
        for conversa, nome_do_agente in linhas
    ]


@router.post("/conversas", status_code=status.HTTP_201_CREATED)
def abrir_conversa(
    pedido: NovaConversa, acesso: AcessoAtual, sessao: Annotated[Session, Depends(obter_sessao)]
) -> dict:
    """Abre uma conversa vazia. 404 se a pessoa não vê o agente; 403 se vê mas não pode executar."""
    agentes = AgentesDoPedido(sessao, acesso, [pedido.agente_id])
    linha = agentes.linha_visivel(pedido.agente_id)
    exigir_execucao(agentes, linha)
    conversa = models.Conversa(id=novo_id("cv"), usuario_id=acesso.conta.id, agente_id=linha.id)
    sessao.add(conversa)
    sessao.commit()
    return conversa_saida(sessao, agentes, conversa)


@router.get("/conversas/{conversa_id}")
def obter_conversa(
    conversa_id: str, acesso: AcessoAtual, sessao: Annotated[Session, Depends(obter_sessao)]
) -> dict:
    conversa = conversa_da_pessoa(sessao, conversa_id, acesso.conta.id)
    agentes = AgentesDoPedido(sessao, acesso, [conversa.agente_id])
    return conversa_saida(sessao, agentes, conversa)


@router.post("/conversas/{conversa_id}/mensagens")
def enviar_mensagem(
    conversa_id: str,
    pedido: NovaMensagem,
    acesso: AcessoAtual,
    sessao: Annotated[Session, Depends(obter_sessao)],
    llm: Annotated[object, Depends(obter_llm)],
) -> dict:
    """Um turno do agente: grava a pergunta e a resposta com o rastro e devolve a resposta."""
    conversa = conversa_da_pessoa(sessao, conversa_id, acesso.conta.id)
    texto = validar_texto(pedido.texto)

    # A conversa é da pessoa: quem perdeu o acesso ao agente recebe 403 (não 404), como no contrato.
    agentes = AgentesDoPedido(sessao, acesso, [conversa.agente_id])
    linha = sessao.get(models.Agente, conversa.agente_id)
    execucao_id = uuid.uuid4().hex
    exigir_execucao(agentes, linha, execucao_id)
    agente = agentes.agentes[linha.id]
    ferramentas_do_agente, prompt_sistema = configuracao_do_agente(agente, linha.ferramentas or ())

    mensagens = mensagens_da_conversa(sessao, conversa.id)
    ultima = mensagens[-1] if mensagens else None
    estado = conversa.estado if ultima is not None and ultima.tipo == "pergunta" else None

    uso = Uso()
    usos_sem_registro: list[RespostaLLM] = []

    def registrar_uso(resposta_do_modelo: RespostaLLM) -> None:
        uso.somar(resposta_do_modelo)
        try:
            gravar_uso(
                resposta_do_modelo,
                usuario_id=acesso.conta.id,
                conversa_id=conversa_id,
                execucao_id=execucao_id,
            )
        except Exception:
            usos_sem_registro.append(resposta_do_modelo)
            raise

    sessao.commit()
    # Primeira checagem (acesso ao agente) no decorator; a segunda, por ferramenta, no catálogo.
    turno = executar_agente(
        agentes.plataforma,
        acesso.pessoa,
        agente,
        execucao_id,
        pergunta=texto,
        usuario_ferramentas=acesso.ferramentas,
        ferramentas_do_agente=ferramentas_do_agente,
        prompt_sistema=prompt_sistema,
        chamar_modelo=llm.como_chamar_modelo(ao_responder=registrar_uso),
        historico=historico_de(mensagens),
        estado=estado,
        segundos_por_turno=configuracao.turno_segundos,
    )
    if usos_sem_registro:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=MENSAGEM_REGISTRO_DE_USO)
    if turno.tipo == "limite" and turno.motivo in MOTIVOS_DE_MODELO:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail=MENSAGEM_MODELO)
    # Escrita em duas fases: a prévia que este turno deixou esperando a pessoa vira o cartão de confirmação.
    confirmacao = (
        confirmacoes.confirmacao_da_execucao(execucao_id, acesso.ferramentas) if acesso.ferramentas else None
    )

    agora = datetime.now(UTC)
    proxima = len(mensagens)
    sessao.add(
        models.Mensagem(
            id=novo_id("m"), conversa_id=conversa.id, ordem=proxima, autor="usuario", texto=texto, criada_em=agora
        )
    )
    resposta = models.Mensagem(
        id=novo_id("m"),
        conversa_id=conversa.id,
        ordem=proxima + 1,
        autor="agente",
        texto=turno.resposta,
        tipo="confirmacao" if confirmacao else turno.tipo,
        motivo=turno.motivo,
        confirmacao=confirmacao,
        trajetoria=list(turno.trajetoria),
        uso=uso.como_dict(),
        execucao_id=execucao_id,
        criada_em=datetime.now(UTC),
    )
    sessao.add(resposta)
    if conversa.titulo is None:
        conversa.titulo = texto[:TAMANHO_DO_TITULO]
    conversa.estado = turno.estado if turno.tipo == "pergunta" else None
    conversa.atualizada_em = resposta.criada_em
    sessao.commit()

    return resposta_agente(resposta)


@router.post("/conversas/{conversa_id}/confirmacoes/{confirmacao_id}")
def decidir_confirmacao(
    conversa_id: str,
    confirmacao_id: str,
    pedido: Decisao,
    acesso: AcessoAtual,
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> dict:
    """Confirma ou cancela a prévia de uma escrita (frontend/CONTRATO_API.md, §6.2).

    Quem age é `ferramentas.confirmacoes`: só o mesmo funcionário confirma, a governança é conferida de novo e
    os argumentos reais nunca saem do servidor. Aqui: a conversa é da pessoa (404), ela ainda pode executar o
    agente (403), a prévia é desta conversa (404) e ainda não foi decidida (409).
    """
    conversa = conversa_da_pessoa(sessao, conversa_id, acesso.conta.id)
    original = mensagem_da_confirmacao(sessao, conversa.id, confirmacao_id)
    if original is None or acesso.ferramentas is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=MENSAGEM_CONFIRMACAO)
    if original.confirmacao.get("situacao") != confirmacoes.PENDENTE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=MENSAGEM_JA_DECIDIDA)

    agentes = AgentesDoPedido(sessao, acesso, [conversa.agente_id])
    exigir_execucao(agentes, sessao.get(models.Agente, conversa.agente_id), original.execucao_id)

    usuario = acesso.ferramentas
    atual = confirmacoes.confirmacao_para_interface(confirmacao_id, usuario)
    if atual is None:
        situacao = confirmacoes.situacao_da_decisao(confirmacao_id, usuario)
        if situacao is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=MENSAGEM_CONFIRMACAO)
        # Expirou ou foi decidida fora desta rota: o histórico passa a mostrar isso.
        original.confirmacao = {**original.confirmacao, "situacao": situacao}
        sessao.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=confirmacoes.MENSAGEM_JA_DECIDIDA.get(situacao, MENSAGEM_JA_DECIDIDA),
        )

    resultado = (confirmacoes.confirmar if pedido.aprovar else confirmacoes.cancelar)(confirmacao_id, usuario)
    if pedido.aprovar and confirmacoes.confirmacao_para_interface(confirmacao_id, usuario) is not None:
        situacao = confirmacoes.PENDENTE  # falha passageira: nada saiu e a prévia continua na fila
    elif pedido.aprovar:
        situacao = confirmacoes.situacao_da_decisao(confirmacao_id, usuario) or confirmacoes.APROVADA
    else:
        situacao = confirmacoes.CANCELADA
    original.confirmacao = {**atual, "situacao": situacao}

    agora = datetime.now(UTC)
    nova = models.Mensagem(
        id=novo_id("m"),
        conversa_id=conversa.id,
        ordem=proxima_ordem(sessao, conversa.id),
        autor="agente",
        texto=resultado.get("mensagem") or ("Feito." if resultado.get("status") == "ok" else "Não foi possível."),
        tipo="final",
        trajetoria=[],
        criada_em=agora,
    )
    sessao.add(nova)
    conversa.atualizada_em = agora
    sessao.commit()
    return resposta_agente(nova)


# ---------------------------------------------------------------- apoio
def conversa_da_pessoa(sessao: Session, conversa_id: str, usuario_id: str) -> models.Conversa:
    """A conversa, filtrada pelo id do token na própria consulta. De outra pessoa: 404."""
    conversa = sessao.scalar(
        select(models.Conversa).where(
            models.Conversa.id == conversa_id, models.Conversa.usuario_id == usuario_id
        )
    )
    if conversa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=MENSAGEM_CONVERSA)
    return conversa


def exigir_execucao(
    agentes: AgentesDoPedido, linha: models.Agente, execucao_id: str | None = None
) -> None:
    """Primeira checagem, registrada pela Plataforma. Agente desativado tem mensagem própria."""
    try:
        agentes.plataforma.autorizar(
            agentes.acesso.pessoa, seg.Acao.EXECUTAR, agentes.agentes[linha.id], execucao_id
        )
    except AcessoNegado:
        if not linha.ativo:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MENSAGEM_DESATIVADO) from None
        raise


def validar_texto(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        raise HTTPException(422, detail=MENSAGEM_VAZIA)
    if len(texto) > LIMITE_DO_TEXTO:
        raise HTTPException(422, detail=MENSAGEM_LONGA)
    return texto


def resposta_agente(mensagem: models.Mensagem) -> dict:
    """`RespostaAgente` (§4.6): a mensagem do agente com o texto em `resposta`."""
    saida = mensagem_saida(mensagem)
    saida["resposta"] = saida.pop("texto")
    del saida["autor"]
    return saida


def mensagem_da_confirmacao(sessao: Session, conversa_id: str, confirmacao_id: str) -> models.Mensagem | None:
    """A mensagem do agente desta conversa que trouxe a prévia `confirmacao_id`."""
    for mensagem in mensagens_da_conversa(sessao, conversa_id):
        if mensagem.confirmacao and mensagem.confirmacao.get("id") == confirmacao_id:
            return mensagem
    return None


def proxima_ordem(sessao: Session, conversa_id: str) -> int:
    mensagens = mensagens_da_conversa(sessao, conversa_id)
    return mensagens[-1].ordem + 1 if mensagens else 0


def mensagens_da_conversa(sessao: Session, conversa_id: str) -> list[models.Mensagem]:
    return list(
        sessao.scalars(
            select(models.Mensagem)
            .where(models.Mensagem.conversa_id == conversa_id)
            .order_by(models.Mensagem.ordem)
        )
    )


def historico_de(mensagens: list[models.Mensagem]) -> list[tuple[str, str]]:
    """Pares (mensagem da pessoa, resposta do agente) dos turnos anteriores, para o motor."""
    pares = []
    pergunta = None
    for mensagem in mensagens:
        if mensagem.autor == "usuario":
            pergunta = mensagem.texto
        elif pergunta is not None:
            pares.append((pergunta, mensagem.texto))
            pergunta = None
    return pares


def mensagem_saida(mensagem: models.Mensagem) -> dict:
    saida = {
        "id": mensagem.id,
        "autor": mensagem.autor,
        "texto": mensagem.texto,
        "criada_em": iso(mensagem.criada_em),
    }
    if mensagem.autor == "agente":
        saida.update(
            tipo=mensagem.tipo,
            trajetoria=mensagem.trajetoria or [],
            uso=mensagem.uso,
            confirmacao=mensagem.confirmacao,
        )
    return saida


def conversa_saida(sessao: Session, agentes: AgentesDoPedido, conversa: models.Conversa) -> dict:
    linha = sessao.get(models.Agente, conversa.agente_id)
    agente = agentes.agentes[linha.id]
    return {
        "id": conversa.id,
        "agente": {
            "id": linha.id,
            "nome": linha.nome,
            "objetivo": linha.objetivo,
            "ferramentas": agentes.ferramentas(linha),
            "ativo": linha.ativo,
            # Agora, não quando a conversa foi aberta: convite removido ou agente desativado
            # desligam a caixa de texto, mas o histórico continua visível.
            "pode_executar": linha.ativo and agentes.acesso.pessoa.pode(seg.Acao.EXECUTAR, agente),
        },
        "criada_em": iso(conversa.criada_em),
        "mensagens": [mensagem_saida(m) for m in mensagens_da_conversa(sessao, conversa.id)],
    }

