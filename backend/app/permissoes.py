"""Quem é a pessoa deste pedido: monta os dois `Usuario` (camadas 1 e 2) a partir do banco e do mock.

Porta 1 (CLAUDE.md, "As quatro portas"): token válido, linha em `usuarios`, perfil conhecido e
funcionário `ativo` no diretório do mock. Tudo é lido de novo a cada pedido: perfil, área e carteira
nunca vêm do token, do corpo nem do prompt.
"""

from dataclasses import dataclass

from ferramentas import diretorio, governanca
from seguranca import permissoes as seg
from sqlalchemy.orm import Session

from app import models

# Correspondência cargo (mock) → perfil (camada 1), decidida em D8/O1 (tabela no CLAUDE.md).
PERFIL_DO_CARGO: dict[str, type[seg.Usuario]] = {
    "atendente_n1": seg.Colaborador,
    "especialista_n2": seg.Colaborador,
    "supervisor_atendimento": seg.Supervisor,
    "analista_ouvidoria": seg.Colaborador,
    "analista_cobranca": seg.Colaborador,
    "analista_disputas": seg.Colaborador,
    "analista_recebiveis": seg.Colaborador,
    "coordenador_financeiro": seg.Supervisor,
    "auditor_compliance": seg.Auditor,
    "admin_plataforma": seg.AdminGlobal,
}
PERFIS: dict[str, type[seg.Usuario]] = {classe.__name__: classe for classe in seg.ROLES}


class AcessoRecusado(Exception):
    """Porta 1 fechada (pessoa ausente, inativa ou com perfil desconhecido). Vira 401 genérico."""


class DiretorioIndisponivel(Exception):
    """O diretório do mock não respondeu. Vira 503: não é o mesmo que "funcionário não existe"."""


@dataclass(frozen=True)
class Acesso:
    """A mesma pessoa nas duas camadas. `ferramentas` é None para quem não usa ferramentas."""

    conta: models.Usuario
    pessoa: seg.Usuario  # camada 1: acesso ao agente (seguranca/)
    ferramentas: governanca.Usuario | None  # camada 2: acesso à ferramenta (governanca.py)


def montar_acesso(sessao: Session, id_usuario: str) -> Acesso:
    """Lê a pessoa do banco e do diretório e devolve as duas camadas, ou levanta AcessoRecusado."""
    conta = sessao.get(models.Usuario, id_usuario) if isinstance(id_usuario, str) else None
    if conta is None:
        raise AcessoRecusado
    classe = PERFIS.get(conta.perfil)
    if classe is None:  # perfil fora de ROLES: negar por padrão
        raise AcessoRecusado

    area_slug = conta.area
    ferramentas = None
    if conta.id_funcionario:
        try:
            # Ponto único da checagem de situação (D11): só `ativo` passa.
            ferramentas = diretorio.buscar_usuario(conta.id_funcionario)
        except ConnectionError:
            raise DiretorioIndisponivel from None
        if ferramentas is None:
            raise AcessoRecusado
        area_slug = ferramentas.area  # a área vem do cargo, não de uma cópia no banco
    elif classe.usa_ferramentas:
        raise AcessoRecusado  # quem usa ferramentas precisa estar no diretório

    try:
        pessoa = _pessoa(classe, conta, area_slug)
    except ValueError:  # área ausente ou desconhecida para um perfil que exige área
        raise AcessoRecusado from None
    return Acesso(conta, pessoa, ferramentas if classe.usa_ferramentas else None)


def _pessoa(classe: type[seg.Usuario], conta: models.Usuario, area_slug: str | None) -> seg.Usuario:
    area = seg.area_do_slug(area_slug) if area_slug else None
    # O nome na camada 1 é o id: a auditoria guarda só o id, nunca o nome da pessoa.
    if classe is seg.Supervisor:
        extras = {seg.area_do_slug(slug) for slug in conta.areas_extras or ()}
        return classe(conta.id, area, id=conta.id, areas_extras=extras)
    return classe(conta.id, area, id=conta.id)


def nome_da_area(area: seg.Area | None) -> str | None:
    """Nome da área como o contrato da interface usa (`Financeiro`, `AtendimentoCliente`)."""
    return type(area).__name__ if area is not None else None


# ---------------------------------------------------------------- camada 1 por pedido (porta 2)
def agente_da_linha(linha: models.Agente, convidados: set[str]) -> seg.Agente:
    """O `seguranca.Agente` montado com o que veio do banco."""
    if linha.dono_id == seg.DONO_PLATAFORMA:
        agente = seg.Agente.da_plataforma(linha.nome, id=linha.id)
        agente.ativo = linha.ativo
        return agente
    return seg.Agente(
        nome=linha.nome,
        area=seg.area_do_slug(linha.area),
        dono_id=linha.dono_id,
        id=linha.id,
        convidados_ids=convidados,
        visibilidade=linha.visibilidade,
        ativo=linha.ativo,
    )


def plataforma_do_pedido(
    acesso: Acesso, linhas: list[models.Agente], convidados: dict[str, set[str]]
) -> tuple[seg.Plataforma, dict[str, seg.Agente]]:
    """Uma `Plataforma` NOVA para este pedido, com a pessoa e os agentes lidos agora do banco.

    Nunca reaproveitar entre pedidos nem usar a global `PLATAFORMA` (seguranca/CLAUDE.md, passo 3).
    """
    # [A FAZER (Marcelo e Isabel, back-end, KAN-60): ligar ao_registrar à gravação na tabela auditoria]
    plataforma = seg.Plataforma()
    plataforma.cadastrar(acesso.pessoa)
    agentes = {}
    for linha in linhas:
        agente = agente_da_linha(linha, convidados.get(linha.id, set()))
        plataforma.carregar_agente(agente)
        agentes[linha.id] = agente
    return plataforma, agentes


def acoes_permitidas(pessoa: seg.Usuario, agente: seg.Agente) -> list[str]:
    """Cada `Acao` que a pessoa pode fazer no agente (decide os botões da interface)."""
    return [acao.name for acao in seg.Acao if pessoa.pode(acao, agente)]


def relacao_com(pessoa: seg.Usuario, agente: seg.Agente) -> str:
    """Selo do cartão (frontend/CONTRATO_API.md, §4.2)."""
    if agente.dono_id == pessoa.id:
        return "dono"
    if isinstance(pessoa, seg.AdminGlobal):
        return "admin"
    if isinstance(pessoa, seg.Supervisor) and agente.area in pessoa.areas:
        return "supervisor"
    return "convidado"
