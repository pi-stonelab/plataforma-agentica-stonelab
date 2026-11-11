"""
Perfis de acesso da Plataforma Agêntica (RBAC por hierarquia + área + convite).

Nível 1 - AdminGlobal:  vê e gerencia todos os agentes.
Nível 2 - Supervisor:   vê e gerencia todos os agentes da(s) sua(s) área(s).
Nível 3 - Colaborador:  vê apenas agentes que criou ou para os quais foi convidado.
GestorDeAcessos:        só atribui e remove roles/áreas; não vê nem cria agentes
                        e não pode alterar a própria role (separação de funções).

Os níveis 1 a 3 podem criar agentes. A regra de visibilidade fica em cada classe
(polimorfismo), então adicionar um novo perfil = criar uma nova subclasse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from itertools import count
from uuid import uuid4


class Area(ABC):
    """Classe abstrata: só existe para ser herdada pelas áreas concretas."""

    @property
    @abstractmethod
    def nome(self) -> str: ...

    # duas instâncias da mesma área são consideradas iguais
    def __eq__(self, outra: object) -> bool:
        return type(self) is type(outra)

    def __hash__(self) -> int:
        return hash(type(self))

    def __repr__(self) -> str:
        return self.nome


class Financeiro(Area):
    nome = "Financeiro"


class AtendimentoCliente(Area):
    nome = "Atendimento ao cliente"


class Acao(Enum):
    VER = auto()
    EXECUTAR = auto()
    EDITAR = auto()
    CONVIDAR = auto()
    DEPRECAR = auto()


class AcessoNegado(Exception):
    pass


# ---------------------------------------------------------------- Agente
_ids = count(1)


@dataclass
class Agente:
    nome: str
    area: Area
    dono: Usuario
    id: int = field(default_factory=lambda: next(_ids))
    convidados: set[Usuario] = field(default_factory=set)
    ativo: bool = True

    def __hash__(self) -> int:
        return hash(self.id)


# ---------------------------------------------------------------- Usuários
class Usuario(ABC):
    nivel: int = 0

    def __init__(self, nome: str, area: Area, id: str | None = None):
        # o id é a identidade da pessoa: continua o mesmo quando a role muda
        self.id = id or str(uuid4())
        self.nome = nome
        self.area = area

    def criar_agente(self, nome: str, plataforma: Plataforma) -> Agente:
        agente = Agente(nome=nome, area=self.area, dono=self)
        plataforma.registrar(agente, self)
        return agente

    def eh_dono_ou_convidado(self, agente: Agente) -> bool:
        return agente.dono == self or self in agente.convidados

    @abstractmethod
    def pode(self, acao: Acao, agente: Agente) -> bool:
        """Regra de autorização específica de cada perfil."""

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Usuario) and self.id == outro.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nome}, {self.area.nome})"


class AdminGlobal(Usuario):
    nivel = 1

    def pode(self, acao: Acao, agente: Agente) -> bool:
        return True


class Supervisor(Usuario):
    nivel = 2

    def __init__(self, nome: str, area: Area, id: str | None = None,
                 areas_extras: set[Area] | None = None):
        super().__init__(nome, area, id)
        self.areas = {area} | (areas_extras or set())

    def pode(self, acao: Acao, agente: Agente) -> bool:
        if agente.area in self.areas or agente.dono == self:
            return True
        # fora da sua área, convidado só usa (igual ao Colaborador)
        return self in agente.convidados and acao in {Acao.VER, Acao.EXECUTAR}


class Colaborador(Usuario):
    nivel = 3

    def pode(self, acao: Acao, agente: Agente) -> bool:
        if agente.dono == self:
            return True  # dono tem controle total do próprio agente
        if self in agente.convidados:
            return acao in {Acao.VER, Acao.EXECUTAR}  # convidado só usa
        return False


class GestorDeAcessos(Usuario):
    """Só administra roles. Não tem nenhum acesso a agentes."""

    nivel = 0

    def pode(self, acao: Acao, agente: Agente) -> bool:
        return False

    def criar_agente(self, nome: str, plataforma: Plataforma) -> Agente:
        raise AcessoNegado(f"{self} não cria agentes")

    # único dever do gestor: a regra e o log ficam centralizados na Plataforma
    def atribuir_role(self, alvo: Usuario, nova_role: type[Usuario],
                      plataforma: Plataforma, area: Area | None = None) -> Usuario:
        return plataforma.atribuir_role(self, alvo, nova_role, area)

    def remover_role(self, alvo: Usuario, plataforma: Plataforma) -> None:
        plataforma.remover_role(self, alvo)


ROLES: set[type[Usuario]] = {AdminGlobal, Supervisor, Colaborador, GestorDeAcessos}


# ---------------------------------------------------------------- Plataforma
@dataclass
class Evento:
    quando: datetime
    usuario: Usuario
    acao: str
    alvo: str  # id do agente ou do usuário afetado
    permitido: bool


class Plataforma:
    def __init__(self):
        self._agentes: dict[int, Agente] = {}
        self._usuarios: dict[str, Usuario] = {}
        self.auditoria: list[Evento] = []

    def _log(self, usuario, acao, alvo, ok):
        self.auditoria.append(Evento(datetime.now(UTC), usuario, acao, str(alvo), ok))

    # ---- usuários e roles
    def cadastrar(self, usuario: Usuario) -> Usuario:
        self._usuarios[usuario.id] = usuario
        return usuario

    def usuario(self, id: str) -> Usuario:
        return self._usuarios[id]

    def _atual(self, usuario: Usuario) -> Usuario | None:
        """Role vigente da pessoa, vinda do cadastro, nunca do objeto recebido.

        Sem isso, quem foi rebaixado ou removido mas guardou o objeto antigo
        continuaria com os poderes da role antiga.
        """
        return self._usuarios.get(getattr(usuario, "id", None))

    def _checar_gestor(self, gestor: Usuario, alvo: Usuario, acao: str) -> Usuario:
        atual = self._atual(gestor)
        if not isinstance(atual, GestorDeAcessos):
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{gestor} não pode administrar roles")
        if atual == alvo:
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{gestor} não pode alterar a própria role")
        if self._atual(alvo) is None:
            self._log(gestor, acao, alvo.id, False)
            raise AcessoNegado(f"{alvo} não está cadastrado")
        return atual

    def atribuir_role(self, gestor: Usuario, alvo: Usuario,
                      nova_role: type[Usuario], area: Area | None = None) -> Usuario:
        acao = f"ATRIBUIR_ROLE:{getattr(nova_role, '__name__', nova_role)}"
        self._checar_gestor(gestor, alvo, acao)
        if nova_role not in ROLES:
            self._log(gestor, acao, alvo.id, False)
            raise ValueError(f"Role desconhecida: {nova_role}")

        # mesma pessoa (mesmo id), nova classe de role
        novo = nova_role(alvo.nome, area or alvo.area, id=alvo.id)
        self._usuarios[alvo.id] = novo
        self._log(gestor, acao, alvo.id, True)
        return novo

    def remover_role(self, gestor: Usuario, alvo: Usuario) -> None:
        """Tira a role: a pessoa sai do cadastro e perde todo acesso."""
        self._checar_gestor(gestor, alvo, "REMOVER_ROLE")
        del self._usuarios[alvo.id]
        self._log(gestor, "REMOVER_ROLE", alvo.id, True)

    # ---- agentes
    def registrar(self, agente: Agente, criador: Usuario) -> None:
        atual = self._atual(criador)
        if atual is None or isinstance(atual, GestorDeAcessos):
            self._log(criador, "CRIAR", agente.id, False)
            raise AcessoNegado(f"{criador} não pode criar agentes")
        self._agentes[agente.id] = agente
        self._log(criador, "CRIAR", agente.id, True)

    def autorizar(self, usuario: Usuario, acao: Acao, agente: Agente) -> None:
        atual = self._atual(usuario)
        ok = atual is not None and atual.pode(acao, agente)
        self._log(usuario, acao.name, agente.id, ok)
        if not ok:
            raise AcessoNegado(f"{usuario} não pode {acao.name} em '{agente.nome}'")

    def convidar(self, quem: Usuario, convidado: Usuario, agente: Agente) -> None:
        self.autorizar(quem, Acao.CONVIDAR, agente)
        agente.convidados.add(convidado)

    def agentes_visiveis(self, usuario: Usuario) -> list[Agente]:
        atual = self._atual(usuario)
        if atual is None:
            return []
        return [a for a in self._agentes.values() if atual.pode(Acao.VER, a)]


# ---------------------------------------------------------------- Demo
if __name__ == "__main__":
    p = Plataforma()

    ceo = p.cadastrar(AdminGlobal("Ana", Financeiro()))
    sup_fin = p.cadastrar(Supervisor("Bruno", Financeiro()))
    joao = p.cadastrar(Colaborador("João", Financeiro()))
    maria = p.cadastrar(Colaborador("Maria", AtendimentoCliente()))
    gestor = p.cadastrar(GestorDeAcessos("Carla", Financeiro()))

    a1 = joao.criar_agente("Relatório de carteira", p)
    a2 = maria.criar_agente("Triagem de chamados", p)

    p.convidar(maria, joao, a2)

    for u in (ceo, sup_fin, joao, maria, gestor):
        print(f"{u}: {[a.nome for a in p.agentes_visiveis(u)]}")

    def tentar(descricao, func):
        try:
            func()
        except AcessoNegado as e:
            print(f"Bloqueado ({descricao}):", e)

    tentar("convidado edita", lambda: p.autorizar(joao, Acao.EDITAR, a2))
    tentar("gestor cria agente", lambda: gestor.criar_agente("X", p))
    tentar("gestor se promove",
           lambda: p.atribuir_role(gestor, gestor, AdminGlobal))
    tentar("admin atribui role",
           lambda: p.atribuir_role(ceo, joao, Supervisor))

    # gestor promove Maria a supervisora do Atendimento
    maria = gestor.atribuir_role(maria, Supervisor, p)
    print(f"Promovida: {maria}: {[a.nome for a in p.agentes_visiveis(maria)]}")

    # gestor remove a role de João: o objeto antigo dele deixa de valer
    gestor.remover_role(joao, p)
    tentar("removido usa agente", lambda: p.autorizar(joao, Acao.VER, a1))

    print("\nAuditoria de roles:")
    for e in p.auditoria:
        if "_ROLE" in e.acao:
            print(f"  {e.usuario.nome} -> {e.acao} em {e.alvo}: "
                  f"{'ok' if e.permitido else 'negado'}")
