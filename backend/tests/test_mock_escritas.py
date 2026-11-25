"""Escrita nos sistemas simulados (mock/escritas.py): regras do DOC-MOCK, transação e menor privilégio.

Cada teste grava num mundo novo, gerado de verdade em SQLite: o que muda no banco é a prova, não só a resposta.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from mock import (  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
    escritas,
    falhas,
    regras,
)
from mock.banco import criar_engine
from mock.consultas import motivos_de_recusa_da_antecipacao
from mock.escritas import PRIVILEGIOS_DE_ESCRITA, EscritaRecusada
from mock.gerar import CONTA_EM_VERIFICACAO, recriar
from mock.modelos import Acordo, Antecipacao, Chamado, Fatura, Interacao, Liquidacao, Recebivel
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests import gabaritos as gab

ANA, BRUNO, SUPERVISORA, OUVIDORIA = "F0001", "F0002", "F0006", "F0007"
COBRANCA, RECEBIVEIS, COORDENADORA = "F0008", "F0010", "F0011"
DISPUTAS = "F0009"
N1_DA_PME = "F0004"
AGORA = regras.AGORA_DO_MOCK
AMANHA_UTIL = date(2026, 10, 16)


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


def _ler(engine, modelo, chave):
    with Session(engine) as sessao:
        return sessao.get(modelo, chave)


def _recusa(funcao, *argumentos, **opcoes):
    with pytest.raises(EscritaRecusada) as erro:
        funcao(*argumentos, **opcoes)
    return erro.value.tipo_erro, erro.value.mensagem


def _abrir(engine, codigo="M00001", categoria="Maquininha", funcionario=ANA, **opcoes):
    return escritas.abrir_chamado(engine, codigo, categoria, "Maquininha não liga desde cedo.", "whatsapp", funcionario, **opcoes)


# --- abrir chamado (§6.3 e §6.4) ---------------------------------------------------------------


def test_abrir_chamado_tira_fila_prioridade_nivel_e_prazo_das_regras(engine):
    criado = _abrir(engine, impede_vender=True)
    assert criado == {
        "codigo": "CH000071",
        "protocolo": "20261015-000004",  # o dia já tinha 3 chamados
        "categoria": "Maquininha",
        "prioridade": "crítica",  # o lojista não consegue vender
        "fila": "varejo",
        "nivel_atendimento": "N1",
        "situacao": "em_atendimento",  # o N1 que abriu fica com ele
        "id_responsavel": ANA,
        "prazo_em": "2026-10-16T01:00:00",  # 4 horas corridas
        "suspeita_fraude": False,
    }
    gravado = _ler(engine, Chamado, "CH000071")
    assert (gravado.aberto_por, gravado.aberto_em, gravado.resumo) == ("funcionario", AGORA, "Maquininha não liga desde cedo.")


def test_maquininha_que_ainda_vende_e_media_e_o_segundo_chamado_do_dia_segue_a_sequencia(engine):
    primeiro, segundo = _abrir(engine), _abrir(engine)
    assert primeiro["prioridade"] == "média" and primeiro["prazo_em"] == "2026-10-20T21:00:00"  # 3 dias úteis
    assert (segundo["codigo"], segundo["protocolo"]) == ("CH000072", "20261015-000005")


def test_categoria_do_n2_ou_valor_acima_de_mil_reais_vai_para_a_fila_do_n2_sem_responsavel(engine):
    cadastral = _abrir(engine, categoria="Alteração cadastral")
    recebimento = _abrir(engine, categoria="Recebimento", valor_envolvido_centavos=gab.C1_LIQUIDACAO_CENTAVOS)
    for chamado in (cadastral, recebimento):
        assert (chamado["nivel_atendimento"], chamado["situacao"], chamado["id_responsavel"]) == ("N2", "novo", None)
    assert _abrir(engine, categoria="Recebimento", valor_envolvido_centavos=100000)["nivel_atendimento"] == "N1"
    assert _abrir(engine, categoria="Alteração cadastral", funcionario=BRUNO)["id_responsavel"] == BRUNO


@pytest.mark.parametrize(
    "opcoes, tipo",
    [
        ({"codigo": "M09999"}, "nao_encontrado"),
        ({"categoria": "Cancelamento"}, "parametro_invalido"),
        ({"funcionario": "F0099"}, "permissao_negada"),
    ],
)
def test_abrir_chamado_recusa_sem_gravar(engine, opcoes, tipo):
    antes = _contar(engine, Chamado)
    assert _recusa(_abrir, engine, **opcoes)[0] == tipo
    assert _contar(engine, Chamado) == antes


def test_canal_e_resumo_invalidos_sao_recusados(engine):
    assert _recusa(escritas.abrir_chamado, engine, "M00001", "Maquininha", "x", "pombo", ANA)[0] == "parametro_invalido"
    assert _recusa(escritas.abrir_chamado, engine, "M00001", "Maquininha", "  ", "chat", ANA)[0] == "parametro_invalido"


def test_funcionario_afastado_nao_grava(engine):
    with engine.begin() as conexao:
        conexao.execute(text("UPDATE funcionarios SET situacao = 'afastado' WHERE id = :id"), {"id": ANA})
    assert _recusa(_abrir, engine)[0] == "permissao_negada"


@pytest.mark.parametrize("sistema", ["crm", "cadastro"])
def test_sistema_fora_do_ar_antes_de_gravar_nao_grava_nada(engine, sistema):
    falhas.ligar(sistema)
    antes = _contar(engine, Chamado)
    with pytest.raises(falhas.SistemaIndisponivel):
        _abrir(engine)
    assert _contar(engine, Chamado) == antes


def test_erro_no_meio_da_transacao_desfaz_tudo(engine, monkeypatch):
    original = escritas._descrever_chamado

    def quebra_depois_de_gravar(chamado):
        original(chamado)
        raise RuntimeError("queda no meio")

    monkeypatch.setattr(escritas, "_descrever_chamado", quebra_depois_de_gravar)
    antes = _contar(engine, Chamado)
    with pytest.raises(RuntimeError):
        _abrir(engine)
    assert _contar(engine, Chamado) == antes


# --- notas e respostas ------------------------------------------------------------------------


def test_nota_do_agente_fica_no_canal_interno_com_quem_confirmou(engine):
    feita = escritas.adicionar_nota(
        engine, "M00001", gab.C1_CHAMADO, "Liguei e expliquei.", "nota_interna", ANA, escrita_pelo_agente=True
    )
    assert feita == {
        "id_chamado": gab.C1_CHAMADO, "tipo": "nota_interna", "canal": "interno", "data_hora": AGORA.isoformat()
    }
    with Session(engine) as sessao:
        ultima = sessao.scalars(select(Interacao).order_by(Interacao.id.desc())).first()
    assert (ultima.autor, ultima.canal, ultima.id_funcionario, ultima.texto) == (
        "agente", "interno", ANA, "Liguei e expliquei."  # §6.8: texto do agente nunca em nome do funcionário
    )


def test_o_banco_recusa_texto_do_agente_sem_quem_confirmou(engine):
    with pytest.raises(IntegrityError), Session(engine) as sessao, sessao.begin():
        sessao.add(Interacao(id_chamado=gab.C1_CHAMADO, autor="agente", canal="whatsapp", data_hora=AGORA, texto="x"))


def test_resposta_ao_lojista_vai_pelo_canal_em_que_ele_falou(engine):
    with Session(engine) as sessao:
        canal = sessao.scalar(
            select(Interacao.canal).where(Interacao.id_chamado == gab.C1_CHAMADO, Interacao.autor == "lojista")
            .order_by(Interacao.data_hora.desc())
        )
    feita = escritas.adicionar_nota(engine, "M00001", gab.C1_CHAMADO, "Estamos vendo.", "resposta_ao_lojista", ANA, escrita_pelo_agente=True)
    assert feita["canal"] == (canal or "whatsapp")


def test_nota_recusa_chamado_fechado_de_outro_lojista_e_tipo_desconhecido(engine):
    with Session(engine) as sessao:
        fechado = sessao.scalars(select(Chamado).where(Chamado.situacao == "fechado")).first()
    assert _recusa(escritas.adicionar_nota, engine, fechado.id_lojista, fechado.codigo, "x", "nota_interna", ANA, escrita_pelo_agente=True)[0] == (
        "parametro_invalido"
    )
    assert _recusa(escritas.adicionar_nota, engine, "M00002", gab.C1_CHAMADO, "x", "nota_interna", ANA, escrita_pelo_agente=True)[0] == (
        "nao_encontrado"
    )
    assert _recusa(escritas.adicionar_nota, engine, "M00001", gab.C1_CHAMADO, "x", "sms", ANA, escrita_pelo_agente=True)[0] == "parametro_invalido"


# --- situação, encaminhamento e suspeita (§6.5 e §6.6) ----------------------------------------


def test_pegar_chamado_novo_poe_quem_pegou_e_resolver_marca_a_hora(engine):
    pego = escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, nova_situacao="em_atendimento")
    assert (pego["situacao"], pego["id_responsavel"]) == ("em_atendimento", ANA)
    escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, nova_situacao="resolvido")
    assert _ler(engine, Chamado, gab.C1_CHAMADO).resolvido_em == AGORA
    reaberto = escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, nova_situacao="em_atendimento")
    assert reaberto["situacao"] == "em_atendimento" and _ler(engine, Chamado, gab.C1_CHAMADO).resolvido_em is None


@pytest.mark.parametrize("nova", ["resolvido", "fechado", "aguardando_lojista", "novo"])
def test_passagens_fora_do_ciclo_sao_recusadas(engine, nova):
    assert _ler(engine, Chamado, gab.C1_CHAMADO).situacao == "novo"
    tipo, _ = _recusa(escritas.atualizar_chamado, engine, "M00001", gab.C1_CHAMADO, ANA, nova_situacao=nova)
    assert tipo == "parametro_invalido" and _ler(engine, Chamado, gab.C1_CHAMADO).situacao == "novo"


def test_n1_nao_mexe_na_situacao_de_chamado_do_n2_e_o_n2_mexe(engine):
    assert _recusa(
        escritas.atualizar_chamado, engine, "M00006", "CH000063", ANA, nova_situacao="em_atendimento"
    )[0] == "permissao_negada"
    feito = escritas.atualizar_chamado(engine, "M00006", "CH000063", BRUNO, nova_situacao="em_atendimento")
    assert feito["id_responsavel"] == BRUNO


def test_so_a_ouvidoria_muda_o_caso_da_ouvidoria_cenario_9(engine):
    for funcionario in (ANA, SUPERVISORA):
        tipo, mensagem = _recusa(
            escritas.atualizar_chamado, engine, "M00007", "CH000066", funcionario, nova_situacao="resolvido"
        )
        assert tipo == "permissao_negada" and "ouvidoria" in mensagem
    assert escritas.atualizar_chamado(
        engine, "M00007", "CH000066", OUVIDORIA, nova_situacao="resolvido"
    )["situacao"] == "resolvido"


def test_suspeita_de_fraude_marca_e_sobe_para_o_n2_cenario_6(engine):
    _abrir(engine, codigo="M00001", categoria="Recebimento")  # um chamado do N1, para ver a subida
    feito = escritas.atualizar_chamado(engine, "M00001", "CH000071", ANA, suspeita_fraude=True)
    assert (feito["suspeita_fraude"], feito["nivel_atendimento"], feito["situacao"], feito["id_responsavel"]) == (
        True, "N2", "novo", None
    )


def test_encaminhar_so_para_cima_e_nunca_chamado_resolvido(engine):
    escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, encaminhar_para="N2")
    assert _ler(engine, Chamado, gab.C1_CHAMADO).nivel_atendimento == "N2"
    assert _recusa(
        escritas.atualizar_chamado, engine, "M00001", gab.C1_CHAMADO, BRUNO, encaminhar_para="N1"
    )[0] == "parametro_invalido"
    escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, BRUNO, nova_situacao="em_atendimento")
    escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, BRUNO, nova_situacao="resolvido")
    assert _recusa(
        escritas.atualizar_chamado, engine, "M00001", gab.C1_CHAMADO, BRUNO, encaminhar_para="supervisor"
    )[0] == "parametro_invalido"


def test_cargo_que_nao_atende_e_pedido_sem_mudanca_sao_recusados(engine):
    assert _recusa(
        escritas.atualizar_chamado, engine, "M00001", gab.C1_CHAMADO, COBRANCA, nova_situacao="em_atendimento"
    )[0] == "permissao_negada"
    assert _recusa(escritas.atualizar_chamado, engine, "M00001", gab.C1_CHAMADO, ANA)[0] == (
        "parametro_invalido"
    )


# --- liquidação (§7.3, cenário 1 e onboarding 6) ----------------------------------------------


def _id_da_liquidacao_do_cenario_1(engine):
    with Session(engine) as sessao:
        return sessao.scalar(select(Liquidacao.id).where(
            Liquidacao.id_lojista == gab.C1_LOJISTA, Liquidacao.situacao == "falhou"))


def test_reprocessar_com_a_conta_invalida_e_recusado_cenario_1(engine):
    id_liquidacao = _id_da_liquidacao_do_cenario_1(engine)
    tipo, mensagem = _recusa(escritas.reprocessar_liquidacao, engine, gab.C1_LOJISTA, id_liquidacao, RECEBIVEIS)
    assert tipo == "parametro_invalido" and "N2" in mensagem
    assert _ler(engine, Liquidacao, id_liquidacao).situacao == "falhou"


def test_reprocessar_depois_que_a_conta_volta_agenda_nova_tentativa_ligada_a_original(engine):
    id_liquidacao = _id_da_liquidacao_do_cenario_1(engine)
    with engine.begin() as conexao:
        conexao.execute(text("UPDATE contas_recebimento SET situacao = 'ativa' WHERE id_lojista = 'M00001'"))
    feito = escritas.reprocessar_liquidacao(engine, gab.C1_LOJISTA, id_liquidacao, RECEBIVEIS)
    nova = _ler(engine, Liquidacao, feito["id_nova_tentativa"])
    original = _ler(engine, Liquidacao, id_liquidacao)
    assert (original.situacao, original.motivo_falha) == ("reprocessada", gab.C1_MOTIVO_DA_FALHA)
    assert (nova.situacao, nova.data, nova.valor_total_centavos, nova.id_liquidacao_original, nova.motivo_falha) == (
        "agendada", AMANHA_UTIL, gab.C1_LIQUIDACAO_CENTAVOS, id_liquidacao, None
    )
    assert _recusa(escritas.reprocessar_liquidacao, engine, gab.C1_LOJISTA, id_liquidacao, RECEBIVEIS)[0] == (
        "parametro_invalido"  # já reprocessada: uma vez só
    )


def test_reprocessar_liquidacao_paga_ou_de_outro_lojista_e_recusado(engine):
    with Session(engine) as sessao:
        paga = sessao.scalars(select(Liquidacao).where(Liquidacao.situacao == "paga")).first()
    assert _recusa(escritas.reprocessar_liquidacao, engine, paga.id_lojista, paga.id, RECEBIVEIS)[0] == "parametro_invalido"
    assert _recusa(escritas.reprocessar_liquidacao, engine, "M00002", _id_da_liquidacao_do_cenario_1(engine), RECEBIVEIS)[
        0
    ] == "nao_encontrado"


# --- acordos (§7.5 e §7.9, cenário 3 e onboarding 8) -----------------------------------------


def test_numeros_do_acordo_seguem_os_encargos_do_cenario_3():
    so_o_saldo = [{"valor_centavos": 32000, "vencimento": date(2026, 9, 5)}]  # 40 dias antes de 15/10
    numeros = escritas.montar_acordo(so_o_saldo, 4, None, False, 0)
    assert numeros["valor_renegociado_centavos"] == 33067  # R$ 330,67, o gabarito do cenário 3
    assert numeros["entrada_centavos"] == 6614  # 20% arredondado para cima
    # 26.453 de saldo em 4 parcelas: 3 de R$ 66,13 e a última absorve a diferença (R$ 66,14), como na venda (§7.1)
    assert (numeros["alcada"], numeros["valor_da_parcela_centavos"], numeros["valor_da_ultima_parcela_centavos"]) == (
        "analista", 6613, 6614)


def test_acordo_de_4_parcelas_na_alcada_da_analista_nasce_ativo_cenario_3(engine):
    feito = escritas.registrar_acordo(engine, "M00003", (), 4, None, False, 0, COBRANCA)
    acordo = _ler(engine, Acordo, feito["codigo"])
    assert (feito["codigo"], acordo.situacao, acordo.alcada, acordo.id_aprovador) == ("AC0005", "ativo", "analista", COBRANCA)
    with Session(engine) as sessao:
        faturas = sessao.scalars(select(Fatura).where(Fatura.id_acordo == "AC0005")).all()
    assert sorted(f.codigo for f in faturas) == ["I000017", "I000018", "I000121"]
    assert {f.situacao for f in faturas} == {"em_acordo"}
    assert motivos_de_recusa_da_antecipacao(engine, "M00003") == []  # em acordo, sai da régua (§7.5)


def test_acordo_de_10_parcelas_sobe_ao_coordenador_e_as_faturas_continuam_vencidas(engine):
    feito = escritas.registrar_acordo(engine, "M00003", ("I000121",), 10, None, False, 0, COBRANCA)
    assert (feito["situacao"], feito["alcada"]) == ("pendente_aprovacao", "coordenador")
    fatura = _ler(engine, Fatura, "I000121")
    assert (fatura.situacao, fatura.id_acordo) == ("vencida", feito["codigo"])
    assert "fatura_vencida_ha_mais_de_15_dias" in motivos_de_recusa_da_antecipacao(engine, "M00003")


@pytest.mark.parametrize(
    "parcelas, desconto, mensagem",
    [(13, 0, "parcelas"), (4, Decimal("10.01"), "10%")],
)
def test_acordo_fora_das_regras_e_recusado_sem_gravar(engine, parcelas, desconto, mensagem):
    antes = _contar(engine, Acordo)
    tipo, texto = _recusa(escritas.registrar_acordo, engine, "M00003", ("I000121",), parcelas, None, False, desconto, COBRANCA)
    assert tipo == "parametro_invalido" and mensagem in texto
    assert _contar(engine, Acordo) == antes and _ler(engine, Fatura, "I000121").id_acordo is None


def test_acordo_so_com_fatura_vencida_do_proprio_lojista_e_fora_de_acordo(engine):
    assert _recusa(escritas.registrar_acordo, engine, "M00003", ("I000122",), 4, None, False, 0, COBRANCA)[0] == (
        "parametro_invalido"  # é da M00013 e já está no AC0001
    )
    assert _recusa(escritas.registrar_acordo, engine, "M00002", (), 4, None, False, 0, COBRANCA)[0] == "nao_encontrado"


def test_acima_de_dez_mil_reais_e_dupla_aprovacao():
    grande = [{"valor_centavos": 1100000, "vencimento": date(2026, 10, 1)}]
    assert escritas.montar_acordo(grande, 4, None, False, 0)["alcada"] == "dupla_aprovacao"


def test_quem_pediu_nao_aprova_e_o_coordenador_aprova_onboarding_8(engine):
    assert _recusa(escritas.decidir_acordo, engine, "AC0001", True, COBRANCA)[0] == "permissao_negada"
    feito = escritas.decidir_acordo(engine, "AC0001", True, COORDENADORA)
    assert (feito["situacao"], _ler(engine, Acordo, "AC0001").id_aprovador) == ("ativo", COORDENADORA)
    assert _ler(engine, Fatura, "I000122").situacao == "em_acordo"
    assert _recusa(escritas.decidir_acordo, engine, "AC0001", True, COORDENADORA)[0] == "parametro_invalido"


def test_coordenador_fecha_sozinho_o_que_cabe_na_alcada_dele(engine):
    feito = escritas.registrar_acordo(engine, "M00003", ("I000121",), 10, None, False, 0, COORDENADORA)
    assert (feito["situacao"], feito["alcada"]) == ("ativo", "coordenador")
    assert _ler(engine, Acordo, feito["codigo"]).id_aprovador == COORDENADORA


def _dupla_aprovacao_pedida_pela_coordenadora(engine):
    escritas.decidir_acordo(engine, "AC0001", False, COORDENADORA)  # solta a fatura de R$ 12.200 da M00013
    feito = escritas.registrar_acordo(engine, "M00013", ("I000122",), 10, None, False, 0, COORDENADORA)
    assert (feito["situacao"], feito["alcada"]) == ("pendente_aprovacao", "dupla_aprovacao")
    return feito["codigo"]


def test_dupla_aprovacao_pedida_pela_coordenadora_espera_outra_pessoa(engine):
    codigo = _dupla_aprovacao_pedida_pela_coordenadora(engine)
    assert _recusa(escritas.decidir_acordo, engine, codigo, True, COORDENADORA)[0] == "permissao_negada"
    assert _ler(engine, Acordo, codigo).situacao == "pendente_aprovacao"


@pytest.mark.parametrize("quem", [COBRANCA, ANA])
def test_quem_nao_tem_a_alcada_nao_decide(engine, quem):
    codigo = _dupla_aprovacao_pedida_pela_coordenadora(engine)
    tipo, texto = _recusa(escritas.decidir_acordo, engine, codigo, True, quem)
    assert (tipo, texto) == ("permissao_negada", "Este acordo passa da sua alçada.")


def test_quem_nao_negocia_acordo_nao_registra(engine):
    tipo, texto = _recusa(escritas.registrar_acordo, engine, "M00003", (), 4, None, False, 0, ANA)
    assert (tipo, texto) == ("permissao_negada", "Seu cargo não negocia acordos.")
    assert _contar(engine, Acordo) == 4


def test_percentuais_arredondam_a_favor_da_regra():
    so_o_saldo = [{"valor_centavos": 32000, "vencimento": date(2026, 9, 5)}]
    no_limite = escritas.montar_acordo(so_o_saldo, 4, 20, False, 10)
    assert no_limite["desconto_principal_centavos"] == 3200 and no_limite["alcada"] == "coordenador"
    assert no_limite["entrada_centavos"] * 100 >= no_limite["valor_renegociado_centavos"] * 20
    assert escritas.montar_acordo(so_o_saldo, 4, Decimal("19.99"), False, 0)["alcada"] == "coordenador"
    with pytest.raises(EscritaRecusada):
        escritas.montar_acordo(so_o_saldo, 4, 100, False, 0)


def test_recusar_solta_as_faturas_do_acordo(engine):
    feito = escritas.decidir_acordo(engine, "AC0003", False, COORDENADORA)
    assert feito["situacao"] == "recusado"
    fatura = _ler(engine, Fatura, "I000124")
    assert (fatura.situacao, fatura.id_acordo) == ("vencida", None)
    assert _recusa(escritas.decidir_acordo, engine, "AC9999", True, COORDENADORA)[0] == "nao_encontrado"


# --- antecipação (§7.4, cenário 4) ------------------------------------------------------------


def _pedido_de_antecipacao(engine, codigo="M00004", funcionario=N1_DA_PME):
    return escritas.abrir_chamado(
        engine, codigo, "Antecipação", "Lojista pediu para antecipar a agenda.", "telefone", funcionario, "N1",
        nivel_minimo="N2",
    )["codigo"]


def test_executar_antecipacao_bate_com_a_simulacao_do_cenario_4(engine):
    chamado = _pedido_de_antecipacao(engine)
    assert _ler(engine, Chamado, chamado).nivel_atendimento == "N2"
    feito = escritas.executar_antecipacao(engine, "M00004", chamado, BRUNO)
    assert feito == {
        "codigo": "AN0001",
        "id_chamado": chamado,
        "quantidade_de_parcelas": gab.C4_SIMULACAO["quantidade_de_parcelas"],
        "valor_antecipado_bruto_centavos": 1178246,
        "desconto_antecipacao_centavos": 115348,
        "valor_antecipado_liquido_centavos": 1062898,
        "taxa_antecipacao_pontos_base": 299,
        "data_credito": gab.C4_SIMULACAO["data_credito"],
    }
    with Session(engine) as sessao:
        marcadas = sessao.scalar(select(func.count()).select_from(Recebivel).where(Recebivel.id_antecipacao == "AN0001"))
        nota = sessao.scalars(select(Interacao).where(Interacao.id_chamado == chamado)).one()
    assert marcadas == 25 and (nota.canal, nota.id_funcionario) == ("interno", BRUNO)
    tipo, mensagem = _recusa(escritas.executar_antecipacao, engine, "M00004", chamado, BRUNO)
    assert tipo == "parametro_invalido" and "parcelas" in mensagem  # o que dava já foi antecipado


@pytest.mark.parametrize(
    "codigo, motivo",
    [(gab.C4_LOJISTA_RECUSADO, "fatura vencida"), (CONTA_EM_VERIFICACAO, "em verificação")],
)
def test_execucao_confere_de_novo_as_recusas_do_7_4(engine, codigo, motivo):
    chamado = _pedido_de_antecipacao(engine, codigo, ANA)
    tipo, mensagem = _recusa(escritas.executar_antecipacao, engine, codigo, chamado, BRUNO)
    assert tipo == "parametro_invalido" and motivo in mensagem
    assert _contar(engine, Antecipacao) == 0


def test_antecipacao_exige_chamado_de_antecipacao_do_lojista(engine):
    assert _recusa(escritas.executar_antecipacao, engine, "M00004", gab.C1_CHAMADO, BRUNO)[0] == "nao_encontrado"
    outro = _abrir(engine, codigo="M00004", categoria="Dúvida de produto", funcionario=N1_DA_PME)["codigo"]
    assert _recusa(escritas.executar_antecipacao, engine, "M00004", outro, BRUNO)[0] == "parametro_invalido"


# --- menor privilégio: cada operação só mexe no que o papel de escrita pode -------------------


def _operacoes(engine):
    with engine.begin() as conexao:
        conexao.execute(text("UPDATE contas_recebimento SET situacao = 'ativa' WHERE id_lojista = 'M00001'"))
    yield lambda: _abrir(engine)
    yield lambda: escritas.adicionar_nota(engine, "M00001", gab.C1_CHAMADO, "Ok.", "nota_interna", ANA, escrita_pelo_agente=True)
    yield lambda: escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, nova_situacao="em_atendimento")
    yield lambda: escritas.atualizar_chamado(engine, "M00001", gab.C1_CHAMADO, ANA, suspeita_fraude=True)
    yield lambda: escritas.reprocessar_liquidacao(engine, "M00001", _id_da_liquidacao_do_cenario_1(engine), RECEBIVEIS)
    yield lambda: escritas.registrar_acordo(engine, "M00003", (), 4, None, False, 0, COBRANCA)
    yield lambda: escritas.decidir_acordo(engine, "AC0001", True, COORDENADORA)
    yield lambda: escritas.decidir_acordo(engine, "AC0003", False, COORDENADORA)
    yield lambda: escritas.retirar_acordo(engine, "AC0002", COBRANCA)
    yield lambda: escritas.registrar_defesa_chargeback(engine, "M00002", "CB00001", ("nota_fiscal",), DISPUTAS)
    chamado = _pedido_de_antecipacao(engine)
    yield lambda: escritas.executar_antecipacao(engine, "M00004", chamado, BRUNO)


def test_cada_operacao_so_insere_e_altera_o_que_o_papel_de_escrita_pode(engine):
    tocados = []

    @event.listens_for(Session, "before_flush")
    def anotar(sessao, _contexto, _instancias):
        for objeto in sessao.new:
            tocados.append((objeto.__tablename__, "insert", None))
        for objeto in sessao.dirty:
            estado = inspect(objeto)
            for atributo in estado.mapper.column_attrs:
                if estado.attrs[atributo.key].history.has_changes():
                    tocados.append((objeto.__tablename__, "update", atributo.key))

    try:
        for numero, operacao in enumerate(_operacoes(engine)):
            with escritas.com_chave(f"CONF-TESTE{numero:04d}"):  # com chave, a escrita grava a trava de idempotência
                operacao()
    finally:
        event.remove(Session, "before_flush", anotar)
    assert tocados
    for tabela, acao, coluna in tocados:
        privilegio = PRIVILEGIOS_DE_ESCRITA.get(tabela)
        assert privilegio is not None, tabela
        assert privilegio["insert"] if acao == "insert" else coluna in privilegio["update"], (tabela, acao, coluna)
    assert {tabela for tabela, _, _ in tocados} == set(PRIVILEGIOS_DE_ESCRITA)  # a lista não sobra


def test_toda_escrita_usa_o_relogio_parado_do_mock(engine):
    _abrir(engine)
    escritas.adicionar_nota(engine, "M00001", gab.C1_CHAMADO, "Ok.", "nota_interna", ANA, escrita_pelo_agente=True)
    with engine.connect() as conexao:
        momentos = conexao.execute(text(
            "SELECT aberto_em FROM chamados WHERE codigo = 'CH000071' "
            "UNION ALL SELECT data_hora FROM interacoes WHERE id_funcionario IS NOT NULL"
        )).scalars().all()
    assert {datetime.fromisoformat(str(m)) for m in momentos} == {AGORA}
