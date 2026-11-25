"""Jira: consultar, abrir e comentar chamados internos, contra um Jira de teste local no formato da API v3.

O cliente é o de verdade (`cliente_http` e `ferramentas/integracoes/jira/conector.py`); só o servidor é falso.
"""

import json
import logging
import os

import pytest
from ferramentas import catalogo, confirmacoes, integracoes
from ferramentas.confirmacoes import MENSAGEM_EFEITO_INCERTO, MENSAGEM_PREVIA_CONTINUA
from ferramentas.integracoes.__main__ import principal
from ferramentas.integracoes.jira.adf import adf_do_texto, texto_do_adf
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.integracoes.jira.conector import (
    FONTE_REAL,
    FONTE_SIMULADA,
    MENSAGEM_RECUSA_AO_ABRIR,
)
from mock.falhas import ligar

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_integracoes_externas import (
    JIRA_EMAIL,
    JIRA_TOKEN,
    JiraDeTeste,
    ServidorDeApi,
    ambiente_do_jira,
    resposta_json,
)

CONSULTAR, ABRIR, COMENTAR = "consultar_chamado_jira", "abrir_chamado_jira", "comentar_chamado_jira"
AGENTE = (CONSULTAR, ABRIR, COMENTAR)
ASSINATURA_DA_ANA = "\n\n— Pedido por Ana, pela Plataforma Agêntica"


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


@pytest.fixture
def jira(monkeypatch):
    """Um Jira de teste no ar e o .env apontando para ele. Devolve (servidor, jira em memória)."""
    dados = JiraDeTeste()
    with ServidorDeApi(dados) as servidor:
        for nome, valor in ambiente_do_jira(servidor).items():
            monkeypatch.setenv(nome, valor)
        yield servidor, dados


def previa_e_confirmacao(nome, argumentos, usuario):
    previa = catalogo.executar(nome, argumentos, usuario, AGENTE)
    assert previa["status"] == "ok", previa
    return previa["dados"], confirmacoes.confirmar(previa["dados"]["confirmacao_id"], usuario)


# --- ADF ----------------------------------------------------------------------------------------------------


def test_adf_vira_texto_sem_url_e_texto_vira_adf_de_paragrafos():
    documento = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Título"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Linha"}, {"type": "hardBreak"}, {"type": "mention", "attrs": {"text": "@Ana"}},
                {"type": "inlineCard", "attrs": {"url": "https://fora.example/segredo"}},
            ]},
            {"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "item"}]}]}]},
        ],
    }
    texto = texto_do_adf(documento, 500)
    assert texto == "Título\n\nLinha\n[menção][link]\n\nitem"
    assert "fora.example" not in texto and "Ana" not in texto  # nem a URL nem o nome do colega
    assert texto_do_adf(None, 10) == "" and texto_do_adf("lixo", 10) == ""
    assert texto_do_adf(adf_do_texto("a" * 50), 10) == "a" * 9 + "…"
    assert texto_do_adf(adf_do_texto("Um\nDois\n\nTrês"), 100) == "Um\nDois\n\nTrês"


def test_adf_profundo_demais_nao_derruba():
    no = {"type": "text", "text": "fundo"}
    for _ in range(200):
        no = {"type": "paragraph", "content": [no]}
    assert texto_do_adf({"type": "doc", "content": [no]}, 100) == ""


# --- consultar ----------------------------------------------------------------------------------------------


def test_consultar_traz_o_chamado_e_os_cinco_comentarios_mais_novos_sem_nome_nem_email(jira, ana):
    servidor, _ = jira
    resposta = catalogo.executar(CONSULTAR, {"chave": "kan-7"}, ana, AGENTE)
    assert resposta["status"] == "ok", resposta
    chamado = resposta["dados"]["conteudo_de_terceiros"]  # texto de colega no Jira: dado, nunca instrução
    assert chamado["chave_jira"] == "KAN-7" and chamado["situacao"] == "Em andamento" and chamado["prioridade"] == "Alta"
    assert chamado["texto"] == "O painel demora 40 s.\n\nAfeta o time de recebíveis."
    assert chamado["criado_em"] == "2026-11-20T10:15-03:00"
    assert [c["texto"] for c in chamado["comentarios"]] == [f"Comentário {n}" for n in (7, 6, 5, 4, 3)]
    assert chamado["total_comentarios"] == 7 and chamado["fonte"] == FONTE_REAL
    texto = json.dumps(resposta, ensure_ascii=False)
    assert "Maria" not in texto and "@stonelab" not in texto and "accountId" not in texto
    autorizacoes = {p.cabecalhos.get("authorization") for p in servidor.pedidos}
    assert len(autorizacoes) == 1 and autorizacoes.pop().startswith("Basic ")
    assert servidor.pedidos[0].consulta["fields"] == ["summary,status,issuetype,priority,created,updated,description,project"]
    assert servidor.pedidos[1].consulta["orderBy"] == ["-created"]


