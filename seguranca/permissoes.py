"""
Perfis de acesso da Plataforma Agêntica (RBAC por perfil + área + visibilidade do agente).

Perfis (cada um é uma subclasse de Usuario e decide em `pode()`):
  AdminGlobal:      opera a plataforma sem ver conteúdo (pausa/desativa qualquer agente,
                    vê só os não privados, nunca executa, edita ou convida).
  Supervisor:       gerencia os agentes não privados das suas áreas.
  Colaborador:      usa e gerencia o que é seu; usa o que foi aberto para ele.
  Auditor:          só lê a auditoria; não cria, não vê e não executa agentes.
  GestorDeAcessos:  só atribui e remove perfis; não vê nem cria agentes e não pode
                    alterar o próprio perfil (separação de funções).

A tabela completa de regras está em seguranca/README.md. Pessoas são guardadas por id
(nunca o objeto), e nenhuma mensagem de erro nem evento de auditoria leva nome.
Adicionar um novo perfil = criar uma nova subclasse de Usuario.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from itertools import count
from uuid import uuid4


# ---------------------------------------------------------------- Áreas
class Area(ABC):
    """Classe abstrata: só existe para ser herdada pelas áreas concretas."""

    @property
    @abstractmethod
    def nome(self) -> str: ...

    @property
    @abstractmethod
    def slug(self) -> str:
        """Texto curto e estável que liga a área ao resto do sistema (banco, ferramentas)."""

    # duas instâncias da mesma área são consideradas iguais
    def __eq__(self, outra: object) -> bool:
        return type(self) is type(outra)

    def __hash__(self) -> int:
        return hash(type(self))

    def __repr__(self) -> str:
        return self.nome


class Financeiro(Area):
    nome = "Financeiro"
    slug = "financeiro"


class AtendimentoCliente(Area):
    nome = "Atendimento ao cliente"
    slug = "atendimento"


AREAS: dict[str, type[Area]] = {a.slug: a for a in (AtendimentoCliente, Financeiro)}


def area_do_slug(slug: str) -> Area:
    """Converte o texto guardado no banco na área; slug desconhecido é erro (negar por padrão)."""
    if slug not in AREAS:
        raise ValueError("Área desconhecida")
    return AREAS[slug]()


# ---------------------------------------------------------------- Ações e visibilidade
class Acao(Enum):
    VER = auto()
    EXECUTAR = auto()
    EDITAR = auto()
    CONVIDAR = auto()
    DEPRECAR = auto()


class Visibilidade(Enum):
    """Quem pode usar o agente além do dono. O dono escolhe; publicar não exige aprovação."""

    PRIVADO = "privado"  # só o dono
    CONVIDADOS = "convidados"  # o dono e as pessoas que ele convidou
    PUBLICO = "publico"  # todos os funcionários das duas áreas


class AcessoNegado(Exception):
    pass


# ---------------------------------------------------------------- Agente
_ids = count(1)


@dataclass
class Agente:
    nome: str
    area: Area
    dono_id: str
    id: int | str | None = None  # vem do banco; só sem valor usamos o contador (demo e testes)
    convidados_ids: set[str] = field(default_factory=set)
    visibilidade: Visibilidade = Visibilidade.PRIVADO
    ativo: bool = True

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = next(_ids)
        if not isinstance(self.dono_id, str) or not self.dono_id:
            raise ValueError("Agente precisa do id do dono")
        # aceita o valor guardado no banco ("privado") e recusa qualquer outro
        self.visibilidade = Visibilidade(self.visibilidade)
        self.convidados_ids = set(self.convidados_ids)

    def __hash__(self) -> int:
        return hash(self.id)


# Regras compartilhadas pelos perfis (cada uma é uma pergunta simples sobre o agente)
USO = frozenset({Acao.VER, Acao.EXECUTAR})  # o que quem só usa o agente pode fazer
ABERTOS = (Visibilidade.CONVIDADOS, Visibilidade.PUBLICO)  # tudo que não é privado


def _gerencia(acao: Acao, agente: Agente) -> bool:
    """Dono (ou supervisor da área) faz tudo; agente inativo é o único que ninguém executa."""
    return acao is not Acao.EXECUTAR or agente.ativo


def _usa(usuario: Usuario, acao: Acao, agente: Agente) -> bool:
    """Quem não gerencia só vê e executa, e só se o agente está ativo e aberto para a pessoa."""
    if acao not in USO or not agente.ativo:
        return False
    if agente.visibilidade is Visibilidade.PUBLICO:
        return True
    return agente.visibilidade is Visibilidade.CONVIDADOS and usuario.id in agente.convidados_ids


# ---------------------------------------------------------------- Usuários
class Usuario(ABC):
    nivel: int = 0
    # Atributos de perfil: tudo falso por padrão, para um perfil novo nascer sem poder.
    usa_ferramentas: bool = False  # pode ter ferramentas de dados dentro de um agente
    cria_agentes: bool = False
    pode_ler_auditoria: bool = False

    def __init__(self, nome: str, area: Area | None = None, id: str | None = None):
        # o id é a identidade da pessoa: continua o mesmo quando o perfil muda
        self.id = id or str(uuid4())
        self.nome = nome
        self.area = area

    def criar_agente(self, nome: str, plataforma: Plataforma) -> Agente:
        agente = Agente(nome=nome, area=self.area, dono_id=self.id)
        plataforma.registrar(agente, self)
        return agente

    @abstractmethod
    def pode(self, acao: Acao, agente: Agente) -> bool:
        """Regra de autorização específica de cada perfil."""

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Usuario) and self.id == outro.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        # sem nome: o repr aparece em log e em mensagem de erro
        area = self.area.slug if self.area else "-"
        return f"{type(self).__name__}(id={self.id}, area={area})"


class AdminGlobal(Usuario):
    """Opera sem ver conteúdo: pausa qualquer agente e só enxerga os não privados."""

    nivel = 1

    def pode(self, acao: Acao, agente: Agente) -> bool:
        if acao is Acao.DEPRECAR:
            return True
        # nunca executa (não vê dado de lojista), não edita e não convida
        return acao is Acao.VER and agente.visibilidade in ABERTOS


class Supervisor(Usuario):
    nivel = 2
    usa_ferramentas = True
    cria_agentes = True

    def __init__(self, nome: str, area: Area, id: str | None = None,
                 areas_extras: set[Area] | None = None):
        if area is None:
            raise ValueError("Supervisor precisa de área")
        super().__init__(nome, area, id)
        self.areas = {area} | (areas_extras or set())

    def pode(self, acao: Acao, agente: Agente) -> bool:
        if agente.dono_id == self.id:
            return _gerencia(acao, agente)
        # privado de outra pessoa o supervisor não vê (decisão do grupo)
        if agente.visibilidade in ABERTOS and agente.area in self.areas:
            return _gerencia(acao, agente)
        # fora das suas áreas, vale o que vale para qualquer funcionário: só usa
        return _usa(self, acao, agente)


class Colaborador(Usuario):
    nivel = 3
    usa_ferramentas = True
    cria_agentes = True

    def __init__(self, nome: str, area: Area, id: str | None = None):
        if area is None:
            raise ValueError("Colaborador precisa de área")
        super().__init__(nome, area, id)

    def pode(self, acao: Acao, agente: Agente) -> bool:
        if agente.dono_id == self.id:
            return _gerencia(acao, agente)  # dono tem controle total do próprio agente
        return _usa(self, acao, agente)


class Auditor(Usuario):
    """Só lê a auditoria (D9). Não cria, não vê e não executa agentes."""

    pode_ler_auditoria = True

    def pode(self, acao: Acao, agente: Agente) -> bool:
        return False


class GestorDeAcessos(Usuario):
    """Só administra perfis. Não tem nenhum acesso a agentes."""

    def pode(self, acao: Acao, agente: Agente) -> bool:
        return False

    # único dever do gestor: a regra e o log ficam centralizados na Plataforma
    def atribuir_role(self, alvo: Usuario, nova_role: type[Usuario],
                      plataforma: Plataforma, area: Area | None = None) -> Usuario:
        return plataforma.atribuir_role(self, alvo, nova_role, area)

    def remover_role(self, alvo: Usuario, plataforma: Plataforma) -> None:
        plataforma.remover_role(self, alvo)


ROLES: set[type[Usuario]] = {AdminGlobal, Supervisor, Colaborador, Auditor, GestorDeAcessos}


# ---------------------------------------------------------------- Plataforma
@dataclass
class Evento:
    quando: datetime
    id_usuario: str  # só o id: o evento não carrega nome nem o objeto da pessoa
    acao: str
    alvo: str  # id do agente ou do usuário afetado
    permitido: bool


def _id_de(usuario: object) -> str:
    """Id textual de quem tentou a ação, sem nunca chamar repr/str em objeto desconhecido."""
    id_usuario = getattr(usuario, "id", None)
    return id_usuario if isinstance(id_usuario, str) else "desconhecido"


class Plataforma:
    """Cadastro e auditoria de UM pedido (no back-end, uma instância nova por pedido).

    `ao_registrar` é chamado a cada evento (por exemplo, para gravar no banco). Se ele falhar,
    a ação é negada: sem rastro, sem ação (falha fechada).
    """

    def __init__(self, ao_registrar: Callable[[Evento], None] | None = None):
        self._agentes: dict[int | str, Agente] = {}
        self._usuarios: dict[str, Usuario] = {}
        self.auditoria: list[Evento] = []
        self._ao_registrar = ao_registrar

    def _log(self, usuario: object, acao: str, alvo: object, ok: bool) -> None:
        evento = Evento(datetime.now(UTC), _id_de(usuario), acao, str(alvo), ok)
        if self._ao_registrar is not None:
            try:
                self._ao_registrar(evento)
            except Exception:  # noqa: BLE001 (falha fechada de propósito)
                evento.permitido = False  # nunca fica como "permitido" um evento não gravado
                self.auditoria.append(evento)
                raise AcessoNegado(f"{acao} negado: auditoria indisponível") from None
        self.auditoria.append(evento)

    # ---- usuários e perfis
    def cadastrar(self, usuario: Usuario) -> Usuario:
        self._usuarios[usuario.id] = usuario
        return usuario

    def usuario(self, id: str) -> Usuario:
        return self._usuarios[id]

    def _atual(self, usuario: object) -> Usuario | None:
        """Perfil vigente da pessoa, vindo do cadastro, nunca do objeto recebido.

        Sem isso, quem foi rebaixado ou removido mas guardou o objeto antigo
        continuaria com os poderes do perfil antigo.
        """
        try:
            return self._usuarios.get(getattr(usuario, "id", None))
        except TypeError:  # id que não é hashable
            return None

    def _checar_gestor(self, gestor: Usuario, alvo: Usuario, acao: str) -> Usuario:
        atual = self._atual(gestor)
        if not isinstance(atual, GestorDeAcessos):
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{acao} negado: só o gestor de acessos administra perfis")
        if atual == alvo:
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{acao} negado: o gestor não altera o próprio perfil")
        if self._atual(alvo) is None:
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{acao} negado: pessoa {alvo.id} não está cadastrada")
        return atual

    def atribuir_role(self, gestor: Usuario, alvo: Usuario,
                      nova_role: type[Usuario], area: Area | None = None) -> Usuario:
        acao = f"ATRIBUIR_ROLE:{getattr(nova_role, '__name__', nova_role)}"
        self._checar_gestor(gestor, alvo, acao)
        if nova_role not in ROLES:
            self._log(gestor, acao, alvo.id, False)
            raise ValueError(f"Role desconhecida: {nova_role}")

        # mesma pessoa (mesmo id), nova classe de perfil
        try:
            novo = nova_role(alvo.nome, area or alvo.area, id=alvo.id)
        except ValueError:  # ex.: Colaborador sem área
            self._log(gestor, acao, alvo.id, False)
            raise
        self._log(gestor, acao, alvo.id, True)  # grava antes de mudar: sem rastro, sem mudança
        self._usuarios[alvo.id] = novo
        return novo

    def remover_role(self, gestor: Usuario, alvo: Usuario) -> None:
        """Tira o perfil: a pessoa sai do cadastro e perde todo acesso."""
        self._checar_gestor(gestor, alvo, "REMOVER_ROLE")
        self._log(gestor, "REMOVER_ROLE", alvo.id, True)
        del self._usuarios[alvo.id]

    # ---- agentes
    def registrar(self, agente: Agente, criador: Usuario) -> None:
        atual = self._atual(criador)
        # só cria quem tem perfil que cria, e só em nome de si mesmo
        if atual is None or not atual.cria_agentes or agente.dono_id != atual.id:
            self._log(criador, "CRIAR", agente.id, False)
            raise AcessoNegado(f"CRIAR negado no agente {agente.id}")
        self._log(criador, "CRIAR", agente.id, True)
        self._agentes[agente.id] = agente

    def autorizar(self, usuario: Usuario, acao: Acao, agente: Agente) -> None:
        atual = self._atual(usuario)
        try:
            ok = atual is not None and atual.pode(acao, agente)
            if acao is Acao.EXECUTAR and not agente.ativo:
                ok = False  # cinto de segurança: vale mesmo para um perfil novo que esqueça disso
        except Exception:  # noqa: BLE001 (agente ou regra com defeito: nega)
            ok = False
        alvo = getattr(agente, "id", "desconhecido")
        self._log(usuario, acao.name, alvo, ok)
        if not ok:
            raise AcessoNegado(f"{acao.name} negado no agente {alvo}")

    def convidar(self, quem: Usuario, convidado: Usuario, agente: Agente) -> None:
        self.autorizar(quem, Acao.CONVIDAR, agente)
        if self._atual(convidado) is None:
            self._log(quem, "CONVIDAR_PESSOA_DESCONHECIDA", agente.id, False)
            raise AcessoNegado(f"CONVIDAR negado: pessoa {_id_de(convidado)} não está cadastrada")
        agente.convidados_ids.add(convidado.id)

    def agentes_visiveis(self, usuario: Usuario) -> list[Agente]:
        atual = self._atual(usuario)
        if atual is None:
            return []
        return [a for a in self._agentes.values() if atual.pode(Acao.VER, a)]

    # ---- auditoria
    def ler_auditoria(self, usuario: Usuario) -> list[Evento]:
        """Só o perfil com `pode_ler_auditoria` (Auditor) lê; a própria leitura é registrada."""
        atual = self._atual(usuario)
        ok = atual is not None and atual.pode_ler_auditoria
        self._log(usuario, "LER_AUDITORIA", "auditoria", ok)
        if not ok:
            raise AcessoNegado("LER_AUDITORIA negado")
        return list(self.auditoria)


# ---------------------------------------------------------------- Demo
if __name__ == "__main__":
    p = Plataforma()

    # ids neutros: a demo imprime ids, nunca nomes
    adm = p.cadastrar(AdminGlobal("Ana", id="adm-1"))
    sup_fin = p.cadastrar(Supervisor("Bruno", Financeiro(), id="sup-1"))
    joao = p.cadastrar(Colaborador("João", Financeiro(), id="col-1"))
    maria = p.cadastrar(Colaborador("Maria", AtendimentoCliente(), id="col-2"))
    gestor = p.cadastrar(GestorDeAcessos("Carla", Financeiro(), id="ges-1"))
    auditor = p.cadastrar(Auditor("Davi", id="aud-1"))

    a1 = joao.criar_agente("Relatório de carteira", p)  # privado
    a2 = maria.criar_agente("Triagem de chamados", p)
    a2.visibilidade = Visibilidade.CONVIDADOS
    a3 = maria.criar_agente("Perguntas frequentes", p)
    a3.visibilidade = Visibilidade.PUBLICO

    p.convidar(maria, joao, a2)

    for u in (adm, sup_fin, joao, maria, gestor, auditor):
        print(f"{u}: ve {[a.id for a in p.agentes_visiveis(u)]}")

    def tentar(descricao, func):
        try:
            func()
        except AcessoNegado as e:
            print(f"Bloqueado ({descricao}):", e)

    tentar("convidado edita", lambda: p.autorizar(joao, Acao.EDITAR, a2))
    tentar("supervisor lê privado", lambda: p.autorizar(sup_fin, Acao.VER, a1))
    tentar("admin executa", lambda: p.autorizar(adm, Acao.EXECUTAR, a3))
    tentar("gestor cria agente", lambda: gestor.criar_agente("X", p))
    tentar("gestor se promove", lambda: p.atribuir_role(gestor, gestor, AdminGlobal))
    tentar("admin atribui role", lambda: p.atribuir_role(adm, joao, Supervisor))
    tentar("admin lê auditoria", lambda: p.ler_auditoria(adm))
    p.autorizar(adm, Acao.DEPRECAR, a1)  # admin pausa qualquer agente, sem ver o conteúdo
    a1.ativo = False
    tentar("dono executa agente inativo", lambda: p.autorizar(joao, Acao.EXECUTAR, a1))

    # gestor promove Maria a supervisora do Atendimento
    maria = gestor.atribuir_role(maria, Supervisor, p)
    print(f"Promovida: {maria}: ve {[a.id for a in p.agentes_visiveis(maria)]}")

    # gestor remove o perfil de João: o objeto antigo dele deixa de valer
    gestor.remover_role(joao, p)
    tentar("removido usa agente", lambda: p.autorizar(joao, Acao.VER, a1))

    print("\nAuditoria de perfis (lida pelo auditor):")
    for e in p.ler_auditoria(auditor):
        if "_ROLE" in e.acao:
            print(f"  {e.id_usuario} -> {e.acao} em {e.alvo}: {'ok' if e.permitido else 'negado'}")
