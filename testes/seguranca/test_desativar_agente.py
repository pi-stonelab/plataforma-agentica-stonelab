"""Agente desativado (ativo=False) não pode mais ser usado, só visto.

Regra esperada:
- Plataforma.deprecar(usuario, agente) desativa o agente do cadastro, se o usuário
  puder Acao.DEPRECAR nele, e registra a tentativa na auditoria.
- Em agente inativo, só Acao.VER continua permitida (para histórico).
  EXECUTAR, EDITAR, CONVIDAR e DEPRECAR são negadas para todos, inclusive o AdminGlobal.
- O ativo que vale é o do cadastro, nunca o do objeto recebido.
"""

from dataclasses import replace

import pytest

from seguranca.envelope import exige_permissao
from seguranca.permissoes import (
    Acao,
    AcessoNegado,
    AdminGlobal,
    AtendimentoCliente,
    Financeiro,
    GestorDeAcessos,
    Supervisor,
    Visibilidade,
)

ACOES_BLOQUEADAS = [Acao.EXECUTAR, Acao.EDITAR, Acao.CONVIDAR, Acao.DEPRECAR]


@pytest.fixture
def admin(plataforma):
    return plataforma.cadastrar(AdminGlobal("Ana", Financeiro()))


# ---------------------------------------------------------------- o campo ativo é respeitado


@pytest.mark.parametrize("acao", ACOES_BLOQUEADAS, ids=lambda a: a.name)
def test_dono_nao_usa_agente_inativo(plataforma, maria, triagem, acao):
    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(maria, acao, triagem)


@pytest.mark.parametrize("acao", ACOES_BLOQUEADAS, ids=lambda a: a.name)
def test_admin_nao_usa_agente_inativo(plataforma, admin, triagem, acao):
    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(admin, acao, triagem)


def test_convidado_nao_executa_agente_inativo(plataforma, maria, joao, triagem):
    plataforma.convidar(maria, joao, triagem)
    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.EXECUTAR, triagem)


def test_dono_ainda_ve_agente_inativo(plataforma, maria, triagem):
    triagem.ativo = False
    plataforma.autorizar(maria, Acao.VER, triagem)
    assert triagem in plataforma.agentes_visiveis(maria)


def test_quem_nao_via_continua_sem_ver_agente_inativo(plataforma, joao, triagem):
    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.VER, triagem)


def test_decorator_nega_execucao_de_agente_inativo(plataforma, maria, triagem):
    @exige_permissao(Acao.EXECUTAR, plataforma=plataforma)
    def rodar_agente(usuario, agente, pergunta):
        return "rodou"

    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        rodar_agente(maria, triagem, "oi")


def test_copia_dizendo_ativo_nao_reativa(plataforma, maria, triagem):
    """O ativo que vale é o do cadastro (depende também da correção do ponto 1)."""
    triagem.ativo = False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(maria, Acao.EXECUTAR, replace(triagem, ativo=True))


# ---------------------------------------------------------------- deprecar


def test_dono_desativa_o_proprio_agente(plataforma, maria, triagem):
    plataforma.deprecar(maria, triagem)
    assert triagem.ativo is False
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(maria, Acao.EXECUTAR, triagem)


def test_supervisor_da_area_desativa(plataforma, maria, triagem):
    # o supervisor não vê agente privado de outra pessoa (decisão do grupo): o dono abre antes
    plataforma.alterar_visibilidade(maria, triagem, Visibilidade.CONVIDADOS)
    bia = plataforma.cadastrar(Supervisor("Bia", AtendimentoCliente()))
    plataforma.deprecar(bia, triagem)
    assert triagem.ativo is False


def test_admin_desativa(plataforma, admin, triagem):
    plataforma.deprecar(admin, triagem)
    assert triagem.ativo is False


def test_convidado_nao_desativa(plataforma, maria, joao, triagem):
    plataforma.convidar(maria, joao, triagem)
    with pytest.raises(AcessoNegado):
        plataforma.deprecar(joao, triagem)
    assert triagem.ativo is True


def test_estranho_nao_desativa(plataforma, joao, triagem):
    with pytest.raises(AcessoNegado):
        plataforma.deprecar(joao, triagem)
    assert triagem.ativo is True


def test_gestor_nao_desativa(plataforma, triagem):
    carla = plataforma.cadastrar(GestorDeAcessos("Carla", Financeiro()))
    with pytest.raises(AcessoNegado):
        plataforma.deprecar(carla, triagem)
    assert triagem.ativo is True


def test_deprecar_com_copia_desativa_o_agente_do_cadastro(plataforma, maria, triagem):
    plataforma.deprecar(maria, replace(triagem))
    assert triagem.ativo is False


def test_deprecar_vai_para_auditoria(plataforma, maria, joao, triagem):
    with pytest.raises(AcessoNegado):
        plataforma.deprecar(joao, triagem)
    plataforma.deprecar(maria, triagem)
    eventos = [e for e in plataforma.auditoria if e.acao == "DEPRECAR"]
    assert [(e.id_usuario, e.permitido) for e in eventos] == [(joao.id, False), (maria.id, True)]
    assert all(e.alvo == str(triagem.id) for e in eventos)
