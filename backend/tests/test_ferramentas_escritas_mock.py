"""Regressão das 8 escritas com confirmação sobre o mock (bloco D), gravando de verdade no mundo do mock.

Cada ferramenta: a prévia não muda o banco e recusa o que a confirmação recusaria; a confirmação grava uma vez
só, com quem confirmou; cancelar e expirar não gravam; outra pessoa não confirma; a carteira vale; sistema fora do
ar não grava; texto livre chega mascarado ao banco; o registro não leva conteúdo.
"""

import json
from datetime import timedelta

import pytest
from ferramentas import catalogo, confirmacoes, governanca
from mock import falhas  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.modelos import (
    Acordo,
    Antecipacao,
    Chamado,
    ContaRecebimento,
    Interacao,
    Liquidacao,
    Recebivel,
)
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import gabaritos as gab
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

ESCRITAS = tuple(governanca.ESCRITA_COM_CONFIRMACAO)
CPF_NO_TEXTO = "123.456.789-09"  # o CPF de teste permitido (gab.CPF_VALIDO_PERMITIDO)
TABELAS = (Chamado, Interacao, Liquidacao, Acordo, Antecipacao)

ANA = gab.ANA  # atendente N1, varejo
N1_PME = gab.ATENDENTE_PME
N2_VAREJO = "F0002"
N2_PME = "F0005"
COBRANCA = gab.COBRANCA
RECEBIVEIS = "F0010"
COORDENADORA = gab.COORDENADOR_FINANCEIRO
OUVIDORIA = gab.OUVIDORIA
SUPERVISORA = gab.SUPERVISOR_ATENDIMENTO


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def pessoa(engine, id_funcionario):
    return usuario_do_diretorio(engine, id_funcionario)


def preparar(engine, nome, argumentos, id_funcionario):
    return catalogo.executar(nome, argumentos, pessoa(engine, id_funcionario), ESCRITAS)


def preparar_e_confirmar(engine, nome, argumentos, id_funcionario):
    previa = preparar(engine, nome, argumentos, id_funcionario)
    assert previa["status"] == "ok", previa
    return confirmacoes.confirmar(previa["dados"]["confirmacao_id"], pessoa(engine, id_funcionario))


def contagem(engine):
    with Session(engine) as sessao:
        return {tabela.__tablename__: sessao.scalar(select(func.count()).select_from(tabela)) for tabela in TABELAS}


def ler(engine, modelo, **filtro):
    with Session(engine) as sessao:
        return sessao.scalars(select(modelo).filter_by(**filtro)).all()


def ativar_conta(engine, codigo):
    with Session(engine) as sessao, sessao.begin():
        sessao.execute(update(ContaRecebimento).where(ContaRecebimento.id_lojista == codigo).values(situacao="ativa"))


def id_da_liquidacao_do_cenario_1(engine):
    (liquidacao,) = ler(engine, Liquidacao, id_lojista=gab.C1_LOJISTA, situacao="falhou")
    return liquidacao.id


