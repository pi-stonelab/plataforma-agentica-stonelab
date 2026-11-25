"""Regras de negócio das escritas sobre o mock, pelo catálogo e por cargo (blocos U1 a U16 da revisão de usuário).

O que a prévia mostra e o que a confirmação grava: antecipação parcial, pedido que não se executa por quem registrou,
resposta ao lojista em chamado com suspeita de fraude, acordos somados, acordo parado que se retira, parcelas que
fecham o saldo e a liquidação que o banco recusou.
"""

import re

import pytest
from ferramentas import catalogo, confirmacoes, governanca
from mock import falhas  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.gerar import LIQUIDACAO_RECUSADA_PELO_BANCO
from mock.modelos import Acordo, Antecipacao, Chamado, Fatura, Interacao, Liquidacao, Recebivel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

ESCRITAS = tuple(governanca.ESCRITA_COM_CONFIRMACAO)
TODAS = tuple(catalogo.nomes())
ANA, N1_PME, N2_PME, N2_VAREJO = gab.ANA, gab.ATENDENTE_PME, "F0005", "F0002"
COBRANCA, COORDENADORA, RECEBIVEIS = gab.COBRANCA, gab.COORDENADOR_FINANCEIRO, "F0010"
DATA_E_HORA_BR = re.compile(r"\d{2}/\d{2}/\d{4} às \d{2}:\d{2}")


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def pessoa(engine, id_funcionario):
    return usuario_do_diretorio(engine, id_funcionario)


def usar(engine, nome, argumentos, id_funcionario):
    return catalogo.executar(nome, argumentos, pessoa(engine, id_funcionario), TODAS)


def confirmar(engine, previa, id_funcionario):
    assert previa["status"] == "ok", previa
    return confirmacoes.confirmar(previa["dados"]["confirmacao_id"], pessoa(engine, id_funcionario))


def cartao(engine, previa, id_funcionario):
    return {c["rotulo"]: c["valor"] for c in confirmacoes.confirmacao_para_interface(
        previa["dados"]["confirmacao_id"], pessoa(engine, id_funcionario))["campos"]}


def contar(engine, modelo, *condicoes):
    with Session(engine) as sessao:
        return sessao.scalar(select(func.count()).select_from(modelo).where(*condicoes))


def pedido_de_antecipacao(engine, resumo="Quer antecipar só R$ 3.000."):
    feito = confirmar(engine, usar(engine, "registrar_pedido_antecipacao", {"id_cliente": "M00004", "resumo": resumo}, N1_PME), N1_PME)
    return feito["dados"]["id_chamado"]


# --- antecipação (U1, dev 7, U16) ------------------------------------------------------------------------


def test_previa_da_antecipacao_mostra_o_pedido_do_lojista_so_para_a_pessoa(engine):
    chamado = pedido_de_antecipacao(engine)
    previa = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": chamado}, N2_PME)
    assert "pedido_do_lojista" not in previa["dados"]  # o modelo não recebe o texto do chamado
    campos = cartao(engine, previa, N2_PME)
    assert campos["O que o lojista pediu"] == "Quer antecipar só R$ 3.000."
    assert campos["Quanto antecipar"] == "Toda a agenda disponível"


def test_antecipacao_parcial_mostra_e_grava_so_o_que_cabe_no_valor_pedido(engine):
    chamado = pedido_de_antecipacao(engine)
    previa = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": chamado, "valor_maximo": 3000}, N2_PME)
    assert previa["dados"]["alcance"] == "Até R$ 3.000,00, parcelas inteiras"
    feito = confirmar(engine, previa, N2_PME)
    assert feito["status"] == "ok"
    assert feito["dados"]["quantidade_de_parcelas"] == previa["dados"]["quantidade_de_parcelas"] < 25
    assert contar(engine, Recebivel, Recebivel.id_antecipacao.is_not(None)) == previa["dados"]["quantidade_de_parcelas"]


