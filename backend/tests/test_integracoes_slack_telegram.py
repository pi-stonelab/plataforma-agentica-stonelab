"""Slack e Telegram: mensagem num canal (ou chat) interno da lista do .env, com confirmação de quem pediu.

O cliente é o de verdade; só o servidor é falso (`apoio_integracoes_externas.py`, no formato das APIs).
"""

import json
import logging
import os
import traceback

import pytest
from ferramentas import catalogo, confirmacoes, integracoes
from ferramentas.confirmacoes import MENSAGEM_EFEITO_INCERTO, MENSAGEM_FORA_DO_AR
from ferramentas.integracoes.__main__ import principal
from ferramentas.integracoes.slack.conector import CONECTOR as SLACK
from ferramentas.integracoes.slack.conector import FONTE_REAL as FONTE_SLACK
from ferramentas.integracoes.slack.conector import FONTE_SIMULADA as SLACK_SIMULADO
from ferramentas.integracoes.telegram.conector import CONECTOR as TELEGRAM
from ferramentas.integracoes.telegram.conector import FONTE_REAL as FONTE_TELEGRAM
from ferramentas.integracoes.telegram.conector import FONTE_SIMULADA as TELEGRAM_SIMULADO

from .apoio_ferramentas import FUNCIONARIO_DO_CARGO, limpar_estado, mundo_do_mock, usuario_do_diretorio
from .apoio_http import porta_que_recusa
from .apoio_integracoes_externas import (
    SLACK_TOKEN,
    TELEGRAM_TOKEN,
    ServidorDeApi,
    SlackDeTeste,
    TelegramDeTeste,
    ambiente_do_slack,
    ambiente_do_telegram,
    resposta_json,
)

SLACK_FERRAMENTA, TELEGRAM_FERRAMENTA = "enviar_mensagem_slack", "enviar_aviso_telegram"
AGENTE = (SLACK_FERRAMENTA, TELEGRAM_FERRAMENTA)
ASSINATURA_DA_ANA = "\n\n— Ana, pela Plataforma Agêntica"


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["atendente_n1"])


def _no_ambiente(monkeypatch, valores):
    for nome, valor in valores.items():
        monkeypatch.setenv(nome, valor)


@pytest.fixture
def slack(monkeypatch):
    dados = SlackDeTeste()
    with ServidorDeApi(dados) as servidor:
        _no_ambiente(monkeypatch, ambiente_do_slack(servidor))
        yield servidor, dados


@pytest.fixture
def telegram(monkeypatch):
    dados = TelegramDeTeste()
    with ServidorDeApi(dados) as servidor:
        _no_ambiente(monkeypatch, ambiente_do_telegram(servidor))
        yield servidor, dados


def previa(nome, argumentos, usuario):
    resposta = catalogo.executar(nome, argumentos, usuario, AGENTE)
    assert resposta["status"] == "ok", resposta
    return resposta["dados"]


# --- Slack --------------------------------------------------------------------------------------------------


def test_slack_publica_no_id_do_apelido_o_texto_mascarado_e_assinado(slack, ana):
    servidor, dados = slack
    preparada = previa(SLACK_FERRAMENTA, {"canal": "Financeiro", "texto": "Cartão 4111 1111 1111 1111 do lojista"}, ana)
    assert preparada["canal"] == "financeiro"
    assert preparada["texto"] == "Cartão **** **** **** 1111 do lojista" + ASSINATURA_DA_ANA  # a assinatura já na prévia
    assert servidor.pedidos == []
    resultado = confirmacoes.confirmar(preparada["confirmacao_id"], ana)
    assert resultado["dados"] == {"canal": "financeiro", "fonte": FONTE_SLACK}
    (publicada,) = dados.publicadas
    assert publicada == {"channel": "C0123ABCD", "text": preparada["texto"], "unfurl_links": False, "unfurl_media": False}
    assert servidor.pedidos[0].cabecalhos["authorization"] == f"Bearer {SLACK_TOKEN}"


