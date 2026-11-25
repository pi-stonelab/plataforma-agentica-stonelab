"""Escritas do mock que não podem duplicar nem furar a alçada: chave de idempotência, commit incerto, soma dos acordos
do lojista, expiração, retirada, antecipação parcial e segregação de quem registra e de quem executa.
"""

from datetime import timedelta

import pytest
from mock import (  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
    escritas,
    falhas,
    regras,
)
from mock.banco import criar_engine
from mock.escritas import EscritaJaAplicada, EscritaRecusada, GravacaoIncerta
from mock.gerar import recriar
from mock.modelos import Acordo, Antecipacao, Chamado, EscritaAplicada, Fatura, Recebivel
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

ANA, BRUNO = "F0001", "F0002"
COBRANCA, COORDENADORA = "F0008", "F0011"
N1_DA_PME = "F0004"


@pytest.fixture
def engine():
    engine = criar_engine("sqlite://")
    recriar(engine)
    yield engine
    falhas.desligar_todas()
    engine.dispose()


def _contar(engine, modelo):
    with Session(engine) as sessao:
        return sessao.scalar(select(func.count()).select_from(modelo))


def _abrir(engine, funcionario=ANA, codigo="M00001"):
    return escritas.abrir_chamado(engine, codigo, "Maquininha", "Maquininha não liga.", "whatsapp", funcionario)


def _recusa(funcao, *argumentos, **opcoes):
    with pytest.raises(EscritaRecusada) as erro:
        funcao(*argumentos, **opcoes)
    return erro.value


# --- idempotência: a mesma confirmação nunca grava duas vezes ------------------------------------------


def test_mesma_chave_nao_grava_duas_vezes_e_devolve_o_codigo_do_que_ja_foi_criado(engine):
    antes = _contar(engine, Chamado)
    with escritas.com_chave("CONF-0001"):
        primeiro = _abrir(engine)
        with pytest.raises(EscritaJaAplicada) as repetida:
            _abrir(engine)
    assert repetida.value.codigo_resultado == primeiro["codigo"]
    assert _contar(engine, Chamado) == antes + 1
    with Session(engine) as sessao:
        marca = sessao.get(EscritaAplicada, "CONF-0001")
    assert (marca.operacao, marca.codigo_resultado) == ("abrir_chamado", primeiro["codigo"])


def test_chaves_diferentes_e_ausencia_de_chave_gravam_cada_uma(engine):
    antes = _contar(engine, Chamado)
    with escritas.com_chave("CONF-0002"):
        _abrir(engine)
    with escritas.com_chave("CONF-0003"):
        _abrir(engine)
    _abrir(engine)
    _abrir(engine)
    assert _contar(engine, Chamado) == antes + 4


def test_chave_ja_usada_nao_deixa_nada_pela_metade(engine):
    with escritas.com_chave("CONF-0004"):
        _abrir(engine)
        interacoes = _contar(engine, Chamado)
        with pytest.raises(EscritaJaAplicada):
            _abrir(engine)
    assert _contar(engine, Chamado) == interacoes


def test_commit_que_pode_ter_chegado_ao_banco_vira_gravacao_incerta_e_a_repeticao_nao_duplica(engine):
    antes = _contar(engine, Chamado)
    quebrar = {"vez": 1}

    def falhar_depois_do_commit(_sessao):
        if quebrar["vez"]:
            quebrar["vez"] = 0
            raise OperationalError("COMMIT", {}, Exception("conexão caiu"))

    event.listen(Session, "after_commit", falhar_depois_do_commit)
    try:
        with escritas.com_chave("CONF-0005"):
            with pytest.raises(GravacaoIncerta):
                _abrir(engine)
            with pytest.raises(EscritaJaAplicada) as repetida:  # a mesma confirmação, depois da falha
                _abrir(engine)
    finally:
        event.remove(Session, "after_commit", falhar_depois_do_commit)
    assert repetida.value.codigo_resultado is not None
    assert _contar(engine, Chamado) == antes + 1


def test_ensaio_com_chave_nao_marca_a_chave(engine):
    with escritas.com_chave("CONF-0006"):
        escritas.ensaiar(escritas.abrir_chamado, engine, "M00001", "Maquininha", "Teste.", "whatsapp", ANA)
        _abrir(engine)  # a prévia não gastou a chave da confirmação
    assert _contar(engine, EscritaAplicada) == 1


# --- soma dos acordos do lojista (alçada) e expiração ---------------------------------------------------


def test_acordo_aberto_soma_para_a_alcada_do_perdao_e_da_dupla_aprovacao():
    sozinho = regras.alcada_do_acordo(150000, 150000, 4, 30000, perdao_encargos_centavos=1000)
    somado = regras.alcada_do_acordo(
        150000, 150000, 4, 30000, perdao_encargos_centavos=1000, original_dos_acordos_abertos_centavos=100000
    )
    assert (sozinho, somado) == ("analista", "coordenador")  # R$ 1.500 + R$ 1.000 passa dos R$ 2.000 do perdão
    assert regras.alcada_do_acordo(600000, 600000, 4, 120000) == "analista"
    assert regras.alcada_do_acordo(600000, 600000, 4, 120000, 0, 0, 0, 600000 + 1) == "dupla_aprovacao"


def test_soma_dos_acordos_abertos_conta_pendentes_e_ativos_da_janela(engine):
    assert escritas.acordos_abertos_do_lojista(engine, "M00013") == {
        "quantidade": 1, "valor_original_centavos": 1220000, "valor_renegociado_centavos": 1266360,
    }
    assert escritas.acordos_abertos_do_lojista(engine, "M00001")["quantidade"] == 0
    with Session(engine) as sessao:  # AC0004 (ativo) foi criado há mais de 30 dias: fora da janela
        assert escritas.acordos_abertos_do_lojista(sessao, "M00014")["quantidade"] == 0


