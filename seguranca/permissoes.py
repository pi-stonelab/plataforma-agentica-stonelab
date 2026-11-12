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

Negar por padrão: por isso há `try/except Exception` em `_log`, `autorizar` e no envelope
(`# noqa: BLE001`). Qualquer erro inesperado na checagem vira AcessoNegado, nunca permissão.

A tabela completa de regras está em seguranca/README.md. Pessoas são guardadas por id
(nunca o objeto), e nenhuma mensagem de erro nem evento de auditoria leva nome.
Adicionar um novo perfil = criar uma nova subclasse de Usuario.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum, auto
from itertools import count
from re import fullmatch
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

# Dono do agente geral. Não é id de pessoa: nenhum Usuario pode ter este id (ver Usuario.__init__),
# então ninguém é "dono" desse agente e ninguém o edita.
DONO_PLATAFORMA = "plataforma"


@dataclass
class Agente:
    nome: str
    area: Area | None  # None só para o agente da plataforma (dono_id == DONO_PLATAFORMA)
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
        if (self.area is None) != (self.dono_id == DONO_PLATAFORMA):
            raise ValueError("Só o agente da plataforma fica sem área, e ele nunca tem área")
        if self.area is not None and not isinstance(self.area, Area):
            raise ValueError("Área inválida")
        # aceita o valor guardado no banco ("privado") e recusa qualquer outro
        self.visibilidade = Visibilidade(self.visibilidade)
        self.convidados_ids = set(self.convidados_ids)

    @classmethod
    def da_plataforma(cls, nome: str, id: int | str | None = None) -> Agente:
        """Agente geral: sem área, dono = plataforma, público. Ninguém o edita; o Admin o pausa."""
        return cls(nome, None, DONO_PLATAFORMA, id=id, visibilidade=Visibilidade.PUBLICO)

    def __hash__(self) -> int:
        return hash(self.id)


# Regras compartilhadas pelos perfis (cada uma é uma pergunta simples sobre o agente)
USO = frozenset({Acao.VER, Acao.EXECUTAR})  # o que quem só usa o agente pode fazer
ABERTOS = (Visibilidade.CONVIDADOS, Visibilidade.PUBLICO)  # tudo que não é privado


def _gerencia(acao: Acao, agente: Agente) -> bool:
    """Dono (ou supervisor da área) faz tudo, com duas exceções.

    - Agente inativo só aceita VER (regra do Brenno, PR #10).
    - Convidar não faz sentido em agente público, que todos já usam. Em privado e em
      convidados o dono pode convidar (decisão de Pedro, 12/11, ver H5).
    """
    if acao is not Acao.VER and not agente.ativo:
        return False
    if acao is Acao.CONVIDAR:
        return agente.visibilidade is not Visibilidade.PUBLICO
    return True


def _usa(usuario: Usuario, acao: Acao, agente: Agente) -> bool:
    """Quem não gerencia só vê e executa, e só se o agente está ativo e aberto para a pessoa."""
    if acao not in USO or not agente.ativo:
        return False
    if agente.visibilidade is Visibilidade.PUBLICO:
        return True
    return usuario.id in agente.convidados_ids  # a lista de convidados vale em privado e em convidados


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
        if self.id == DONO_PLATAFORMA:
            raise ValueError("Este id é reservado ao agente da plataforma")
        if area is not None and not isinstance(area, Area):
            raise ValueError("Área inválida: use Financeiro() ou AtendimentoCliente()")
        self.nome = nome
        self.area = area

    def criar_agente(self, nome: str, plataforma: Plataforma) -> Agente:
        if self.area is None:  # sem área não há agente para criar (Admin, Auditor...)
            plataforma._log(self, "CRIAR", "novo", False)
            raise AcessoNegado("CRIAR negado: perfil sem área")
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
            return agente.ativo  # agente já desativado só aceita VER
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
        extras = set(areas_extras or ())
        if not all(isinstance(extra, Area) for extra in extras):
            raise ValueError("Área inválida em areas_extras")
        self.areas = {area} | extras

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
def execucao_id_valido(valor: object) -> bool:
    """Id de execução seguro para auditoria e log: letras, números, '_' e '-', até 64 caracteres."""
    return isinstance(valor, str) and fullmatch(r"[A-Za-z0-9_-]{1,64}", valor) is not None


