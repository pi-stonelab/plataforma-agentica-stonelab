"""A confirmação liga a chave de idempotência às escritas do mock e trata a falha de cada jeito:

o id da confirmação vira a chave gravada junto da escrita; commit incerto vira "pode ter sido feito" e a prévia não
volta para a fila; recusa definitiva tira a prévia da fila; prévia vencida diz que venceu; cada escrita deixa no
registro o id do que criou (`referencia_externa`), nunca conteúdo.
"""

from datetime import timedelta

import pytest
from ferramentas import catalogo, confirmacoes, governanca
from mock import falhas  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.modelos import Acordo, Chamado, EscritaAplicada
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

ESCRITAS = tuple(governanca.ESCRITA_COM_CONFIRMACAO)
ANA, COBRANCA, COORDENADORA = gab.ANA, gab.COBRANCA, gab.COORDENADOR_FINANCEIRO
ABRIR_CHAMADO = {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Maquininha não liga.", "impede_vender": "sim"}


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def pessoa(engine, id_funcionario):
    return usuario_do_diretorio(engine, id_funcionario)


def preparar(engine, nome, argumentos, id_funcionario):
    previa = catalogo.executar(nome, argumentos, pessoa(engine, id_funcionario), ESCRITAS)
    assert previa["status"] == "ok", previa
    return previa["dados"]["confirmacao_id"]


def contar(engine, modelo):
    with Session(engine) as sessao:
        return sessao.scalar(select(func.count()).select_from(modelo))


def test_o_id_da_confirmacao_vira_a_chave_gravada_com_o_codigo_do_que_foi_criado(engine):
    confirmacao_id = preparar(engine, "abrir_chamado", ABRIR_CHAMADO, ANA)
    feito = confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))
    assert feito["status"] == "ok"
    with Session(engine) as sessao:
        marca = sessao.get(EscritaAplicada, confirmacao_id)
    assert (marca.operacao, marca.codigo_resultado) == ("abrir_chamado", feito["dados"]["id_chamado"])
    assert confirmacoes.CONFIRMACAO_EM_CURSO.get() is None  # a marca não vaza para o próximo pedido


def test_commit_incerto_diz_que_pode_ter_sido_feito_e_a_previa_nao_volta_para_a_fila(engine):
    confirmacao_id = preparar(engine, "abrir_chamado", ABRIR_CHAMADO, ANA)
    antes = contar(engine, Chamado)

    def cair_depois_do_commit(_sessao):
        raise OperationalError("COMMIT", {}, Exception("conexão caiu"))

    event.listen(Session, "after_commit", cair_depois_do_commit)
    try:
        resultado = confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))
    finally:
        event.remove(Session, "after_commit", cair_depois_do_commit)
    assert (resultado["tipo_erro"], resultado["mensagem"]) == ("integracao_indisponivel", confirmacoes.mensagem_efeito_incerto(catalogo.carregar()["abrir_chamado"]))
    assert contar(engine, Chamado) == antes + 1  # o commit chegou ao banco
    repetida = confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))
    assert repetida["tipo_erro"] == "nao_encontrado" and contar(engine, Chamado) == antes + 1


def test_sistema_fora_do_ar_antes_de_gravar_devolve_a_previa_para_a_fila(engine):
    confirmacao_id = preparar(engine, "abrir_chamado", ABRIR_CHAMADO, ANA)
    antes = contar(engine, Chamado)
    falhas.ligar("crm")
    resultado = confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))
    falhas.desligar_todas()
    assert resultado["tipo_erro"] == "integracao_indisponivel" and contar(engine, Chamado) == antes
    assert confirmacoes.confirmacao_para_interface(confirmacao_id, pessoa(engine, ANA)) is not None
    assert confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))["status"] == "ok"  # agora grava, uma vez só
    assert contar(engine, Chamado) == antes + 1


def test_recusa_definitiva_tira_a_previa_da_fila_e_a_repeticao_ouve_que_foi_recusada(engine):
    confirmacao_id = preparar(engine, "aprovar_acordo", {"id_acordo": "AC0002", "decisao": "aprovar"}, COORDENADORA)
    with Session(engine) as sessao, sessao.begin():  # outra pessoa decidiu o acordo antes desta confirmação
        sessao.get(Acordo, "AC0002").situacao = "recusado"
    resultado = confirmacoes.confirmar(confirmacao_id, pessoa(engine, COORDENADORA))
    assert resultado["status"] == "erro" and resultado["tipo_erro"] == "parametro_invalido"
    assert confirmacoes.MENSAGEM_PREVIA_ENCERRADA in resultado["mensagem"]
    assert confirmacoes.confirmacao_para_interface(confirmacao_id, pessoa(engine, COORDENADORA)) is None
    assert confirmacoes.situacao_da_decisao(confirmacao_id, pessoa(engine, COORDENADORA)) == confirmacoes.RECUSADA
    repetida = confirmacoes.confirmar(confirmacao_id, pessoa(engine, COORDENADORA))
    assert repetida["mensagem"] == confirmacoes.MENSAGEM_JA_DECIDIDA[confirmacoes.RECUSADA]


def test_previa_vencida_diz_que_venceu_e_continua_sendo_nao_encontrada(engine, monkeypatch):
    confirmacao_id = preparar(engine, "abrir_chamado", ABRIR_CHAMADO, ANA)
    depois = confirmacoes.agora() + confirmacoes.VALIDADE + timedelta(seconds=1)
    monkeypatch.setattr(confirmacoes, "agora", lambda: depois)
    resultado = confirmacoes.confirmar(confirmacao_id, pessoa(engine, ANA))
    assert resultado["tipo_erro"] == "nao_encontrado" and "expirou" in resultado["mensagem"]
    assert confirmacoes.confirmar("CONF-QUE-NAO-EXISTE", pessoa(engine, ANA))["mensagem"] == confirmacoes.MENSAGEM_NAO_ENCONTRADO


CASOS_COM_REFERENCIA = {
    "abrir_chamado": (ABRIR_CHAMADO, ANA, "CH"),
    "adicionar_nota_chamado": ({"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Resumo."}, ANA, "CH"),
    "atualizar_situacao_chamado": (
        {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "nova_situacao": "em_atendimento"}, ANA, "CH"),
    "registrar_pedido_antecipacao": (
        {"id_cliente": gab.C4_LOJISTA, "resumo": "Quer antecipar tudo."}, gab.ATENDENTE_PME, "CH"),
    "registrar_acordo": ({"id_cliente": gab.C3_LOJISTA, "numero_parcelas": gab.C3_PARCELAS}, COBRANCA, "AC"),
    "aprovar_acordo": ({"id_acordo": "AC0002", "decisao": "aprovar"}, COORDENADORA, "AC"),
}


@pytest.mark.parametrize("nome", sorted(CASOS_COM_REFERENCIA))
def test_cada_escrita_deixa_no_registro_o_id_do_que_criou_e_nenhum_conteudo(engine, nome):
    argumentos, quem, prefixo = CASOS_COM_REFERENCIA[nome]
    confirmacoes.confirmar(preparar(engine, nome, argumentos, quem), pessoa(engine, quem))
    ultimo = [r for r in governanca.REGISTROS if r["ferramenta"] == nome][-1]
    assert ultimo["referencia_externa"].startswith(prefixo), ultimo
    assert "Maquininha não liga" not in str(ultimo) and "Resumo." not in str(ultimo)