def test_slack_canal_fora_da_lista_diz_os_liberados_e_nao_chama_nada(slack, ana):
    servidor, _ = slack
    resposta = catalogo.executar(SLACK_FERRAMENTA, {"canal": "C9999ZZZZ", "texto": "oi"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "parametro_invalido"
    assert resposta["mensagem"] == "Canal fora da lista desta plataforma. Liberados: arquivado, financeiro, plantao."
    assert servidor.pedidos == []


@pytest.mark.parametrize(
    ("canais", "erro_esperado"),
    [("financeiro:C0999XXXX", "não existe mais"), ("financeiro:C0789IJKL", "não existe mais")],
)
def test_slack_canal_que_recusa_nao_publica_e_nao_pausa(slack, ana, monkeypatch, canais, erro_esperado):
    monkeypatch.setenv("SLACK_CANAIS", canais)
    for _ in range(4):
        confirmacao_id = previa(SLACK_FERRAMENTA, {"canal": "financeiro", "texto": "oi"}, ana)["confirmacao_id"]
        resultado = confirmacoes.confirmar(confirmacao_id, ana)
        assert resultado["tipo_erro"] == "integracao_indisponivel" and erro_esperado in resultado["mensagem"]
        assert "Nada foi enviado" in resultado["mensagem"]
    assert SLACK.saude() != "pausada"


@pytest.mark.parametrize("erro", ["invalid_auth", "ratelimited", "erro_que_o_slack_inventou"])
def test_slack_credencial_limite_e_recusa_desconhecida_dizem_que_nada_saiu(slack, ana, erro):
    _, dados = slack
    confirmacao_id = previa(SLACK_FERRAMENTA, {"canal": "plantao", "texto": "oi"}, ana)["confirmacao_id"]
    dados.recusa_seguinte = erro
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert (resultado["tipo_erro"], resultado["mensagem"]) == ("integracao_indisponivel", MENSAGEM_FORA_DO_AR)
    assert dados.publicadas == []


@pytest.mark.parametrize(
    "responder",
    [
        lambda pedido: resposta_json({"ok": True}),  # publicou, mas sem o ts
        lambda pedido: (200, {"Content-Type": "application/json"}, b"<html>"),
        lambda pedido: (None, {}, b""),
    ],
    ids=["sem_ts", "corpo_quebrado", "sem_resposta"],
)
def test_slack_sem_resultado_legivel_pode_ter_publicado(slack, ana, responder):
    servidor, _ = slack
    confirmacao_id = previa(SLACK_FERRAMENTA, {"canal": "plantao", "texto": "oi"}, ana)["confirmacao_id"]
    servidor.responder = responder
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["mensagem"] == MENSAGEM_EFEITO_INCERTO and len(servidor.pedidos) == 1


def test_slack_testar_confere_o_token_e_lista_os_canais(slack):
    linhas = []
    principal(["testar", "slack"], ambiente={**os.environ, "MODO_TERMINAL": "1"}, escrever=linhas.append)
    assert "Canais liberados: arquivado, financeiro, plantao" in linhas[0]
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "slack"], ambiente={**os.environ, "SLACK_TOKEN": "xoxb-0000000000-errado", "MODO_TERMINAL": "1"})
    assert "recusou a credencial" in str(erro.value)


# --- Telegram -----------------------------------------------------------------------------------------------


def test_telegram_envia_ao_chat_do_apelido_sem_formatacao_nem_previa_de_link(telegram, ana):
    servidor, dados = telegram
    preparada = previa(TELEGRAM_FERRAMENTA, {"chat": "plantao", "texto": "Core fora do ar desde 10h"}, ana)
    resultado = confirmacoes.confirmar(preparada["confirmacao_id"], ana)
    assert resultado["dados"] == {"chat": "plantao", "fonte": FONTE_TELEGRAM}
    (enviada,) = dados.enviadas
    assert enviada == {
        "chat_id": "-1001234567890",
        "text": "Core fora do ar desde 10h" + ASSINATURA_DA_ANA,
        "link_preview_options": {"is_disabled": True},
    }
    assert "parse_mode" not in enviada


