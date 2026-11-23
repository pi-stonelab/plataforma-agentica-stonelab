"""enviar_email em duas fases: o agente monta a prévia, só quem pediu confirma (KAN-52, passo 7).

Prova o efeito, não só a resposta: o que chegou ao servidor SMTP de teste, o que ficou na fila de
prévias e o que foi para o registro. Os dados são os do mock (M00001 é da carteira varejo da Ana).
"""

import json
import re
import threading
from datetime import timedelta
from unittest import mock

import pytest
from agentes.agente_geral import agente as geral
from ferramentas import (
    catalogo,
    confirmacoes,
    dados_sinteticos,
    governanca,
    mascara,
)
from ferramentas.comunicacao.enviar_email.func import EnviarEmail
from mock.falhas import desligar_todas, ligar
from mock.regras import CAMPOS_NAO_RESTRITOS

from . import apoio_regressao as reg
from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    NEGADO_PELO_CATALOGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_smtp import REMETENTE_DA_SUITE, enviadas

ENVIAR = "enviar_email"
AGENTE = (ENVIAR, "consultar_transacoes_cliente")
PEDIDO = {"id_cliente": "M00001", "assunto": "Liquidação de 14/10", "corpo": "Olá, a liquidação falhou."}
ID_DA_PREVIA = re.compile(r"CONF-[A-Z]{10}")


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


def pessoa(engine, cargo):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])


@pytest.fixture
def ana(engine):
    return pessoa(engine, "atendente_n1")


def preparar(usuario, argumentos=PEDIDO):
    return catalogo.executar(ENVIAR, argumentos, usuario, AGENTE)


def email_real(codigo, papel):
    contatos, _ = dados_sinteticos.buscar_contatos(codigo)
    return next(c["email"] for c in contatos if c["papel"] == papel)


# --- fase 1: a prévia ----------------------------------------------------------------------------


def test_previa_nao_envia_nada_e_mostra_o_contato_mascarado(ana):
    resposta = preparar(ana)
    dados = resposta["dados"]
    assert resposta["status"] == "ok"
    assert ID_DA_PREVIA.fullmatch(dados["confirmacao_id"])
    assert dados["situacao"] == "aguardando_confirmacao"
    assert dados["para"]["papel"] == "financeiro"
    assert re.fullmatch(r"\S\*\*\*@lojistas\.example", dados["para"]["email"])
    assert email_real("M00001", "financeiro") not in json.dumps(resposta)
    assert enviadas() == []
    assert [p["confirmacao_id"] for p in confirmacoes.pendentes(ana)] == [dados["confirmacao_id"]]


def test_cpf_e_cartao_no_texto_saem_mascarados_na_previa_e_no_envio(ana):
    corpo = "CPF 123.456.789-09 e cartão 4111 1111 1111 1111."
    dados = preparar(ana, {**PEDIDO, "corpo": corpo})["dados"]
    assert "***.456.789-**" in dados["corpo"] and "**** **** **** 1111" in dados["corpo"]
    confirmacoes.confirmar(dados["confirmacao_id"], ana)
    (enviada,) = enviadas()
    assert enviada["corpo"] == dados["corpo"]


def test_corpo_maior_que_o_texto_comum_cabe_e_o_teto_de_cada_campo_vale(ana):
    assert preparar(ana, {**PEDIDO, "corpo": "a" * 1500})["status"] == "ok"
    assert preparar(ana, {**PEDIDO, "corpo": "a" * 2001})["tipo_erro"] == "parametro_invalido"
    assert preparar(ana, {**PEDIDO, "assunto": "a" * 121})["tipo_erro"] == "parametro_invalido"
    assert preparar(ana, {**PEDIDO, "corpo": "   "})["tipo_erro"] == "parametro_invalido"


def test_papel_do_contato_escolhido_desconhecido_ou_ausente(engine, ana):
    assert preparar(ana, {**PEDIDO, "papel_contato": "socio"})["dados"]["para"]["papel"] == "socio"
    assert preparar(ana, {**PEDIDO, "papel_contato": "diretor"})["tipo_erro"] == "parametro_invalido"
    cobranca = pessoa(engine, "analista_cobranca")  # M00003 só tem sócio: sem papel, vai para ele
    assert preparar(cobranca, {**PEDIDO, "id_cliente": "M00003"})["dados"]["para"]["papel"] == "socio"
    sem_financeiro = preparar(cobranca, {**PEDIDO, "id_cliente": "M00003", "papel_contato": "financeiro"})
    assert sem_financeiro["tipo_erro"] == "nao_encontrado"


