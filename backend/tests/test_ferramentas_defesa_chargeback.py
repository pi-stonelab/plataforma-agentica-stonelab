"""registrar_defesa_chargeback pelo catálogo e por cargo (cenário 2: chargeback com prazo acabando, M00002)."""

from datetime import date

import pytest
from ferramentas import catalogo, confirmacoes, governanca
from mock.modelos import Chargeback
from sqlalchemy import update
from sqlalchemy.orm import Session

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

TODAS = tuple(catalogo.nomes())
DISPUTAS, COORDENADOR = gab.DISPUTAS, gab.COORDENADOR_FINANCEIRO
CHARGEBACK = gab.C2_CHARGEBACK  # cenário 2: mercadoria não recebida, prazo amanhã, nenhum documento enviado
LOJISTA = "M00002"
ONTEM_NO_MOCK = date(2026, 10, 14)
NOTA = "nota fiscal"
ENTREGA = "comprovante de entrega (rastreio ou recibo assinado)"
NOTA_E_ENTREGA = "Nota fiscal, comprovante de entrega"


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def usar(engine, id_funcionario, **argumentos):
    argumentos = {"id_cliente": LOJISTA, "id_chargeback": CHARGEBACK, **argumentos}
    return catalogo.executar(
        "registrar_defesa_chargeback", argumentos, usuario_do_diretorio(engine, id_funcionario), TODAS
    )


def confirmar(engine, previa, id_funcionario):
    assert previa["status"] == "ok", previa
    return confirmacoes.confirmar(previa["dados"]["confirmacao_id"], usuario_do_diretorio(engine, id_funcionario))


def estado(engine):
    with Session(engine) as sessao:
        chargeback = sessao.get(Chargeback, CHARGEBACK)
        return chargeback.situacao, chargeback.documentos_enviados


def test_esta_na_lista_de_escritas_com_confirmacao_e_o_catalogo_a_conhece():
    assert "registrar_defesa_chargeback" in governanca.ESCRITA_COM_CONFIRMACAO
    assert catalogo.carregar()["registrar_defesa_chargeback"].esta_ativa()


def test_previa_mostra_prazo_e_o_que_falta_sem_gravar_nada(engine):
    previa = usar(engine, DISPUTAS, documentos="nota fiscal")
    assert previa["status"] == "ok" and previa["dados"]["situacao"] == "aguardando_confirmacao"
    assert previa["dados"]["documentos_a_registrar"] == [NOTA]
    assert previa["dados"]["documentos_que_faltam"] == [ENTREGA]
    assert "incompleta" in previa["dados"]["o_que_acontece"]
    assert estado(engine) == ("aguardando_defesa", "")  # a prévia desfaz tudo


def test_defesa_incompleta_so_registra_e_segue_aguardando(engine):
    feito = confirmar(engine, usar(engine, DISPUTAS, documentos="nota_fiscal"), DISPUTAS)
    assert feito["status"] == "ok" and "incompleta" in feito["mensagem"]
    assert estado(engine) == ("aguardando_defesa", "nota_fiscal")


def test_defesa_completa_manda_o_caso_para_a_analise(engine):
    previa = usar(engine, DISPUTAS, documentos=NOTA_E_ENTREGA)
    assert previa["dados"]["documentos_que_faltam"] == ["nenhum"]
    feito = confirmar(engine, previa, DISPUTAS)
    assert feito["status"] == "ok" and "segue para a análise" in feito["mensagem"]
    assert estado(engine)[0] == "em_analise"


def test_segunda_parte_da_defesa_completa_a_primeira(engine):
    confirmar(engine, usar(engine, DISPUTAS, documentos="nota fiscal"), DISPUTAS)
    previa = usar(engine, DISPUTAS, documentos="Comprovante de entrega")
    assert previa["dados"]["documentos_ja_registrados"] == [NOTA]
    confirmar(engine, previa, DISPUTAS)
    assert estado(engine) == ("em_analise", "nota_fiscal,comprovante_entrega")


def test_documento_repetido_e_documento_que_o_motivo_nao_pede_sao_recusados(engine):
    confirmar(engine, usar(engine, DISPUTAS, documentos="nota fiscal"), DISPUTAS)
    repetido = usar(engine, DISPUTAS, documentos="nota fiscal")
    assert (repetido["status"], repetido["tipo_erro"]) == ("erro", "parametro_invalido")
    estranho = usar(engine, DISPUTAS, documentos="comprovante de entrega, política de cancelamento aceita pelo cliente")
    assert estranho["tipo_erro"] == "parametro_invalido"
    desconhecido = usar(engine, DISPUTAS, documentos="foto do gato")
    assert desconhecido["tipo_erro"] == "parametro_invalido" and "gato" not in desconhecido["mensagem"]


def test_prazo_vencido_e_chargeback_que_ja_nao_aguarda_sao_recusados_na_previa(engine):
    with Session(engine) as sessao, sessao.begin():
        sessao.execute(update(Chargeback).where(Chargeback.codigo == CHARGEBACK).values(prazo_defesa=ONTEM_NO_MOCK))
    vencido = usar(engine, DISPUTAS, documentos="nota fiscal")
    assert vencido["tipo_erro"] == "parametro_invalido" and "prazo de defesa acabou" in vencido["mensagem"]


def test_chargeback_de_outro_lojista_responde_como_o_que_nao_existe(engine):
    de_outro = usar(engine, DISPUTAS, id_cliente="M00001", documentos="nota fiscal")
    inexistente = usar(engine, DISPUTAS, id_chargeback="CB99999", documentos="nota fiscal")
    assert de_outro["tipo_erro"] == inexistente["tipo_erro"] == "nao_encontrado"
    assert de_outro["mensagem"] == inexistente["mensagem"]


def test_codigo_fora_do_formato_e_recusado(engine):
    assert usar(engine, DISPUTAS, id_chargeback="1", documentos="nota fiscal")["tipo_erro"] == "parametro_invalido"


def test_confirmar_duas_vezes_grava_uma_so_vez(engine):
    previa = usar(engine, DISPUTAS, documentos="nota fiscal")
    primeira = confirmar(engine, previa, DISPUTAS)
    segunda = confirmar(engine, previa, DISPUTAS)
    assert (primeira["status"], segunda["status"], segunda["tipo_erro"]) == ("ok", "erro", "nao_encontrado")
    assert estado(engine) == ("aguardando_defesa", "nota_fiscal")


@pytest.mark.parametrize("cargo,id_funcionario", [("analista_disputas", DISPUTAS), ("coordenador_financeiro", COORDENADOR)])
def test_quem_pode_registrar_a_defesa(engine, cargo, id_funcionario):
    assert usar(engine, id_funcionario, documentos="nota fiscal")["status"] == "ok", cargo


@pytest.mark.parametrize("id_funcionario", [gab.ANA, gab.COBRANCA, "F0002", gab.OUVIDORIA, "F0010", gab.SUPERVISOR_ATENDIMENTO])
def test_os_demais_cargos_nao_alcancam_a_ferramenta(engine, id_funcionario):
    resposta = usar(engine, id_funcionario, documentos="nota fiscal")
    assert resposta["tipo_erro"] == "ferramenta_inexistente"
    assert estado(engine) == ("aguardando_defesa", "")