# Uma prévia válida de cada escrita, com quem pode fazê-la.
def casos_validos(engine):
    return {
        "abrir_chamado": (
            {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "Maquininha não liga.", "impede_vender": "sim"},
            ANA,
        ),
        "adicionar_nota_chamado": ({"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "texto": "Resumo."}, ANA),
        "atualizar_situacao_chamado": (
            {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO, "nova_situacao": "em_atendimento"},
            ANA,
        ),
        "registrar_pedido_antecipacao": ({"id_cliente": gab.C4_LOJISTA, "resumo": "Quer antecipar tudo."}, N1_PME),
        "registrar_acordo": ({"id_cliente": gab.C3_LOJISTA, "numero_parcelas": gab.C3_PARCELAS}, COBRANCA),
        "aprovar_acordo": ({"id_acordo": "AC0002", "decisao": "aprovar"}, COORDENADORA),
    }


# --- o ciclo das duas fases, para todas -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome",
    ["abrir_chamado", "adicionar_nota_chamado", "atualizar_situacao_chamado", "registrar_pedido_antecipacao",
     "registrar_acordo", "aprovar_acordo"],
)
def test_previa_nao_grava_e_a_confirmacao_grava_uma_vez_so(engine, nome):
    argumentos, quem = casos_validos(engine)[nome]
    antes = contagem(engine)
    previa = preparar(engine, nome, argumentos, quem)
    assert previa["status"] == "ok" and previa["dados"]["situacao"] == "aguardando_confirmacao"
    assert contagem(engine) == antes
    confirmacao_id = previa["dados"]["confirmacao_id"]
    feito = confirmacoes.confirmar(confirmacao_id, pessoa(engine, quem))
    assert feito["status"] == "ok" and feito["mensagem"] == catalogo.carregar()[nome].mensagem_feito
    depois = contagem(engine)
    assert confirmacoes.confirmar(confirmacao_id, pessoa(engine, quem))["tipo_erro"] == "nao_encontrado"
    assert confirmacoes.situacao_da_decisao(confirmacao_id, pessoa(engine, quem)) == "aprovada"
    assert contagem(engine) == depois  # a segunda confirmação não grava de novo


@pytest.mark.parametrize("nome", ["abrir_chamado", "registrar_acordo"])
def test_cancelar_outra_pessoa_e_expirar_nao_gravam(engine, nome, monkeypatch):
    argumentos, quem = casos_validos(engine)[nome]
    antes = contagem(engine)
    descartada = preparar(engine, nome, argumentos, quem)["dados"]["confirmacao_id"]
    assert confirmacoes.cancelar(descartada, pessoa(engine, quem))["status"] == "ok"
    de_outro = preparar(engine, nome, argumentos, quem)["dados"]["confirmacao_id"]
    outro = pessoa(engine, COORDENADORA if quem != COORDENADORA else ANA)
    assert confirmacoes.confirmar(de_outro, outro)["tipo_erro"] == "nao_encontrado"
    vencida = preparar(engine, nome, argumentos, quem)["dados"]["confirmacao_id"]
    depois_da_validade = confirmacoes.agora() + confirmacoes.VALIDADE + timedelta(seconds=1)
    monkeypatch.setattr(confirmacoes, "agora", lambda: depois_da_validade)
    assert confirmacoes.confirmar(vencida, pessoa(engine, quem))["tipo_erro"] == "nao_encontrado"
    assert contagem(engine) == antes


def test_toda_escrita_tem_titulo_frase_de_sucesso_e_cartao_para_a_interface(engine):
    for nome, (argumentos, quem) in casos_validos(engine).items():
        ferramenta = catalogo.carregar()[nome]
        assert ferramenta.titulo and ferramenta.mensagem_feito != "Enviado.", nome
        previa = preparar(engine, nome, argumentos, quem)
        cartao = confirmacoes.confirmacao_para_interface(previa["dados"]["confirmacao_id"], pessoa(engine, quem))
        assert cartao["titulo"] == ferramenta.titulo and cartao["situacao"] == "pendente", nome
        assert [campo["rotulo"] for campo in cartao["campos"]], nome


def test_sistema_fora_do_ar_nao_grava_nem_na_previa_nem_na_confirmacao(engine):
    argumentos, quem = casos_validos(engine)["abrir_chamado"]
    antes = contagem(engine)
    previa = preparar(engine, "abrir_chamado", argumentos, quem)
    falhas.ligar("crm")
    assert confirmacoes.confirmar(previa["dados"]["confirmacao_id"], pessoa(engine, quem))["tipo_erro"] == (
        "integracao_indisponivel"
    )
    assert preparar(engine, "abrir_chamado", argumentos, quem)["tipo_erro"] == "integracao_indisponivel"
    falhas.desligar_todas()
    assert contagem(engine) == antes


def test_lojista_fora_da_carteira_e_recusado_na_previa(engine):
    resposta = preparar(engine, "abrir_chamado", {"id_cliente": gab.C4_LOJISTA, "categoria": "Maquininha",
                                                   "resumo": "x"}, ANA)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == (gab.TIPO_ERRO_FORA_DO_ESCOPO, gab.MENSAGEM_FORA_DA_CARTEIRA)


def test_texto_livre_chega_mascarado_ao_banco_e_o_registro_nao_leva_conteudo(engine):
    resumo = f"Lojista mandou o CPF {CPF_NO_TEXTO} por engano."
    feito = preparar_e_confirmar(
        engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Recebimento", "resumo": resumo}, ANA
    )
    (chamado,) = ler(engine, Chamado, codigo=feito["dados"]["id_chamado"])
    assert CPF_NO_TEXTO not in chamado.resumo and "***" in chamado.resumo
    texto_do_registro = json.dumps(governanca.REGISTROS, ensure_ascii=False)
    assert "Lojista mandou" not in texto_do_registro and CPF_NO_TEXTO not in texto_do_registro


# --- chamados (DOC-MOCK §6.3 a §6.6) -----------------------------------------------------------------------------


def test_abrir_chamado_prioridade_nivel_e_prazo_vem_das_regras(engine):
    previa = preparar(engine, "abrir_chamado", casos_validos(engine)["abrir_chamado"][0], ANA)["dados"]
    assert (previa["prioridade"], previa["nivel_atendimento"]) == ("crítica", "N1")
    alto = preparar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Recebimento", "resumo": "x",
                                               "valor_envolvido": 1500}, ANA)["dados"]
    assert alto["nivel_atendimento"] == "N2"
    feito = confirmacoes.confirmar(alto["confirmacao_id"], pessoa(engine, ANA))["dados"]
    assert (feito["nivel_atendimento"], feito["situacao"]) == ("N2", "novo")  # vai para a fila do N2, sem dono