def test_telegram_chat_que_o_bot_nao_alcanca_nao_envia_nada(telegram, ana, monkeypatch):
    _, dados = telegram
    monkeypatch.setenv("TELEGRAM_CHATS", "plantao:-1009999999999")
    confirmacao_id = previa(TELEGRAM_FERRAMENTA, {"chat": "plantao", "texto": "oi"}, ana)["confirmacao_id"]
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["tipo_erro"] == "integracao_indisponivel" and "o bot não está nele" in resultado["mensagem"]
    assert dados.enviadas == [] and TELEGRAM.saude() != "pausada"


@pytest.mark.parametrize(
    "falha",
    ["sem_resposta", "500", "timeout", "token_errado", "porta_fechada", "corpo_quebrado"],
)
def test_token_do_telegram_nunca_aparece_em_log_erro_estado_nem_traceback(telegram, ana, monkeypatch, caplog, falha):
    servidor, _ = telegram
    caplog.set_level(logging.DEBUG)
    confirmacao_id = previa(TELEGRAM_FERRAMENTA, {"chat": "coordenacao", "texto": "oi"}, ana)["confirmacao_id"]
    respostas = {
        "sem_resposta": lambda pedido: (None, {}, b""),
        "500": lambda pedido: resposta_json({"ok": False}, 500),
        "token_errado": lambda pedido: resposta_json({"ok": False, "error_code": 401, "description": "Unauthorized"}, 401),
        "corpo_quebrado": lambda pedido: (200, {"Content-Type": "application/json"}, b"{"),
    }
    if falha in respostas:
        servidor.responder = respostas[falha]
    if falha == "timeout":
        servidor.atraso = 0.5
        monkeypatch.setattr("ferramentas.integracoes.cliente_http.TEMPO_LIMITE", 0.2)
    excecoes = []
    if falha == "porta_fechada":
        with porta_que_recusa() as url:
            monkeypatch.setenv("TELEGRAM_URL", url)
            resultado = confirmacoes.confirmar(confirmacao_id, ana)
            try:
                TELEGRAM.enviar("coordenacao", "oi")
            except Exception as erro:  # noqa: BLE001
                excecoes.append(erro)
    else:
        resultado = confirmacoes.confirmar(confirmacao_id, ana)
        try:
            TELEGRAM.enviar("coordenacao", "oi")
        except Exception as erro:  # noqa: BLE001
            excecoes.append(erro)
    assert resultado["status"] == "erro"
    rastros = "".join("".join(traceback.format_exception(e)) + repr(e) for e in excecoes)
    texto = json.dumps([resultado, integracoes.estado_integracoes()], ensure_ascii=False) + caplog.text + rastros
    segredo = TELEGRAM_TOKEN.split(":")[1]
    assert segredo not in texto and TELEGRAM_TOKEN not in texto


def test_telegram_testar_diz_o_nome_do_bot(telegram):
    linhas = []
    principal(["testar", "telegram"], ambiente={**os.environ, "MODO_TERMINAL": "1"}, escrever=linhas.append)
    assert "@stonelab_plataforma_bot" in linhas[0] and "coordenacao, plantao" in linhas[0]