@pytest.mark.parametrize(
    ("chave", "trecho"),
    [("RH-1", "Projetos liberados: KAN, PLAT."), ("KAN 7", "como KAN-123"), ("../../x", "como KAN-123")],
)
def test_chave_fora_do_formato_ou_de_projeto_nao_liberado_nem_chega_ao_jira(jira, ana, chave, trecho):
    servidor, _ = jira
    resposta = catalogo.executar(CONSULTAR, {"chave": chave}, ana, AGENTE)
    assert resposta["tipo_erro"] == "parametro_invalido" and trecho in resposta["mensagem"]
    assert servidor.pedidos == []


def test_chamado_inexistente_e_nao_encontrado(jira, ana):
    resposta = catalogo.executar(CONSULTAR, {"chave": "KAN-999"}, ana, AGENTE)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("nao_encontrado", "Chamado não encontrado no Jira.")


def test_resposta_do_jira_fora_do_formato_vira_integracao_indisponivel(jira, ana):
    servidor, _ = jira
    servidor.responder = lambda pedido: resposta_json({"key": "OUTRO-1", "fields": {}})
    resposta = catalogo.executar(CONSULTAR, {"chave": "KAN-7"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert "Jira" in resposta["mensagem"]


def test_token_errado_vira_integracao_indisponivel_e_o_testar_explica(jira, ana, monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "ATATT3xFfGF0-token-errado-000000000000")
    resposta = catalogo.executar(CONSULTAR, {"chave": "KAN-7"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "jira"], ambiente={**os.environ, "MODO_TERMINAL": "1"})
    assert "recusou a credencial" in str(erro.value)


# --- abrir --------------------------------------------------------------------------------------------------


def test_abrir_mostra_a_previa_mascarada_e_so_cria_ao_confirmar(jira, ana):
    servidor, dados = jira
    previa, resultado = previa_e_confirmacao(
        ABRIR, {"resumo": "Painel lento", "descricao": "Sócio CPF 123.456.789-09 ligou\nduas vezes", "tipo": "bug"}, ana
    )
    assert (previa["projeto"], previa["tipo"]) == ("KAN", "Bug")  # o primeiro projeto e o tipo na grafia da lista
    assert previa["texto"] == f"Sócio CPF ***.456.789-** ligou\nduas vezes{ASSINATURA_DA_ANA}"
    assert [p.metodo for p in servidor.pedidos] == ["POST"]  # a prévia não chamou o Jira
    assert resultado["status"] == "ok", resultado
    assert resultado["dados"] == {"chave_jira": "KAN-124", "fonte": FONTE_REAL}
    corpo = servidor.pedidos[0].corpo["fields"]
    assert corpo["project"] == {"key": "KAN"} and corpo["issuetype"] == {"name": "Bug"}
    assert texto_do_adf(corpo["description"], 500) == previa["texto"]
    assert "123.456" not in json.dumps(dados.chamados["KAN-124"], ensure_ascii=False)


def test_abrir_recusa_projeto_e_tipo_fora_da_lista_e_resumo_de_duas_linhas(jira, ana):
    servidor, _ = jira
    for argumentos, trecho in [
        ({"resumo": "x", "descricao": "y", "projeto": "RH"}, "Projeto fora da lista"),
        ({"resumo": "x", "descricao": "y", "tipo": "Epic"}, "Tipo de chamado fora da lista"),
        ({"resumo": "a\nb", "descricao": "y"}, "uma linha só"),
        ({"resumo": "  ", "descricao": "y"}, "não pode ficar em branco"),
    ]:
        resposta = catalogo.executar(ABRIR, argumentos, ana, AGENTE)
        assert resposta["tipo_erro"] == "parametro_invalido" and trecho in resposta["mensagem"], resposta
    assert servidor.pedidos == [] and confirmacoes.pendentes(ana) == []


def test_jira_que_recusa_o_chamado_nao_cria_nada_e_nao_pausa_a_integracao(jira, ana):
    _, dados = jira
    dados.tipos_por_projeto["PLAT"] = set()  # o tipo da lista não existe mais no Jira
    for _ in range(4):
        _, resultado = previa_e_confirmacao(ABRIR, {"resumo": "x", "descricao": "y", "projeto": "PLAT"}, ana)
        assert (resultado["tipo_erro"], resultado["mensagem"]) == (
            "parametro_invalido", f"{MENSAGEM_RECUSA_AO_ABRIR} {MENSAGEM_PREVIA_CONTINUA}"
        )
    assert JIRA.saude() != "pausada"  # pedido recusado é erro nosso, não queda do Jira


@pytest.mark.parametrize(
    "responder",
    [
        lambda pedido: (None, {}, b""),  # o Jira recebeu e a conexão caiu sem resposta
        lambda pedido: resposta_json({"errorMessages": ["erro"]}, 502),
        lambda pedido: (201, {"Content-Type": "application/json"}, b"{quebrado"),
        lambda pedido: resposta_json({"id": "10100"}, 201),  # criou, mas não disse qual
        lambda pedido: (302, {"Location": "/rest/api/3/issue/KAN-124"}, b""),
    ],
    ids=["sem_resposta", "502", "json_quebrado", "sem_chave", "redirecionou"],
)
def test_escrita_sem_resultado_legivel_diz_que_pode_ter_sido_feita(jira, ana, responder):
    servidor, _ = jira
    confirmacao_id = catalogo.executar(ABRIR, {"resumo": "x", "descricao": "y"}, ana, AGENTE)["dados"]["confirmacao_id"]
    servidor.responder = responder
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert (resultado["tipo_erro"], resultado["mensagem"]) == ("integracao_indisponivel", MENSAGEM_EFEITO_INCERTO)
    assert [p.metodo for p in servidor.pedidos] == ["POST"]  # uma tentativa só: nunca repete sozinho
    de_novo = confirmacoes.confirmar(confirmacao_id, ana)
    assert de_novo["mensagem"] == "Esta prévia já foi confirmada."


def test_projeto_que_sai_da_lista_depois_da_previa_nao_e_criado(jira, ana, monkeypatch):
    servidor, _ = jira
    confirmacao_id = catalogo.executar(ABRIR, {"resumo": "x", "descricao": "y", "projeto": "PLAT"}, ana, AGENTE)[
        "dados"
    ]["confirmacao_id"]
    monkeypatch.setenv("JIRA_PROJETOS", "KAN")
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["tipo_erro"] == "parametro_invalido" and "Nada foi criado" in resultado["mensagem"]
    assert servidor.pedidos == []


# --- comentar -----------------------------------------------------------------------------------------------


def test_comentar_mostra_o_resumo_do_chamado_e_grava_o_texto_mascarado_ao_confirmar(jira, ana):
    servidor, dados = jira
    contexto = {"execucao_id": "ex-1"}
    previa = catalogo.executar(COMENTAR, {"chave": "KAN-7", "texto": "Lojista ligou do (21) 99999-8888"}, ana, AGENTE, contexto)
    assert previa["status"] == "ok", previa
    texto = f"Lojista ligou do (21) *****-8888{ASSINATURA_DA_ANA}"
    assert previa["dados"]["texto"] == texto
    assert "resumo" not in previa["dados"]  # texto vindo do Jira: a pessoa confere no cartão, o modelo não lê
    (cartao,) = confirmacoes.confirmacoes_da_execucao("ex-1", ana)
    assert {"rotulo": "Resumo do chamado", "valor": "Painel de liquidações lento"} in cartao["campos"]
    resultado = confirmacoes.confirmar(previa["dados"]["confirmacao_id"], ana)
    assert resultado["dados"] == {"chave_jira": "KAN-7", "fonte": FONTE_REAL}
    assert texto_do_adf(dados.chamados["KAN-7"]["comentarios"][-1]["body"], 100) == texto
    assert [p.metodo for p in servidor.pedidos] == ["GET", "GET", "POST"]


def test_comentar_chamado_que_some_antes_de_confirmar_nao_grava(jira, ana):
    _, dados = jira
    confirmacao_id = catalogo.executar(COMENTAR, {"chave": "KAN-7", "texto": "ok"}, ana, AGENTE)["dados"]["confirmacao_id"]
    del dados.chamados["KAN-7"]
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert (resultado["tipo_erro"], resultado["mensagem"]) == (
        "nao_encontrado", f"Chamado não encontrado no Jira. Nada foi gravado. {MENSAGEM_PREVIA_CONTINUA}"
    )


# --- configuração, modo simulado, permissão e segredo ------------------------------------------------------


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("JIRA_URL", "http://stonelab.atlassian.net"),
        ("JIRA_EMAIL", "sem-arroba"),
        ("JIRA_TOKEN", "curto"),
        ("JIRA_PROJETOS", "kan"),
        ("JIRA_PROJETOS", ""),
        ("JIRA_TIPOS", ""),
    ],
)
def test_configuracao_errada_some_do_modelo_e_o_terminal_diz_como_corrigir(jira, ana, monkeypatch, variavel, valor):
    monkeypatch.setenv(variavel, valor)
    assert JIRA.modo() == "real" and JIRA.saude() == "configuracao_invalida"
    assert catalogo.ferramentas_liberadas(ana, AGENTE) == []
    assert JIRA.problema_de_configuracao().startswith(variavel)