def test_prazo_do_chamado_usa_a_fila_da_carteira(engine):
    previa = preparar(engine, "abrir_chamado", {"id_cliente": "M00001", "categoria": "Recebimento", "resumo": "x"}, ANA)
    feito = confirmacoes.confirmar(previa["dados"]["confirmacao_id"], pessoa(engine, ANA))
    (chamado,) = ler(engine, Chamado, codigo=feito["dados"]["id_chamado"])
    assert chamado.fila == "varejo" and chamado.prazo_em.isoformat() == previa["dados"]["prazo_em"]


@pytest.mark.parametrize(
    ("argumentos", "tipo"),
    [
        ({"categoria": "Pombo-correio"}, "parametro_invalido"),
        ({"canal": "pombo"}, "parametro_invalido"),
        ({"impede_vender": "talvez"}, "parametro_invalido"),
        ({"valor_envolvido": -1}, "parametro_invalido"),
    ],
)
def test_abrir_chamado_recusa_entrada_invalida(engine, argumentos, tipo):
    base = {"id_cliente": "M00001", "categoria": "Maquininha", "resumo": "x"}
    assert preparar(engine, "abrir_chamado", {**base, **argumentos}, ANA)["tipo_erro"] == tipo


def test_nota_do_agente_fica_com_autor_agente_e_quem_confirmou(engine):
    feito = preparar_e_confirmar(engine, "adicionar_nota_chamado", casos_validos(engine)["adicionar_nota_chamado"][0], ANA)
    assert feito["dados"]["canal"] == "interno"
    nota = ler(engine, Interacao, id_chamado=gab.C1_CHAMADO, canal="interno")[-1]
    assert (nota.autor, nota.id_funcionario) == ("agente", ANA)


def test_nota_em_chamado_de_outro_lojista_e_nao_encontrada(engine):
    resposta = preparar(engine, "adicionar_nota_chamado", {"id_cliente": "M00001", "id_chamado": gab.C6_CHAMADO,
                                                            "texto": "x"}, ANA)
    assert resposta["tipo_erro"] == "nao_encontrado"


def test_passagem_fora_do_ciclo_e_recusada_ja_na_previa(engine):
    antes = contagem(engine)
    resposta = preparar(engine, "atualizar_situacao_chamado", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO,
                                                                "nova_situacao": "resolvido"}, ANA)
    assert resposta["tipo_erro"] == "parametro_invalido" and contagem(engine) == antes


def test_so_a_ouvidoria_resolve_o_caso_da_ouvidoria_cenario_9(engine):
    argumentos = {"id_cliente": gab.C9_LOJISTA, "id_chamado": gab.C9_CHAMADO_OUVIDORIA, "nova_situacao": "resolvido"}
    for quem in (ANA, SUPERVISORA):
        resposta = preparar(engine, "atualizar_situacao_chamado", argumentos, quem)
        assert resposta["tipo_erro"] == "permissao_negada" and "ouvidoria" in resposta["mensagem"]
    assert preparar_e_confirmar(engine, "atualizar_situacao_chamado", argumentos, OUVIDORIA)["status"] == "ok"
    (caso,) = ler(engine, Chamado, codigo=gab.C9_CHAMADO_OUVIDORIA)
    assert caso.situacao == "resolvido"