# --- configuração, simulado e permissão ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("SLACK_TOKEN", "xoxp-token-de-pessoa-0000"),
        ("SLACK_CANAIS", "C0123ABCD"),
        ("SLACK_CANAIS", "Financeiro:C0123ABCD"),
        ("SLACK_CANAIS", "fin:C0123ABCD,fin:C0456EFGH"),
        ("SLACK_CANAIS", ""),
        ("SLACK_URL", "https://slack.com/api?x=1"),
    ],
)
def test_slack_configuracao_errada_some_do_modelo(slack, ana, monkeypatch, variavel, valor):
    monkeypatch.setenv(variavel, valor)
    assert SLACK.saude() == "configuracao_invalida"
    assert SLACK_FERRAMENTA not in catalogo.ferramentas_liberadas(ana, AGENTE)
    assert SLACK.problema_de_configuracao().startswith(variavel)


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [("TELEGRAM_TOKEN", "123:curto"), ("TELEGRAM_TOKEN", "123456789:AAH/../../x/abcdefghijklmnopqrstuvwxyz"),
     ("TELEGRAM_CHATS", "plantao:@canal"), ("TELEGRAM_URL", "http://api.telegram.org")],
)
def test_telegram_configuracao_errada_some_do_modelo(telegram, ana, monkeypatch, variavel, valor):
    monkeypatch.setenv(variavel, valor)
    assert TELEGRAM.saude() == "configuracao_invalida"
    assert TELEGRAM_FERRAMENTA not in catalogo.ferramentas_liberadas(ana, AGENTE)


def test_sem_token_os_dois_ficam_desligados(ana):
    assert (SLACK.modo(), TELEGRAM.modo()) == ("desligado", "desligado")
    assert catalogo.ferramentas_liberadas(ana, AGENTE) == []


def test_modo_simulado_guarda_em_memoria_e_diz_que_e_demonstracao(ana, monkeypatch):
    _no_ambiente(monkeypatch, {"SLACK_MODO": "simulado", "TELEGRAM_MODO": "simulado"})
    _no_ambiente(monkeypatch, {"SLACK_CANAIS": "financeiro:C0123ABCD", "TELEGRAM_CHATS": "plantao:-1001234567890"})
    for nome, destino, fonte in [(SLACK_FERRAMENTA, {"canal": "financeiro"}, SLACK_SIMULADO), (TELEGRAM_FERRAMENTA, {"chat": "plantao"}, TELEGRAM_SIMULADO)]:
        confirmacao_id = previa(nome, {**destino, "texto": "teste"}, ana)["confirmacao_id"]
        assert confirmacoes.confirmar(confirmacao_id, ana)["dados"]["fonte"] == fonte
    assert SLACK.simuladas.listar()[0]["texto"] == "teste" + ASSINATURA_DA_ANA
    assert TELEGRAM.simulados.listar()[0]["chat"] == "plantao"


def test_canal_que_sai_da_lista_depois_da_previa_nao_publica(slack, ana, monkeypatch):
    servidor, _ = slack
    confirmacao_id = previa(SLACK_FERRAMENTA, {"canal": "plantao", "texto": "oi"}, ana)["confirmacao_id"]
    monkeypatch.setenv("SLACK_CANAIS", "financeiro:C0123ABCD")
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["tipo_erro"] == "parametro_invalido" and servidor.pedidos == []


def test_auditor_e_admin_nao_mandam_mensagem(slack, telegram, engine):
    for cargo in ("auditor_compliance", "admin_plataforma"):
        pessoa = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])
        assert catalogo.ferramentas_liberadas(pessoa, AGENTE) == []
    cobranca = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["analista_cobranca"])
    assert catalogo.ferramentas_liberadas(cobranca, AGENTE) == sorted(AGENTE)


def test_modo_simulado_sem_lista_usa_destinos_de_exemplo(ana, monkeypatch):
    _no_ambiente(monkeypatch, {"SLACK_MODO": "simulado", "TELEGRAM_MODO": "simulado"})
    assert SLACK.apelidos() == ["financeiro", "plantao"] and TELEGRAM.apelidos() == ["plantao"]
    assert previa(TELEGRAM_FERRAMENTA, {"chat": "plantao", "texto": "teste"}, ana)["situacao"] == "aguardando_confirmacao"
    monkeypatch.setenv("SLACK_MODO", "real")  # no real, sem lista nada é liberado
    assert SLACK.configurado() is False
