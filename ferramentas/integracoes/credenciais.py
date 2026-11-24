"""Credencial de cada pessoa (OAuth2) para as integrações em que a conta é do funcionário: Google Workspace e
Microsoft 365. A plataforma nunca pede a senha de ninguém: a pessoa autoriza no site do Google ou da Microsoft e
a plataforma guarda só o que o serviço devolve (token de acesso, de curta duração, e token de renovação).

O conector pede o token válido de uma pessoa a um `ProvedorDeCredencial`. Sem conta ligada, ou com a permissão
(escopo) que a ferramenta precisa ainda não concedida, o pedido falha com `integracao_indisponivel` e uma
mensagem que o agente repassa ("conta não ligada"). Quem escreve a ferramenta nunca vê o token.

O que o provedor faz sozinho (`token_de_acesso`): devolve o token se ele ainda vale (com margem), renova com o
token de renovação quando venceu, guarda o novo par, e apaga a conta se o serviço disse que a autorização acabou
(a pessoa revogou, a senha mudou, o administrador desligou o app). Duas renovações da mesma conta ao mesmo tempo
viram uma só (o Microsoft troca o token de renovação a cada uso, então a segunda falharia).

Quem guarda de verdade é o back-end. O provedor em memória daqui serve a testes e à demonstração: os tokens
somem quando o processo reinicia.

[A FAZER (Marcelo e Isabel, back-end, Sprint 3): um `ProvedorNoBanco(ProvedorDeCredencial)` com os três métodos
abstratos (`ler`, `guardar`, `apagar`) sobre uma tabela `credenciais_externas` (id_usuario, servico, escopos,
expira_em e os dois tokens CIFRADOS com uma chave do .env, nunca em texto puro), e `credenciais.usar(provedor)`
no `lifespan`. Só o token de renovação precisa ficar guardado de forma durável; o de acesso pode ficar em memória]
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ferramentas.base import ErroFerramenta

logger = logging.getLogger(__name__)

MARGEM_DE_VENCIMENTO = timedelta(seconds=60)  # renova um pouco antes de vencer, para o token não morrer no caminho


def agora():
    """Relógio dos tokens, em UTC. Os testes trocam esta função para o tempo passar."""
    return datetime.now(UTC)


class ContaNaoLigada(ErroFerramenta):
    """A pessoa ainda não ligou a conta (ou a autorização acabou). O agente avisa e não tenta de novo."""

    def __init__(self, rotulo):
        super().__init__(
            "integracao_indisponivel",
            f"A conta {rotulo} desta pessoa não está ligada. Avise o usuário para conectar a conta na tela de "
            "integrações e não tente de novo.",
        )


class PermissaoInsuficiente(ErroFerramenta):
    """A conta está ligada, mas sem a permissão que esta ferramenta pede (por exemplo, escrever na agenda)."""

    def __init__(self, rotulo, tipo_de_acesso):
        super().__init__(
            "integracao_indisponivel",
            f"A conta {rotulo} desta pessoa não deu a permissão de {tipo_de_acesso}. Avise o usuário para "
            "reconectar a conta na tela de integrações liberando essa permissão.",
        )


class ConcessaoRevogada(Exception):
    """O serviço disse que a autorização acabou (token de renovação revogado ou vencido). A conta precisa ser ligada de novo."""


@dataclass(frozen=True)
class Credencial:
    """O que o serviço entregou para uma pessoa. Os tokens ficam fora do `repr`, para nunca irem a um log."""

    access_token: str = field(repr=False)
    expira_em: datetime
    escopos: frozenset
    refresh_token: str | None = field(default=None, repr=False)

    def valida(self):
        return agora() + MARGEM_DE_VENCIMENTO < self.expira_em

    def cobre(self, escopos, mais_amplos):
        """True se cada escopo pedido foi concedido, ele mesmo ou um que o inclui (`mais_amplos[escopo]`)."""
        return all(
            escopo in self.escopos or any(maior in self.escopos for maior in mais_amplos.get(escopo, ()))
            for escopo in escopos
        )


class ProvedorDeCredencial(ABC):
    """Onde ficam as credenciais. A subclasse escreve só `ler`, `guardar` e `apagar`; o resto é daqui."""

    def __init__(self):
        self._trava_geral = threading.Lock()
        self._travas = {}

    @abstractmethod
    def ler(self, id_usuario, servico):
        """A `Credencial` da pessoa nesse serviço, ou None."""

    @abstractmethod
    def guardar(self, id_usuario, servico, credencial):
        """Grava (ou troca) a credencial da pessoa nesse serviço."""

    @abstractmethod
    def apagar(self, id_usuario, servico):
        """Esquece a credencial da pessoa nesse serviço. Sem credencial, não faz nada."""

    def ligada(self, id_usuario, servico):
        """True se a pessoa tem conta ligada (para a tela de conectores e para escolher Google ou Microsoft)."""
        return self.ler(id_usuario, servico) is not None

    def _trava_da_conta(self, id_usuario, servico):
        with self._trava_geral:
            return self._travas.setdefault((id_usuario, servico), threading.Lock())

    def token_de_acesso(self, id_usuario, fluxo, escopos, recusado=None):
        """Um token que vale agora para `id_usuario` com os `escopos`, ou `ContaNaoLigada` / `PermissaoInsuficiente`.

        `fluxo` é o `oauth.FluxoOAuth` do serviço (nome, rótulo, escopos mais amplos e `renovar`). `recusado` é o token
        que o serviço acabou de recusar com 401: se ele ainda é o guardado, renova na hora (mesmo sem ter vencido
        pelo relógio); se outra chamada já o trocou, devolve o novo."""
        credencial = self.ler(id_usuario, fluxo.nome)
        if credencial is None:
            raise ContaNaoLigada(fluxo.rotulo)
        if not credencial.cobre(escopos, fluxo.mais_amplos):
            raise PermissaoInsuficiente(fluxo.rotulo, fluxo.tipo_de_acesso(escopos))
        if credencial.valida() and credencial.access_token != recusado:
            return credencial.access_token
        return self._renovar(id_usuario, fluxo, recusado).access_token

    def _renovar(self, id_usuario, fluxo, recusado):
        with self._trava_da_conta(id_usuario, fluxo.nome):
            atual = self.ler(id_usuario, fluxo.nome)  # outra chamada pode ter renovado enquanto esperávamos a trava
            if atual is None or not atual.refresh_token:
                self.apagar(id_usuario, fluxo.nome)
                raise ContaNaoLigada(fluxo.rotulo)
            if atual.valida() and atual.access_token != recusado:
                return atual
            try:
                nova = fluxo.renovar(atual)
            except ConcessaoRevogada:
                return self._depois_da_concessao_revogada(id_usuario, fluxo, atual)
            self.guardar(id_usuario, fluxo.nome, nova)
            return nova

    def _depois_da_concessao_revogada(self, id_usuario, fluxo, usada):
        """O serviço recusou o token de renovação `usada`. Se ele ainda é o guardado, a autorização acabou e a conta
        é esquecida. Se outro processo já guardou um token novo (o serviço troca o de renovação a cada uso, e o
        nosso ficou velho), a conta continua ligada e vale a credencial nova: apagá-la desligaria quem não pediu."""
        guardada = self.ler(id_usuario, fluxo.nome)
        if guardada is not None and guardada.refresh_token != usada.refresh_token:
            if guardada.valida():
                return guardada
            raise ContaNaoLigada(fluxo.rotulo)  # a pessoa tenta de novo: a credencial guardada é a que renova
        self.apagar(id_usuario, fluxo.nome)
        logger.info("conta externa desligada pelo serviço: integracao=%s", fluxo.nome)
        raise ContaNaoLigada(fluxo.rotulo)


class ProvedorEmMemoria(ProvedorDeCredencial):
    """Testes e demonstração: um dicionário no processo. Nada é gravado em disco."""

    def __init__(self):
        super().__init__()
        self._contas = {}
        self._trava = threading.Lock()

    def ler(self, id_usuario, servico):
        with self._trava:
            return self._contas.get((id_usuario, servico))

    def guardar(self, id_usuario, servico, credencial):
        with self._trava:
            self._contas[(id_usuario, servico)] = credencial

    def apagar(self, id_usuario, servico):
        with self._trava:
            self._contas.pop((id_usuario, servico), None)

    def limpar(self):
        with self._trava:
            self._contas.clear()


_ATIVO = {"provedor": ProvedorEmMemoria()}


def usar(provedor):
    """Define o provedor de credenciais do processo (o back-end troca o de memória pelo do banco ao subir)."""
    if not isinstance(provedor, ProvedorDeCredencial):
        raise TypeError("provedor de credencial inválido")
    _ATIVO["provedor"] = provedor


def provedor():
    return _ATIVO["provedor"]