def test_suspeita_de_fraude_sobe_o_chamado_para_o_n2_cenario_6(engine):
    argumentos = {"id_cliente": gab.C6_LOJISTA, "id_chamado": gab.C6_CHAMADO, "suspeita_fraude": "sim"}
    previa = preparar(engine, "atualizar_situacao_chamado", argumentos, N2_VAREJO)
    assert previa["dados"]["suspeita_fraude"].startswith("sim")
    feito = confirmacoes.confirmar(previa["dados"]["confirmacao_id"], pessoa(engine, N2_VAREJO))["dados"]
    assert (feito["suspeita_fraude"], feito["nivel_atendimento"]) == (True, "N2")


def test_atualizar_sem_nada_a_mudar_e_recusado(engine):
    resposta = preparar(engine, "atualizar_situacao_chamado", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO}, ANA)
    assert resposta["tipo_erro"] == "parametro_invalido"


# --- antecipação (DOC-MOCK §7.4, cenário 4) -----------------------------------------------------------------------


def test_cenario_4_n1_registra_o_pedido_e_o_n2_executa(engine):
    previa = preparar(engine, "registrar_pedido_antecipacao", {"id_cliente": gab.C4_LOJISTA, "resumo": "Antecipar."},
                      N1_PME)["dados"]
    assert previa["valor_liquido"] == gab.C4_SIMULACAO["valor_liquido"] and previa["nivel_atendimento"] == "N2"
    pedido = confirmacoes.confirmar(previa["confirmacao_id"], pessoa(engine, N1_PME))["dados"]
    assert preparar(engine, "executar_antecipacao", {"id_cliente": gab.C4_LOJISTA, "id_chamado": pedido["id_chamado"]},
                    N1_PME)["tipo_erro"] == gab.TIPO_ERRO_FERRAMENTA_BLOQUEADA  # executar é do N2
    feito = preparar_e_confirmar(
        engine, "executar_antecipacao", {"id_cliente": gab.C4_LOJISTA, "id_chamado": pedido["id_chamado"]}, N2_PME
    )["dados"]
    for campo in ("quantidade_de_parcelas", "valor_antecipado", "desconto", "valor_liquido", "data_credito"):
        assert feito[campo] == gab.C4_SIMULACAO[campo], campo
    (antecipacao,) = ler(engine, Antecipacao, id_lojista=gab.C4_LOJISTA)
    assert antecipacao.id_executor == N2_PME and antecipacao.id_chamado == pedido["id_chamado"]
    assert len(ler(engine, Recebivel, id_antecipacao=antecipacao.codigo)) == gab.C4_SIMULACAO["quantidade_de_parcelas"]


def test_antecipacao_recusada_nao_vira_pedido_cenario_4(engine):
    resposta = preparar(engine, "registrar_pedido_antecipacao", {"id_cliente": gab.C4_LOJISTA_RECUSADO,
                                                                  "resumo": "Antecipar."}, ANA)
    assert resposta["tipo_erro"] == "parametro_invalido" and gab.C4_MOTIVO_DA_RECUSA_TEXTO in resposta["mensagem"]


def test_executar_exige_chamado_de_antecipacao(engine):
    resposta = preparar(engine, "executar_antecipacao", {"id_cliente": "M00001", "id_chamado": gab.C1_CHAMADO}, N2_VAREJO)
    assert resposta["tipo_erro"] == "parametro_invalido"


# --- liquidação (DOC-MOCK §7.3) -----------------------------------------------------------------------------------


def test_reprocessar_com_conta_invalida_e_recusado_ja_na_previa_cenario_1(engine):
    antes = contagem(engine)
    resposta = preparar(engine, "reprocessar_liquidacao", {"id_cliente": gab.C1_LOJISTA,
                                                            "id_liquidacao": id_da_liquidacao_do_cenario_1(engine)},
                        RECEBIVEIS)
    assert resposta["tipo_erro"] == "parametro_invalido" and "conta" in resposta["mensagem"]
    assert contagem(engine) == antes


def test_reprocessar_com_conta_ativa_agenda_a_nova_tentativa(engine):
    ativar_conta(engine, gab.C1_LOJISTA)
    original = id_da_liquidacao_do_cenario_1(engine)
    feito = preparar_e_confirmar(engine, "reprocessar_liquidacao", {"id_cliente": gab.C1_LOJISTA,
                                                                     "id_liquidacao": original}, RECEBIVEIS)["dados"]
    (nova,) = ler(engine, Liquidacao, id_liquidacao_original=original)
    assert (nova.situacao, nova.id, feito["valor"]) == ("agendada", feito["id_nova_tentativa"], gab.C1_LIQUIDACAO_TEXTO)


