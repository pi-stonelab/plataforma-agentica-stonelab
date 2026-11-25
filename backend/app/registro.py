from datetime import datetime

from ferramentas import governanca
from seguranca import permissoes as seg

from app import models
from app.db import SessaoLocal
from app.llm_client import RespostaLLM

PRECO_SIMULADO_POR_MIL_TOKENS = 0.01


def custo_simulado(tokens_entrada: int, tokens_saida: int) -> float:
    return (tokens_entrada + tokens_saida) / 1000 * PRECO_SIMULADO_POR_MIL_TOKENS


def gravar_evento(evento: seg.Evento) -> None:
    _gravar(
        models.Auditoria(
            quando=evento.quando,
            id_usuario=evento.id_usuario,
            acao=evento.acao,
            alvo=evento.alvo,
            permitido=evento.permitido,
            execucao_id=evento.execucao_id,
        )
    )


def gravar_execucao(registro: dict) -> None:
    campos = {campo: registro[campo] for campo in governanca.CAMPOS_REGISTRO}
    campos["momento"] = datetime.fromisoformat(campos["momento"])
    for campo in ("integracoes", "categorias_dados"):
        campos[campo] = list(campos[campo] or ())
    _gravar(models.ExecucaoFerramenta(**campos))


def gravar_uso(resposta: RespostaLLM, *, usuario_id: str, conversa_id: str, execucao_id: str) -> None:
    _gravar(
        models.UsoModelo(
            usuario_id=usuario_id,
            conversa_id=conversa_id,
            execucao_id=execucao_id,
            modelo=resposta.modelo,
            tokens_entrada=resposta.tokens_entrada,
            tokens_saida=resposta.tokens_saida,
            latencia_ms=resposta.duracao_ms,
            custo_simulado=custo_simulado(resposta.tokens_entrada, resposta.tokens_saida),
        )
    )


def _gravar(linha: object) -> None:
    with SessaoLocal() as sessao:
        sessao.add(linha)
        sessao.commit()
