"""Orquestrador: roda um turno do agente para uma pessoa, depois da checagem de acesso ao agente.

A função de serviço é decorada com `@exige_permissao(Acao.EXECUTAR)` (ponto 3 do CLAUDE.md): a rota
chama esta função, e o decorator confere a permissão na `Plataforma` deste pedido antes de qualquer
chamada ao modelo. Negado → `AcessoNegado` (o tratador da API responde 403).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from agentes.agente_atendimento import agente as agente_atendimento
from agentes.agente_atendimento.agente import Turno, rodar_turno
from agentes.agente_geral import agente as agente_geral
from ferramentas import catalogo, governanca
from seguranca import permissoes as seg
from seguranca.envelope import exige_permissao

from app.llm_client import RespostaLLM

PRECO_SIMULADO_POR_MIL_TOKENS = 0.01  # R$; o modelo é local (custo real zero). SEM FONTE: o mesmo do mock do front


@dataclass
class Uso:
    """Soma das chamadas ao modelo de um turno (o objeto `Uso` do contrato, §4.8)."""

    chamadas_modelo: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    respostas: list[RespostaLLM] = field(default_factory=list, repr=False)

    def somar(self, resposta: RespostaLLM) -> None:
        self.respostas.append(resposta)
        self.chamadas_modelo += 1
        self.tokens_entrada += resposta.tokens_entrada
        self.tokens_saida += resposta.tokens_saida
        self.latencia_ms += resposta.duracao_ms

    def como_dict(self) -> dict:
        tokens = self.tokens_entrada + self.tokens_saida
        return {
            "chamadas_modelo": self.chamadas_modelo,
            "tokens_entrada": self.tokens_entrada,
            "tokens_saida": self.tokens_saida,
            "latencia_ms": self.latencia_ms,
            "custo": round(tokens / 1000 * PRECO_SIMULADO_POR_MIL_TOKENS, 4),
        }


def configuracao_do_agente(agente: seg.Agente, ferramentas_salvas: Sequence[str]) -> tuple[tuple[str, ...], str]:
    """Ferramentas e prompt de sistema de um agente.

    O agente geral (dono "plataforma") usa o catálogo inteiro e o prompt do geral; os outros, a lista
    salva no banco e o prompt do agente de atendimento. Lista de ferramentas não é permissão: o
    catálogo ainda confere cargo, área e lojista a cada chamada.
    """
    if agente.dono_id == seg.DONO_PLATAFORMA:
        return tuple(catalogo.nomes()), agente_geral.SISTEMA
    # O catálogo só aceita nomes que existem; um nome antigo no banco vira "ferramenta não encontrada".
    return tuple(ferramentas_salvas), agente_atendimento.SISTEMA


@exige_permissao(seg.Acao.EXECUTAR)
def executar_agente(
    plataforma: seg.Plataforma,
    usuario: seg.Usuario,
    agente: seg.Agente,
    execucao_id: str,
    *,
    pergunta: str,
    usuario_ferramentas: governanca.Usuario | None,
    ferramentas_do_agente: Sequence[str],
    prompt_sistema: str,
    chamar_modelo: Callable[..., str],
    historico: Sequence[tuple[str, str]] = (),
    estado: dict | None = None,
) -> Turno:
    """Um turno do agente com as permissões de quem pediu (primeira checagem já feita pelo decorator).

    `usuario` é a pessoa na camada 1 (acesso ao agente); `usuario_ferramentas`, a mesma pessoa na
    camada 2 (acesso à ferramenta), que o catálogo reconfere a cada USAR.
    """
    return rodar_turno(
        pergunta,
        usuario_ferramentas,
        ferramentas_do_agente,
        chamar_modelo=chamar_modelo,
        historico=historico,
        estado=estado,
        contexto={"execucao_id": execucao_id, "agente_id": str(agente.id)},
        prompt_sistema=prompt_sistema,
    )