def test_o_acordo_novo_do_mesmo_lojista_conta_na_soma_da_proxima_previa(engine):
    escritas.registrar_acordo(engine, "M00003", ("I000121",), 4, None, False, 0, COBRANCA)
    assert escritas.acordos_abertos_do_lojista(engine, "M00003") == {
        "quantidade": 1, "valor_original_centavos": 32000, "valor_renegociado_centavos": 33067,
    }


def _envelhecer(engine, codigo, dias):
    with engine.begin() as conexao:
        conexao.execute(update(Acordo).where(Acordo.codigo == codigo).values(
            criado_em=regras.HOJE_DO_MOCK - timedelta(days=dias)))


def test_acordo_pendente_vencido_expira_e_solta_as_faturas_para_um_acordo_novo(engine):
    _envelhecer(engine, "AC0002", regras.VALIDADE_DO_ACORDO_PENDENTE_DIAS + 1)
    assert escritas.acordos_abertos_do_lojista(engine, "M00010")["quantidade"] == 0  # vencido não soma
    novo = escritas.registrar_acordo(engine, "M00010", ("I000123",), 4, None, False, 0, COBRANCA)
    with Session(engine) as sessao:
        assert sessao.get(Acordo, "AC0002").situacao == "expirado"
        assert sessao.get(Fatura, "I000123").id_acordo == novo["codigo"]


def test_acordo_vencido_nao_pode_mais_ser_decidido(engine):
    _envelhecer(engine, "AC0002", regras.VALIDADE_DO_ACORDO_PENDENTE_DIAS + 1)
    erro = _recusa(escritas.decidir_acordo, engine, "AC0002", True, COORDENADORA)
    assert erro.tipo_erro == "parametro_invalido" and "expirou" in erro.mensagem


# --- retirar o acordo -----------------------------------------------------------------------------------


def test_quem_pediu_retira_o_acordo_pendente_e_as_faturas_ficam_livres(engine):
    feito = escritas.retirar_acordo(engine, "AC0002", COBRANCA)
    assert (feito["situacao"], feito["faturas"]) == ("cancelado", ["I000123"])
    with Session(engine) as sessao:
        acordo, fatura = sessao.get(Acordo, "AC0002"), sessao.get(Fatura, "I000123")
    assert (acordo.id_decisor, fatura.id_acordo) == (COBRANCA, None)
    assert escritas.acordos_abertos_do_lojista(engine, "M00010")["quantidade"] == 0


def test_outra_pessoa_nao_retira_e_acordo_ja_ativo_nao_se_retira(engine):
    assert _recusa(escritas.retirar_acordo, engine, "AC0002", COORDENADORA).tipo_erro == "nao_encontrado"
    assert _recusa(escritas.retirar_acordo, engine, "AC0004", COBRANCA).tipo_erro == "parametro_invalido"
    assert _recusa(escritas.retirar_acordo, engine, "AC9999", COBRANCA).tipo_erro == "nao_encontrado"


def test_recusa_do_acordo_grava_quem_recusou(engine):
    escritas.decidir_acordo(engine, "AC0003", False, COORDENADORA)
    with Session(engine) as sessao:
        acordo = sessao.get(Acordo, "AC0003")
    assert (acordo.situacao, acordo.id_decisor, acordo.id_aprovador) == ("recusado", COORDENADORA, None)


def test_sem_outro_aprovador_a_previa_pode_avisar(engine):
    assert escritas.aprovadores_possiveis(engine, "coordenador", COBRANCA) == 1
    assert escritas.aprovadores_possiveis(engine, "coordenador", COORDENADORA) == 0
    assert escritas.aprovadores_possiveis(engine, "dupla_aprovacao", COORDENADORA) == 0


# --- antecipação: parcial e registrar diferente de executar ---------------------------------------------


def _pedido(engine, aberto_por=N1_DA_PME):
    return escritas.abrir_chamado(
        engine, "M00004", "Antecipação", "Lojista pediu para antecipar.", "telefone", aberto_por, "N1", nivel_minimo="N2",
    )["codigo"]


def test_antecipacao_parcial_leva_so_as_parcelas_mais_proximas_que_cabem_no_valor(engine):
    chamado = _pedido(engine)
    feito = escritas.executar_antecipacao(engine, "M00004", chamado, BRUNO, valor_maximo_centavos=300000)
    assert 0 < feito["quantidade_de_parcelas"] < 25
    assert 0 < feito["valor_antecipado_bruto_centavos"] <= 300000
    with Session(engine) as sessao:
        marcadas = sessao.scalar(select(func.count()).select_from(Recebivel).where(Recebivel.id_antecipacao == feito["codigo"]))
    assert marcadas == feito["quantidade_de_parcelas"] < 25  # a agenda inteira são 25 parcelas (cenário 4)


def test_antecipacao_com_valor_menor_que_a_primeira_parcela_e_recusada_sem_gravar(engine):
    chamado = _pedido(engine)
    assert _recusa(escritas.executar_antecipacao, engine, "M00004", chamado, BRUNO, valor_maximo_centavos=1).tipo_erro == "parametro_invalido"
    assert _contar(engine, Antecipacao) == 0


def test_quem_registrou_o_pedido_nao_executa_a_antecipacao(engine):
    chamado = _pedido(engine, aberto_por=BRUNO)
    erro = _recusa(escritas.executar_antecipacao, engine, "M00004", chamado, BRUNO)
    assert erro.tipo_erro == "permissao_negada"
    assert _contar(engine, Antecipacao) == 0