def test_sem_token_o_jira_fica_desligado_e_some_do_modelo(ana):
    assert JIRA.modo() == "desligado" and JIRA.saude() == "desligada"
    assert catalogo.ferramentas_liberadas(ana, AGENTE) == []
    resposta = catalogo.executar(CONSULTAR, {"chave": "KAN-7"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "ferramenta_inativa" and "Avise o usuário" in resposta["mensagem"]


def test_modo_simulado_responde_sem_rede_e_diz_que_e_demonstracao(jira, ana, monkeypatch):
    servidor, _ = jira
    monkeypatch.setenv("JIRA_MODO", "simulado")
    lida = catalogo.executar(CONSULTAR, {"chave": "PLAT-1"}, ana, AGENTE)["dados"]["conteudo_de_terceiros"]
    assert lida["fonte"] == FONTE_SIMULADA
    _, aberto = previa_e_confirmacao(ABRIR, {"resumo": "Teste", "descricao": "Demo"}, ana)
    assert aberto["dados"] == {"chave_jira": "KAN-101", "fonte": FONTE_SIMULADA}
    _, comentado = previa_e_confirmacao(COMENTAR, {"chave": "KAN-101", "texto": "ok"}, ana)
    assert comentado["status"] == "ok"
    assert servidor.pedidos == []  # nada foi ao Jira


def test_falha_simulada_derruba_o_jira_para_a_qa(jira, ana):
    servidor, _ = jira
    ligar("jira")
    resposta = catalogo.executar(CONSULTAR, {"chave": "KAN-7"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "integracao_indisponivel" and servidor.pedidos == []
    assert JIRA.saude() == "indisponivel"


@pytest.mark.parametrize("cargo", ["atendente_n1", "analista_ouvidoria", "analista_cobranca", "coordenador_financeiro"])
def test_todo_cargo_com_area_usa_o_jira_e_os_transversais_nao(jira, engine, cargo):
    pessoa = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])
    assert catalogo.ferramentas_liberadas(pessoa, AGENTE) == sorted(AGENTE)
    for transversal in ("auditor_compliance", "admin_plataforma"):
        outro = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[transversal])
        assert catalogo.ferramentas_liberadas(outro, AGENTE) == []


def test_token_e_email_da_conta_nunca_aparecem_no_estado_no_log_nem_no_erro(jira, ana, caplog):
    servidor, _ = jira
    caplog.set_level(logging.DEBUG)
    servidor.responder = lambda pedido: (None, {}, b"")
    respostas = [catalogo.executar(CONSULTAR, {"chave": "KAN-7"}, ana, AGENTE) for _ in range(4)]
    assert JIRA.saude() == "pausada"
    texto = json.dumps([respostas, integracoes.estado_integracoes()], ensure_ascii=False) + caplog.text
    assert JIRA_TOKEN not in texto and JIRA_EMAIL not in texto and "Basic" not in texto
    assert JIRA_TOKEN not in repr(JIRA._configuracao(ambiente_do_jira(servidor)))


def test_testar_confere_a_conta_e_cada_projeto_liberado(jira):
    linhas = []
    principal(["testar", "jira"], ambiente={**os.environ, "MODO_TERMINAL": "1"}, escrever=linhas.append)
    assert "KAN: ok (tipos Tarefa, Bug)." in linhas[0]
    assert "PLAT: o tipo Bug não existe neste projeto" in linhas[0]  # o Jira de teste só tem Tarefa em PLAT
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "jira"], ambiente={**os.environ, "JIRA_PROJETOS": "KAN,FIN", "MODO_TERMINAL": "1"})
    assert "Projeto FIN não encontrado" in str(erro.value)