def test_reprocessar_so_liquidacao_que_falhou_e_so_dos_recebiveis(engine):
    paga = ler(engine, Liquidacao, id_lojista=gab.C1_LOJISTA, situacao="paga")[0].id
    resposta = preparar(engine, "reprocessar_liquidacao", {"id_cliente": gab.C1_LOJISTA, "id_liquidacao": paga},
                        RECEBIVEIS)
    assert resposta["tipo_erro"] == "parametro_invalido"
    assert preparar(engine, "reprocessar_liquidacao", {"id_cliente": gab.C1_LOJISTA, "id_liquidacao": paga},
                    ANA)["tipo_erro"] == gab.TIPO_ERRO_FERRAMENTA_BLOQUEADA


# --- acordos (DOC-MOCK §7.5 e §7.9) -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argumentos", "aprovacao", "situacao"),
    [
        ({"numero_parcelas": 4}, "dentro da sua alçada", "ativo"),
        ({"numero_parcelas": 10}, "coordenador", "pendente_aprovacao"),
        ({"numero_parcelas": 4, "entrada_percentual": 10}, "coordenador", "pendente_aprovacao"),
    ],
)
def test_alcada_da_analista_cenario_3(engine, argumentos, aprovacao, situacao):
    previa = preparar(engine, "registrar_acordo", {"id_cliente": gab.C3_LOJISTA, **argumentos}, COBRANCA)["dados"]
    assert aprovacao in previa["aprovacao"]
    feito = confirmacoes.confirmar(previa["confirmacao_id"], pessoa(engine, COBRANCA))["dados"]
    assert feito["situacao"] == situacao


@pytest.mark.parametrize("argumentos", [{"numero_parcelas": 13}, {"numero_parcelas": 4, "desconto_principal_percentual": 15}])
def test_acordo_fora_das_regras_e_recusado(engine, argumentos):
    resposta = preparar(engine, "registrar_acordo", {"id_cliente": gab.C3_LOJISTA, **argumentos}, COORDENADORA)
    assert resposta["tipo_erro"] == "parametro_invalido"


def test_quem_pede_o_acordo_nao_aprova(engine):
    pedido = preparar_e_confirmar(engine, "registrar_acordo", {"id_cliente": gab.C3_LOJISTA, "numero_parcelas": 10},
                                  COBRANCA)["dados"]
    assert pedido["situacao"] == "pendente_aprovacao"
    resposta = preparar(engine, "aprovar_acordo", {"id_acordo": pedido["codigo"], "decisao": "aprovar"}, COBRANCA)
    assert resposta["tipo_erro"] == gab.TIPO_ERRO_FERRAMENTA_BLOQUEADA  # a analista nem alcança aprovar
    feito = preparar_e_confirmar(engine, "aprovar_acordo", {"id_acordo": pedido["codigo"], "decisao": "aprovar"},
                                 COORDENADORA)["dados"]
    assert feito["situacao"] == "ativo"


def test_dupla_aprovacao_e_dada_pela_coordenadora_onboarding_8(engine):
    feito = preparar_e_confirmar(engine, "aprovar_acordo", {"id_acordo": "AC0001", "decisao": "aprovar"},
                                 COORDENADORA)["dados"]
    assert feito["situacao"] == "ativo"
    (acordo,) = ler(engine, Acordo, codigo="AC0001")
    assert acordo.id_aprovador == COORDENADORA


def test_recusar_acordo_devolve_as_faturas_a_regua(engine):
    feito = preparar_e_confirmar(engine, "aprovar_acordo", {"id_acordo": "AC0003", "decisao": "recusar"},
                                 COORDENADORA)["dados"]
    assert feito["situacao"] == "recusado"
    resposta = preparar(engine, "aprovar_acordo", {"id_acordo": "AC0003", "decisao": "aprovar"}, COORDENADORA)
    assert resposta["tipo_erro"] == "nao_encontrado"  # já decidido


@pytest.mark.parametrize("argumentos", [{"id_acordo": "XX1", "decisao": "aprovar"}, {"id_acordo": "AC0001", "decisao": "talvez"}])
def test_aprovar_acordo_recusa_entrada_invalida(engine, argumentos):
    assert preparar(engine, "aprovar_acordo", argumentos, COORDENADORA)["tipo_erro"] == "parametro_invalido"
