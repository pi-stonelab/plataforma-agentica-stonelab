"""O autorizar deve decidir pelo agente do cadastro, nunca pelo objeto recebido.

Do objeto recebido só vale o id. Dono, convidados e área vêm de Plataforma._agentes,
do mesmo jeito que o perfil do usuário vem de Plataforma._usuarios (ver _atual).
"""

from dataclasses import replace

import pytest

from seguranca.envelope import exige_permissao
from seguranca.permissoes import Acao, AcessoNegado, Agente, Financeiro, Supervisor

# ---------------------------------------------------------------- continua funcionando


def test_dono_edita_o_proprio_agente(plataforma, maria, triagem):
    plataforma.autorizar(maria, Acao.EDITAR, triagem)


def test_convidado_executa(plataforma, maria, joao, triagem):
    plataforma.convidar(maria, joao, triagem)
    plataforma.autorizar(joao, Acao.EXECUTAR, triagem)


def test_quem_nao_e_dono_nem_convidado_e_negado(plataforma, joao, triagem):
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.VER, triagem)


# ---------------------------------------------------------------- objeto forjado


def test_copia_com_dono_trocado_e_negada(plataforma, joao, triagem):
    copia = replace(triagem, dono=joao)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.EDITAR, copia)


def test_copia_com_convidado_forjado_e_negada(plataforma, joao, triagem):
    copia = replace(triagem, convidados={joao})
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.EXECUTAR, copia)


def test_copia_com_area_trocada_nao_libera_supervisor(plataforma, triagem):
    bruno = plataforma.cadastrar(Supervisor("Bruno", Financeiro()))
    copia = replace(triagem, area=Financeiro())
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(bruno, Acao.EDITAR, copia)


def test_agente_nao_registrado_e_negado(plataforma, joao):
    fantasma = Agente("Fantasma", Financeiro(), dono=joao)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.EDITAR, fantasma)


def test_negacao_por_objeto_forjado_vai_para_auditoria(plataforma, joao, triagem):
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(joao, Acao.EDITAR, replace(triagem, dono=joao))
    ultimo = plataforma.auditoria[-1]
    assert ultimo.usuario == joao
    assert ultimo.acao == "EDITAR"
    assert ultimo.alvo == str(triagem.id)
    assert ultimo.permitido is False


# ---------------------------------------------------------------- objeto desatualizado


def test_copia_antiga_vale_o_que_esta_no_cadastro(plataforma, maria, joao, triagem):
    """João guardou uma cópia de antes do convite; o convite no cadastro é o que vale."""
    copia_antiga = replace(triagem, convidados=set())
    plataforma.convidar(maria, joao, triagem)
    plataforma.autorizar(joao, Acao.EXECUTAR, copia_antiga)


def test_convite_e_gravado_no_agente_do_cadastro(plataforma, maria, joao, triagem):
    copia = replace(triagem, convidados=set())
    plataforma.convidar(maria, joao, copia)
    assert joao in triagem.convidados
    plataforma.autorizar(joao, Acao.EXECUTAR, triagem)


def test_convite_com_copia_forjada_e_negado(plataforma, maria, joao, triagem):
    """João não pode se convidar passando uma cópia em que ele é o dono."""
    with pytest.raises(AcessoNegado):
        plataforma.convidar(joao, joao, replace(triagem, dono=joao))
    assert joao not in triagem.convidados


# ---------------------------------------------------------------- decorator


def test_decorator_nega_copia_forjada(plataforma, joao, triagem):
    @exige_permissao(Acao.EXECUTAR, plataforma=plataforma)
    def rodar_agente(usuario, agente, pergunta):
        return "rodou"

    with pytest.raises(AcessoNegado):
        rodar_agente(joao, replace(triagem, dono=joao), "oi")