@dataclass(frozen=True)  # imutável: o gancho recebe o evento e não consegue alterá-lo
class Evento:
    quando: datetime
    id_usuario: str  # só o id: o evento não carrega nome nem o objeto da pessoa
    acao: str
    alvo: str  # id do agente ou do usuário afetado
    permitido: bool
    execucao_id: str | None = None  # liga o acesso ao registro de chamadas de ferramenta

    def __post_init__(self) -> None:
        if self.execucao_id is not None and not execucao_id_valido(self.execucao_id):
            raise ValueError("execucao_id inválido")


def _id_de(usuario: object) -> str:
    """Id textual de quem tentou a ação, sem nunca chamar repr/str em objeto desconhecido."""
    id_usuario = getattr(usuario, "id", None)
    return id_usuario if isinstance(id_usuario, str) else "desconhecido"


def _areas_do_usuario(usuario: Usuario | None) -> set[Area]:
    """Áreas em que a pessoa atua: as do Supervisor, ou a única área dos demais perfis."""
    if usuario is None:
        return set()
    return set(getattr(usuario, "areas", None) or ({usuario.area} if usuario.area else set()))


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

    def _log(self, usuario: object, acao: str, alvo: object, ok: bool,
             execucao_id: str | None = None) -> None:
        evento = Evento(datetime.now(UTC), _id_de(usuario), acao, str(alvo), ok, execucao_id)
        if self._ao_registrar is not None:
            try:
                self._ao_registrar(evento)
            except Exception:  # noqa: BLE001 (falha fechada de propósito)
                # nunca fica como "permitido" um evento não gravado
                self.auditoria.append(replace(evento, permitido=False))
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
        """Cria um agente NOVO em nome de quem tem perfil que cria (grava o evento CRIAR)."""
        atual = self._atual(criador)
        # só cria quem tem perfil que cria, em nome de si mesmo, na própria área, com id novo
        permitido = (
            atual is not None
            and atual.cria_agentes
            and agente.dono_id == atual.id
            and agente.area is not None
            and agente.area in _areas_do_usuario(atual)
            and agente.id not in self._agentes  # nunca sobrescreve um agente existente
        )
        self._log(criador, "CRIAR", agente.id, permitido)
        if not permitido:
            raise AcessoNegado(f"CRIAR negado no agente {agente.id}")
        self._agentes[agente.id] = agente

    def carregar_agente(self, agente: Agente) -> None:
        """Põe na Plataforma um agente que JÁ existe (lido do banco), sem evento CRIAR.

        Só o back-end usa, com o que veio do banco: nunca com dado da requisição nem do prompt.
        Não checa criador nem permissão (quem decide é `autorizar`). Serve também para o agente
        da plataforma, que não tem pessoa dona. Id repetido com outro agente é erro.
        """
        if not isinstance(agente, Agente):
            raise TypeError("carregar_agente precisa de um Agente")
        existente = self._agentes.get(agente.id)
        if existente is not None and existente is not agente:
            raise ValueError(f"Já existe outro agente com o id {agente.id}")
        self._agentes[agente.id] = agente

    def _registrado(self, agente: object) -> Agente | None:
        """O agente que a Plataforma conhece com o id recebido; senão None.

        Do objeto recebido só vale o id. Quem decide, e quem muda, é sempre o registrado:
        um objeto forjado ou desatualizado não ganha nem perde nada por dizer outra coisa.
        """
        try:
            registrado = self._agentes.get(getattr(agente, "id", None))
        except TypeError:  # id que não é hashable
            return None
        if registrado is None:
            return None
        return registrado

    def autorizar(self, usuario: Usuario, acao: Acao, agente: Agente,
                  execucao_id: str | None = None) -> Agente:
        """Decide, grava o evento e devolve o agente do cadastro.

        `execucao_id` (opcional) liga o evento à execução; inválido nega.
        Agente desativado só aceita VER, para todos, inclusive o admin.
        """
        return self._decidir(usuario, acao, agente, acao.name, execucao_id)

    def _decidir(self, usuario: Usuario, acao: Acao, agente: Agente, nome_do_evento: str,
                 execucao_id: str | None = None) -> Agente:
        """Decide sobre o agente registrado, grava UM evento e devolve o registrado."""
        atual = self._atual(usuario)
        registrado = self._registrado(agente)
        id_ok = execucao_id is None or execucao_id_valido(execucao_id)
        try:
            # agente não registrado ou diferente do registrado: negado (falha fechada)
            ok = registrado is not None and atual is not None and atual.pode(acao, registrado)
            ok = ok and id_ok
            if acao is not Acao.VER and (registrado is None or not registrado.ativo):
                ok = False  # agente desativado só aceita VER; vale mesmo para um perfil novo
        except Exception:  # noqa: BLE001 (agente ou regra com defeito: nega)
            ok = False
        alvo = getattr(agente, "id", "desconhecido")
        # id de execução inválido nunca vai para o evento (nem para o gancho): grava sem ele
        self._log(usuario, nome_do_evento, alvo, ok, execucao_id if id_ok else None)
        if not ok:
            raise AcessoNegado(f"{acao.name} negado no agente {alvo}")
        return registrado

    # ---- mudanças no ciclo de vida do agente: autorizam, gravam o evento e só então mudam
    def alterar_visibilidade(self, quem: Usuario, agente: Agente, nova: Visibilidade) -> None:
        """Muda a visibilidade (exige EDITAR). O evento leva o novo valor: ALTERAR_VISIBILIDADE:x."""
        nova = Visibilidade(nova)  # valor inválido é erro de programação, não de permissão
        registrado = self._decidir(quem, Acao.EDITAR, agente, f"ALTERAR_VISIBILIDADE:{nova.value}")
        registrado.visibilidade = nova

    def deprecar(self, quem: Usuario, agente: Agente) -> None:
        """Pausa o agente (exige DEPRECAR): depois disso só VER é permitido. Evento: DEPRECAR."""
        registrado = self._decidir(quem, Acao.DEPRECAR, agente, Acao.DEPRECAR.name)
        registrado.ativo = False

    def convidar(self, quem: Usuario, convidado: Usuario, agente: Agente) -> None:
        self.autorizar(quem, Acao.CONVIDAR, agente)
        if self._atual(convidado) is None:
            self._log(quem, "CONVIDAR_PESSOA_DESCONHECIDA", agente.id, False)
            raise AcessoNegado(f"CONVIDAR negado: pessoa {_id_de(convidado)} não está cadastrada")
        self._registrado(agente).convidados_ids.add(convidado.id)  # no registrado, não na cópia

    def agentes_visiveis(self, usuario: Usuario) -> list[Agente]:
        atual = self._atual(usuario)
        if atual is None:
            return []
        return [a for a in self._agentes.values() if atual.pode(Acao.VER, a)]

    # ---- auditoria
    def autorizar_leitura_auditoria(self, usuario: Usuario) -> None:
        """Só decide (Auditor sim; Admin não) e registra a tentativa. Não devolve eventos.

        A Plataforma vive um pedido só, então `self.auditoria` não é a auditoria da empresa.
        Quem lê é o chamador (o back-end), na tabela de auditoria, depois desta autorização.
        """
        atual = self._atual(usuario)
        ok = atual is not None and atual.pode_ler_auditoria
        self._log(usuario, "LER_AUDITORIA", "auditoria", ok)
        if not ok:
            raise AcessoNegado("LER_AUDITORIA negado")


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
    p.alterar_visibilidade(maria, a2, Visibilidade.CONVIDADOS)
    a3 = maria.criar_agente("Perguntas frequentes", p)
    p.alterar_visibilidade(maria, a3, Visibilidade.PUBLICO)

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
    tentar("admin lê auditoria", lambda: p.autorizar_leitura_auditoria(adm))
    p.deprecar(adm, a1)  # admin pausa qualquer agente, sem ver o conteúdo
    tentar("dono executa agente inativo", lambda: p.autorizar(joao, Acao.EXECUTAR, a1))

    # gestor promove Maria a supervisora do Atendimento
    maria = gestor.atribuir_role(maria, Supervisor, p)
    print(f"Promovida: {maria}: ve {[a.id for a in p.agentes_visiveis(maria)]}")

    # gestor remove o perfil de João: o objeto antigo dele deixa de valer
    gestor.remover_role(joao, p)
    tentar("removido usa agente", lambda: p.autorizar(joao, Acao.VER, a1))

    print("\nAuditoria de perfis (lida pelo auditor):")
    p.autorizar_leitura_auditoria(auditor)  # na demo a auditoria fica em memória; no back-end é a tabela
    for e in p.auditoria:
        if "_ROLE" in e.acao:
            print(f"  {e.id_usuario} -> {e.acao} em {e.alvo}: {'ok' if e.permitido else 'negado'}")