def test_antecipacao_com_valor_menor_que_uma_parcela_e_recusada_na_previa(engine):
    chamado = pedido_de_antecipacao(engine)
    previa = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": chamado, "valor_maximo": 0.5}, N2_PME)
    assert (previa["status"], previa["tipo_erro"]) == ("erro", "parametro_invalido")
    assert contar(engine, Antecipacao) == 0


def test_quem_registrou_o_pedido_nao_executa_a_antecipacao_nem_na_previa(engine):
    chamado = pedido_de_antecipacao(engine)  # registrado por F0004 (N1)
    mesma_pessoa = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": chamado}, N2_PME)
    assert mesma_pessoa["status"] == "ok"  # o N2 é outra pessoa
    outro_chamado = confirmar(engine, usar(engine, "registrar_pedido_antecipacao", {"id_cliente": "M00004", "resumo": "Outro."}, N2_PME), N2_PME)
    recusa = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": outro_chamado["dados"]["id_chamado"]}, N2_PME)
    assert (recusa["tipo_erro"], "registrou" in recusa["mensagem"]) == ("permissao_negada", True)
    assert contar(engine, Antecipacao) == 0


def test_coordenador_financeiro_nao_executa_antecipacao_o_8_2_da_so_ao_n2(engine):
    chamado = pedido_de_antecipacao(engine)
    resposta = usar(engine, "executar_antecipacao", {"id_cliente": "M00004", "id_chamado": chamado}, COORDENADORA)
    assert resposta["tipo_erro"] == "ferramenta_inexistente"  # o catálogo nem mostra a ferramenta a quem não pode
    assert governanca.motivo_bloqueio(catalogo.carregar()["executar_antecipacao"], pessoa(engine, COORDENADORA)) is not None


# --- chamados (U1, U2, U11) ------------------------------------------------------------------------------


def test_pedido_de_antecipacao_nao_se_abre_pelo_abrir_chamado(engine):
    resposta = usar(engine, "abrir_chamado", {"id_cliente": "M00004", "categoria": "Antecipação", "resumo": "Quer antecipar."}, N1_PME)
    assert resposta["tipo_erro"] == "parametro_invalido" and "registrar_pedido_antecipacao" in resposta["mensagem"]


@pytest.mark.parametrize("categoria", ["Pix e devolução", "Cancelamento da conta", "Reclamação do atendimento"])
def test_categorias_do_6_3_que_faltavam_abrem_chamado(engine, categoria):
    previa = usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": categoria, "resumo": "Teste."}, ANA)
    assert previa["status"] == "ok"
    assert confirmar(engine, previa, ANA)["status"] == "ok"
    assert contar(engine, Chamado, Chamado.categoria == categoria) == 1