def test_destinatario_escolhido_pelo_modelo_e_recusado(ana):
    ataque = {**PEDIDO, "destinatario": "financeiro@concorrente.example"}
    assert preparar(ana, ataque)["tipo_erro"] == "parametro_invalido"
    assert confirmacoes.pendentes(ana) == []


def test_lojista_fora_da_carteira_e_cargo_sem_contato_nao_preparam(engine, ana):
    assert preparar(ana, {**PEDIDO, "id_cliente": "M00005"})["tipo_erro"] == "permissao_negada"
    disputas = pessoa(engine, "analista_disputas")  # sem a categoria contato: nem enxerga a ferramenta
    assert preparar(disputas) == NEGADO_PELO_CATALOGO
    assert confirmacoes.PEDIDOS == {}


def test_previas_demais_esperando_param_no_limite(ana):
    for _ in range(confirmacoes.LIMITE_POR_USUARIO):
        assert preparar(ana)["status"] == "ok"
    resposta = preparar(ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert resposta["mensagem"] == "Você já tem 5 prévias abertas. Confirme ou descarte uma antes de pedir outra."


# --- fase 2: a confirmação -----------------------------------------------------------------------


def test_quem_pediu_confirma_uma_vez_e_o_conteudo_some_da_fila(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    pedido = confirmacoes.PEDIDOS[confirmacao_id]
    resposta = confirmacoes.confirmar(confirmacao_id, ana)
    assert resposta["status"] == "ok" and re.fullmatch(r"MSG-[0-9A-F]{12}", resposta["dados"]["id_mensagem"])
    (enviada,) = enviadas()
    assert enviada["para"] == email_real("M00001", "financeiro")
    assert enviada["de"].endswith(f" via Stone <{REMETENTE_DA_SUITE}>")
    assert pedido.conteudo == {} and confirmacoes.pendentes(ana) == []
    assert confirmacoes.confirmar(confirmacao_id, ana)["tipo_erro"] == "nao_encontrado"
    assert len(enviadas()) == 1


def test_outra_pessoa_nao_confirma_nem_descobre_que_a_previa_existe(engine, ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    supervisor = pessoa(engine, "supervisor_atendimento")
    inexistente = confirmacoes.confirmar("CONF-NAOEXISTE", supervisor)
    assert confirmacoes.confirmar(confirmacao_id, supervisor) == inexistente
    assert confirmacoes.cancelar(confirmacao_id, supervisor)["tipo_erro"] == "nao_encontrado"
    assert enviadas() == []
    assert confirmacoes.confirmar(confirmacao_id, ana)["status"] == "ok"  # a prévia continuou da Ana


def test_cargo_revalidado_na_confirmacao(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    rebaixada = governanca.usuario_do_cargo(ana.id_usuario, "analista_disputas", ana.carteiras)
    assert confirmacoes.confirmar(confirmacao_id, rebaixada)["tipo_erro"] == "permissao_negada"
    assert enviadas() == []


def test_descartar_nao_envia_e_a_previa_nao_volta(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    assert confirmacoes.cancelar(confirmacao_id, ana)["dados"]["situacao"] == "cancelada"
    assert confirmacoes.confirmar(confirmacao_id, ana)["tipo_erro"] == "nao_encontrado"
    assert enviadas() == []


def test_previa_expira_em_15_minutos_e_apaga_o_conteudo(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    pedido = confirmacoes.PEDIDOS[confirmacao_id]
    depois = pedido.expira_em + timedelta(seconds=1)
    with mock.patch.object(confirmacoes, "agora", return_value=depois):
        assert confirmacoes.pendentes(ana) == []
        assert confirmacoes.confirmar(confirmacao_id, ana)["tipo_erro"] == "nao_encontrado"
    assert pedido.conteudo == {} and enviadas() == []
    assert governanca.REGISTROS[-1]["status"] == "expirada"


def test_destino_do_registro_que_chama_de_volta_durante_a_expiracao_nao_trava_a_fila(ana):
    """O registro de "expirada" é gravado fora da trava da fila: um destino lento ou que volta à fila não a prende."""
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    depois = confirmacoes.PEDIDOS[confirmacao_id].expira_em + timedelta(seconds=1)
    voltou = []

    def destino_que_volta_a_fila(registro):
        if registro["status"] == "expirada":
            voltou.append(confirmacoes.pendentes(ana))

    governanca.adicionar_destino(destino_que_volta_a_fila)
    resultado = []

    def tarefa():
        with mock.patch.object(confirmacoes, "agora", return_value=depois):
            resultado.append(confirmacoes.pendentes(ana))

    with mock.patch.object(confirmacoes, "TRAVA_DOS_PEDIDOS", threading.Lock()):  # uma regressão não trava a suíte
        thread = threading.Thread(target=tarefa, daemon=True)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive(), "a fila travou: registro gravado com a trava tomada"
    assert resultado == [[]] and voltou == [[]]


def test_email_fora_do_ar_nao_envia_e_avisa_para_pedir_nova_previa(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    ligar("email")
    try:
        resposta = confirmacoes.confirmar(confirmacao_id, ana)
    finally:
        desligar_todas()
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert "Nada foi enviado" in resposta["mensagem"]
    assert enviadas() == []


def test_sem_registro_da_intencao_nada_sai_e_a_previa_continua_valendo(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]

    def destino_que_falha(registro):
        raise OSError("disco cheio")

    governanca.adicionar_destino(destino_que_falha)
    assert confirmacoes.confirmar(confirmacao_id, ana)["tipo_erro"] == "integracao_indisponivel"
    assert enviadas() == []
    governanca.DESTINOS.clear()
    assert confirmacoes.confirmar(confirmacao_id, ana)["status"] == "ok"


def destino_que_falha_a_partir_do(numero):
    """Destino de registro que grava as primeiras chamadas e falha da `numero`-ésima em diante."""
    chamadas = []

    def destino(registro):
        chamadas.append(registro)
        if len(chamadas) >= numero:
            raise OSError("disco cheio")

    return destino


def test_registro_final_que_falha_tira_a_previa_da_fila_e_a_nova_tentativa_nao_duplica(ana):
    governanca.adicionar_destino(destino_que_falha_a_partir_do(2))  # grava "iniciada", falha no final
    resposta = preparar(ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert "não repita" not in resposta["mensagem"]  # nada saiu e nada ficou esperando: pode pedir de novo
    assert confirmacoes.pendentes(ana) == []
    assert enviadas() == []
    governanca.DESTINOS.clear()
    nova = preparar(ana)
    assert nova["status"] == "ok"
    assert len(confirmacoes.pendentes(ana)) == 1


def test_erro_depois_de_guardar_a_previa_tambem_tira_ela_da_fila(ana):
    real = mascara.mascarar
    chamadas = []

    def falha_na_segunda(*argumentos):
        chamadas.append(1)
        if len(chamadas) == 2:  # a primeira é a da prévia guardada; a segunda é a da resposta ao agente
            raise ValueError("dados fundos demais")
        return real(*argumentos)

    with mock.patch.object(mascara, "mascarar", side_effect=falha_na_segunda):
        resposta = preparar(ana)
    assert resposta["tipo_erro"] == "erro_interno"
    assert confirmacoes.pendentes(ana) == []


def test_duas_falhas_juntas_dizem_que_nada_foi_enviado_e_nao_deixam_previa(ana):
    """Revisão 2 do Enrico: erro depois de guardar a prévia E registro final fora do ar."""
    real = mascara.mascarar
    chamadas = []

    def falha_na_segunda(*argumentos):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise ValueError("dados fundos demais")
        return real(*argumentos)

    governanca.adicionar_destino(destino_que_falha_a_partir_do(2))
    with mock.patch.object(mascara, "mascarar", side_effect=falha_na_segunda):
        resposta = preparar(ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert "não repita" not in resposta["mensagem"]
    assert "pode ter sido executada" not in resposta["mensagem"]
    assert confirmacoes.pendentes(ana) == []
    assert enviadas() == []


def test_previa_so_aparece_e_so_confirma_depois_que_a_resposta_foi_entregue(ana):
    """Durante o registro final a prévia já está guardada, mas ninguém a vê nem confirma ainda."""
    vistas = {}

    def espiao(registro):
        if registro["status"] == "ok" and not vistas:  # o registro final da fase 1
            ids = list(confirmacoes.PEDIDOS)
            vistas["pendentes"] = confirmacoes.pendentes(ana)
            vistas["confirmacao"] = confirmacoes.confirmar(ids[0], ana)["tipo_erro"]
            vistas["cancelamento"] = confirmacoes.cancelar(ids[0], ana)["tipo_erro"]

    governanca.adicionar_destino(espiao)
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    assert vistas == {"pendentes": [], "confirmacao": "nao_encontrado", "cancelamento": "nao_encontrado"}
    assert [p["confirmacao_id"] for p in confirmacoes.pendentes(ana)] == [confirmacao_id]
    assert enviadas() == []


def test_erro_de_pedido_invalido_com_registro_fora_do_ar_nao_fala_em_acao_executada(ana):
    governanca.adicionar_destino(destino_que_falha_a_partir_do(2))
    resposta = preparar(ana, {**PEDIDO, "assunto": ""})
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert "pode ter sido executada" not in resposta["mensagem"]
    assert confirmacoes.pendentes(ana) == []


def test_assunto_e_corpo_so_passam_sem_mascara_total_na_ferramenta_de_email():
    texto = {"assunto": "Vendas", "corpo": "Segue o resumo."}
    assert mascara.mascarar(texto, ("contato",)) == {"assunto": "***", "corpo": "***"}
    assert mascara.mascarar(texto, ("contato",), EnviarEmail.campos_liberados) == texto
    assert not {"assunto", "corpo", "id_mensagem", "confirmacao_id", "expira_em"} & CAMPOS_NAO_RESTRITOS


def test_campo_liberado_da_ferramenta_ainda_passa_pela_mascara_de_texto_livre():
    texto = {"corpo": "CPF 123.456.789-09"}
    assert mascara.mascarar(texto, ("contato",), ("corpo",)) == {"corpo": "CPF ***.456.789-**"}


def test_registro_tem_so_metadados_das_duas_fases(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    confirmacoes.confirmar(confirmacao_id, ana)
    assert [r["status"] for r in governanca.REGISTROS] == ["iniciada", "ok", "iniciada", "ok"]
    texto = json.dumps(governanca.REGISTROS)
    for trecho in (PEDIDO["assunto"], PEDIDO["corpo"], email_real("M00001", "financeiro"), confirmacao_id):
        assert trecho not in texto


def test_duas_confirmacoes_ao_mesmo_tempo_enviam_uma_vez_so(ana):
    confirmacao_id = preparar(ana)["dados"]["confirmacao_id"]
    respostas = []
    def confirmar():
        respostas.append(confirmacoes.confirmar(confirmacao_id, ana))

    linhas = [threading.Thread(target=confirmar) for _ in range(8)]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()
    assert sorted(r["status"] for r in respostas) == ["erro"] * 7 + ["ok"]
    assert len(enviadas()) == 1


def test_o_agente_nao_tem_como_confirmar(ana):
    assert not [nome for nome in catalogo.nomes() if "confirm" in nome]
    tentativa = catalogo.executar("confirmar", {"confirmacao_id": "CONF-X"}, ana, (*AGENTE, "confirmar"))
    assert tentativa == NEGADO_PELO_CATALOGO


# --- o pedido inteiro pelo agente geral (modelo roteirizado): consultar e preparar o e-mail ---------


def test_agente_consulta_as_vendas_e_prepara_o_email_sem_enviar(engine, ana):
    roteiro = reg.Roteiro(
        [
            reg.ler(),
            reg.ler("financeiro/consultar_transacoes_cliente"),
            reg.usar("consultar_transacoes_cliente", id_cliente="M00001"),
            reg.ler("comunicacao/enviar_email"),
            reg.usar(ENVIAR, **PEDIDO),
            reg.final("A prévia do e-mail está esperando a sua confirmação."),
        ]
    )
    turno = geral.rodar_turno_geral("Mande ao M00001 um e-mail com as vendas.", ana, roteiro)
    assert turno.tipo == "final"
    assert [r["ferramenta"] for r in governanca.REGISTROS if r["status"] == "ok"] == [
        "consultar_transacoes_cliente",
        ENVIAR,
    ]
    assert enviadas() == [] and len(confirmacoes.pendentes(ana)) == 1
    assert email_real("M00001", "financeiro") not in "\n".join(roteiro.prompts)


def test_agente_que_tenta_de_novo_depois_de_registro_fora_do_ar_deixa_uma_previa_so(engine, ana):
    """O caso do Enrico pelo agente: a 1ª tentativa devolve erro de registro, a 2ª funciona. Ficam 0 e depois 1."""
    governanca.adicionar_destino(destino_que_falha_a_partir_do(2))  # "iniciada" grava, o registro final falha
    roteiro = reg.Roteiro(
        [
            reg.ler(),
            reg.ler("comunicacao/enviar_email"),
            reg.usar(ENVIAR, **PEDIDO),
            reg.final("Deu erro de registro; vou tentar de novo."),
        ]
    )
    turno = geral.rodar_turno_geral("Mande o e-mail ao M00001.", ana, roteiro)
    assert turno.tipo == "final"
    assert confirmacoes.pendentes(ana) == [] and enviadas() == []
    governanca.DESTINOS.clear()  # o registro voltou
    segunda = geral.rodar_turno_geral(
        "Tente de novo.",
        ana,
        reg.Roteiro([reg.ler(), reg.ler("comunicacao/enviar_email"), reg.usar(ENVIAR, **PEDIDO), reg.final("Pronto.")]),
    )
    assert segunda.tipo == "final"
    assert len(confirmacoes.pendentes(ana)) == 1 and enviadas() == []