def test_previa_avisa_do_chamado_aberto_da_mesma_categoria_e_nao_impede(engine):
    primeiro = confirmar(engine, usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Não liga."}, ANA), ANA)
    segunda = usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Não liga de novo."}, ANA)
    assert primeiro["dados"]["id_chamado"] in segunda["dados"]["atencao"]
    assert confirmar(engine, segunda, ANA)["status"] == "ok"  # só avisa: abrir outro é decisão da pessoa
    sem_duplicado = usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Dúvida de produto", "resumo": "Dúvida."}, ANA)
    assert "atencao" not in sem_duplicado["dados"]


def test_cartao_do_chamado_usa_data_brasileira_e_nomes_em_vez_de_codigos(engine):
    previa = usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Não liga.", "impede_vender": "sim"}, ANA)
    campos = cartao(engine, previa, ANA)
    assert DATA_E_HORA_BR.fullmatch(campos["Prazo"]) and campos["Prioridade"] == "Crítica" and campos["Nível"] == "Atendimento N1"
    assert campos["Canal"] == "WhatsApp"


def _marcar_fraude(engine, chamado):
    confirmar(engine, usar(engine, "atualizar_situacao_chamado", {"id_cliente": "M00001", "id_chamado": chamado, "suspeita_fraude": "sim"}, ANA), ANA)


def test_resposta_ao_lojista_e_recusada_em_chamado_com_suspeita_de_fraude(engine):
    _marcar_fraude(engine, gab.C1_CHAMADO)
    resposta = usar(engine, "adicionar_nota_chamado",
                    {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Olá!", "tipo": "resposta_ao_lojista"}, ANA)
    assert resposta["tipo_erro"] == "parametro_invalido" and "nota interna" in resposta["mensagem"]
    interna = usar(engine, "adicionar_nota_chamado", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Verificar."}, ANA)
    assert interna["status"] == "ok"


def test_previa_da_nota_diz_para_onde_vai_e_a_confirmacao_diz_o_que_aconteceu(engine):
    interna = usar(engine, "adicionar_nota_chamado", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Resumo."}, ANA)
    assert interna["dados"]["destino"] == "Só a equipe vê"
    assert confirmar(engine, interna, ANA)["mensagem"] == "Nota interna gravada no chamado."
    resposta = usar(engine, "adicionar_nota_chamado",
                    {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Já resolvemos.", "tipo": "resposta_ao_lojista"}, ANA)
    assert resposta["dados"]["destino"].startswith("Vai ao lojista por ")
    assert "para sair ao lojista por" in confirmar(engine, resposta, ANA)["mensagem"]
    assert contar(engine, Interacao, Interacao.id_chamado == gab.C1_CHAMADO, Interacao.autor == "agente") == 2


def test_mensagem_de_sucesso_do_encaminhamento_diz_o_que_mudou(engine):
    previa = usar(engine, "atualizar_situacao_chamado", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "encaminhar_para": "N2"}, ANA)
    assert confirmar(engine, previa, ANA)["mensagem"] == f"Chamado {gab.C1_CHAMADO} encaminhado ao atendimento n2."


# --- acordos (U3, U8, dev 2, dev 21) ---------------------------------------------------------------------


def test_parcelas_do_acordo_sao_as_mesmas_que_o_calcular_parcelas_mostra(engine):
    previa = usar(engine, "registrar_acordo", {"id_cliente": "M00003", "numero_parcelas": 4, "faturas": "I000121"}, COBRANCA)
    campos = cartao(engine, previa, COBRANCA)
    calculo = usar(engine, "calcular_parcelas", {"valor_total": "330.67", "numero_parcelas": 4, "valor_principal": "320"}, COBRANCA)
    parcelas = [p["valor"] for p in calculo["dados"]["parcelas"]]
    assert campos["Valor de cada parcela"] == parcelas[0] == "R$ 66,13"
    assert campos["Última parcela (fecha o saldo)"] == parcelas[-1] == "R$ 66,14"
    assert "Parcelas (além da entrada)" in campos


def test_acordo_em_pedaços_soma_para_a_alcada_e_a_previa_avisa_dos_abertos(engine):
    confirmar(engine, usar(engine, "registrar_acordo", {"id_cliente": "M00003", "numero_parcelas": 4, "faturas": "I000121"}, COBRANCA), COBRANCA)
    segunda = usar(engine, "registrar_acordo", {"id_cliente": "M00003", "numero_parcelas": 4}, COBRANCA)
    assert "já tem 1 acordo(s) em aberto" in segunda["dados"]["atencao"]


def test_acordo_que_ninguem_pode_aprovar_avisa_e_o_pedido_se_retira(engine):
    antigo = usar(engine, "retirar_acordo", {"id_acordo": "AC0001"}, COBRANCA)  # liberta as faturas de M00013
    assert confirmar(engine, antigo, COBRANCA)["status"] == "ok"
    previa = usar(engine, "registrar_acordo", {"id_cliente": "M00013", "numero_parcelas": 6}, COORDENADORA)
    assert previa["status"] == "ok" and "ficaria parado" in previa["dados"]["atencao"]
    registrado = confirmar(engine, previa, COORDENADORA)
    assert registrado["dados"]["situacao"] == "pendente_aprovacao"
    retirada = confirmar(engine, usar(engine, "retirar_acordo", {"id_acordo": registrado["dados"]["codigo"]}, COORDENADORA), COORDENADORA)
    assert retirada["status"] == "ok" and "retirado" in retirada["mensagem"]
    with Session(engine) as sessao:
        assert sessao.get(Acordo, registrado["dados"]["codigo"]).situacao == "cancelado"
        assert sessao.get(Fatura, "I000122").id_acordo is None


def test_so_quem_pediu_retira_o_acordo_e_a_resposta_nao_diz_se_existe(engine):
    de_outro = usar(engine, "retirar_acordo", {"id_acordo": "AC0002"}, COORDENADORA)
    inexistente = usar(engine, "retirar_acordo", {"id_acordo": "AC9999"}, COORDENADORA)
    assert (de_outro["tipo_erro"], de_outro["mensagem"]) == (inexistente["tipo_erro"], inexistente["mensagem"])
    assert usar(engine, "retirar_acordo", {"id_acordo": "AC0002"}, ANA)["tipo_erro"] == "ferramenta_inexistente"  # N1 do atendimento


def test_aprovacao_de_acordo_diz_qual_acordo_e_a_recusa_tambem(engine):
    aprovado = confirmar(engine, usar(engine, "aprovar_acordo", {"id_acordo": "AC0002", "decisao": "aprovar"}, COORDENADORA), COORDENADORA)
    recusado = confirmar(engine, usar(engine, "aprovar_acordo", {"id_acordo": "AC0003", "decisao": "recusar"}, COORDENADORA), COORDENADORA)
    assert (aprovado["mensagem"], recusado["mensagem"]) == ("Acordo AC0002 aprovado.", "Acordo AC0003 recusado.")


def test_cartao_da_aprovacao_fala_o_cargo_de_quem_pediu_e_nao_o_id(engine):
    previa = usar(engine, "aprovar_acordo", {"id_acordo": "AC0002", "decisao": "aprovar"}, COORDENADORA)
    campos = cartao(engine, previa, COORDENADORA)
    assert (campos["Pedido por"], campos["Decisão"]) == ("analista de cobrança", "Aprovar")


# --- liquidação recusada pelo banco (U4) -----------------------------------------------------------------


def test_liquidacao_recusada_pelo_banco_e_reprocessada_com_a_conta_ativa(engine):
    lojista, dia = LIQUIDACAO_RECUSADA_PELO_BANCO
    with Session(engine) as sessao:
        id_liquidacao = sessao.scalar(select(Liquidacao.id).where(Liquidacao.id_lojista == lojista, Liquidacao.data == dia))
    previa = usar(engine, "reprocessar_liquidacao", {"id_cliente": lojista, "id_liquidacao": id_liquidacao}, RECEBIVEIS)
    assert previa["status"] == "ok"
    campos = cartao(engine, previa, RECEBIVEIS)
    assert campos["Motivo da falha"] == "O banco do lojista recusou o crédito"
    assert campos["Data original"] == "13/10/2026" and campos["Nova tentativa em"] == "16/10/2026"
    assert confirmar(engine, previa, RECEBIVEIS)["status"] == "ok"
    assert contar(engine, Liquidacao, Liquidacao.id_lojista == lojista, Liquidacao.situacao == "agendada") == 1


# --- falha de gravação (U14) -----------------------------------------------------------------------------


def test_sistema_fora_do_ar_diz_nada_foi_gravado_e_o_que_pode_ter_acontecido_diz_onde_conferir(engine):
    previa = usar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Não liga."}, ANA)
    falhas.ligar("crm")
    fora = confirmar(engine, previa, ANA)
    falhas.desligar_todas()
    assert "Nada foi gravado." in fora["mensagem"] and "Nada foi enviado" not in fora["mensagem"]
    ferramenta = catalogo.carregar()["abrir_chamado"]
    assert "na lista de chamados do lojista" in confirmacoes.mensagem_efeito_incerto(ferramenta)
    assert "na agenda" in confirmacoes.mensagem_efeito_incerto(catalogo.carregar()["criar_evento_agenda"])
