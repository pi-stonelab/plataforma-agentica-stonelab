"""Leitura de e-mail por IMAP (`buscar_emails`), contra um servidor IMAP de teste local em socket de verdade.

O cliente é o de verdade (`imaplib` em `ferramentas/integracoes/email_leitura/conector.py`); só o servidor é falso.
"""

import json
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from ferramentas import catalogo, dados_sinteticos, integracoes
from ferramentas.integracoes.__main__ import principal
from ferramentas.integracoes.email_leitura.conector import (
    CONECTOR as EMAIL_LEITURA,
)
from ferramentas.integracoes.email_leitura.conector import (
    FONTE_REAL,
    FONTE_SIMULADA,
    TAMANHO_MAXIMO_DA_MENSAGEM,
    TRECHO_DE_MENSAGEM_GRANDE,
    criterio_de_remetentes,
    data_do_imap,
)
from mock.falhas import ligar

from .apoio_ferramentas import FUNCIONARIO_DO_CARGO, limpar_estado, mundo_do_mock, usuario_do_diretorio
from .apoio_imap import SENHA, ServidorImap, ambiente_do_imap, entrada

BUSCAR = "buscar_emails"
AGENTE = (BUSCAR,)
FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = dados_sinteticos.HOJE_DO_MOCK
CPF_NO_TEXTO = "Meu CPF é 123.456.789-09, me liguem."


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine, monkeypatch):
    limpar_estado()
    # Numa caixa real o período padrão conta do dia de verdade; aqui, parado no "hoje" do mock.
    monkeypatch.setattr(EMAIL_LEITURA, "agora_real", lambda: datetime(HOJE.year, HOJE.month, HOJE.day, 12, tzinfo=FUSO))
    yield
    limpar_estado()


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["atendente_n1"])


def contato(codigo, papel):
    contatos, _ = dados_sinteticos.buscar_contatos(codigo)
    return next(c["email"] for c in contatos if c["papel"] == papel)


@pytest.fixture
def caixa(monkeypatch):
    """Uma caixa com mensagens da M00001 (sócio e financeiro), de outro lojista e de fora do período."""
    socio, financeiro = contato("M00001", "socio"), contato("M00001", "financeiro")
    mensagens = [
        entrada(socio, "Depósito antigo", "2026-08-01T10:00:00-03:00", texto="Fora do período padrão."),
        entrada(contato("M00002", "socio"), "Outro lojista", "2026-10-10T10:00:00-03:00", texto="Não é da M00001."),
        entrada(socio, "Dinheiro não caiu", "2026-10-14T09:30:00-03:00", texto=CPF_NO_TEXTO),
        entrada(financeiro, "Re: Liquidação de 14/10", "2026-10-15T08:00:00-03:00", html="<p>Obrigada <b>pelo</b> retorno</p>"),
    ]
    with ServidorImap(mensagens) as servidor:
        for nome, valor in ambiente_do_imap(servidor).items():
            monkeypatch.setenv(nome, valor)
        yield servidor


def buscar(usuario, **argumentos):
    return catalogo.executar(BUSCAR, {"id_cliente": "M00001", **argumentos}, usuario, AGENTE)


def lido(resposta):
    """Os dados de uma resposta com texto de terceiros (a base os embrulha em `conteudo_de_terceiros`)."""
    assert resposta["status"] == "ok", resposta
    return resposta["dados"]["conteudo_de_terceiros"]


# --- caixa real (servidor local) ----------------------------------------------------------------------------


def test_le_so_as_mensagens_do_lojista_no_periodo_da_mais_nova_para_a_mais_antiga(caixa, ana):
    resposta = buscar(ana)
    dados = lido(resposta)
    assert (dados["data_inicio"], dados["data_fim"], dados["total"], dados["fonte"]) == (
        "2026-09-15", "2026-10-15", 2, FONTE_REAL,
    )
    primeira, segunda = dados["mensagens"]
    assert primeira["texto"] == "Assunto: Re: Liquidação de 14/10\nObrigada pelo retorno"  # HTML sem as tags
    assert primeira["data_hora"] == "2026-10-15T08:00-03:00"
    assert segunda["texto"].startswith("Assunto: Dinheiro não caiu\n")
    assert "123.456.789-09" not in json.dumps(dados, ensure_ascii=False)  # CPF do texto mascarado
    assert all("@" in m["email"] and m["email"] != contato("M00001", "socio") for m in dados["mensagens"])
    assert resposta["mensagem"].startswith("Conteúdo de terceiros")


def test_a_caixa_abre_so_para_leitura_e_nada_do_modelo_vai_ao_comando_imap(caixa, ana):
    buscar(ana, assunto='x" OR ALL "')
    comandos = " ".join(caixa.comandos)
    assert "EXAMINE" in comandos and "SELECT" not in comandos and "STORE" not in comandos
    assert "BODY.PEEK" in comandos and "BODY[]" not in comandos.replace("BODY.PEEK[]", "")
    assert "OR ALL" not in comandos and SENHA not in comandos


def test_filtro_de_assunto_e_limite(caixa, ana):
    dados = lido(buscar(ana, assunto="liquidação"))
    assert dados["total"] == 1 and dados["mensagens"][0]["texto"].startswith("Assunto: Re: Liquidação")
    dados = lido(buscar(ana, limite=1))
    assert (len(dados["mensagens"]), dados["total"]) == (1, 2)


def test_periodo_escolhido_e_mensagem_grande_so_com_o_cabecalho(monkeypatch, ana):
    grande = entrada(contato("M00001", "socio"), "Anexo enorme", "2026-08-01T10:00:00-03:00", texto="a",
                     tamanho_extra=TAMANHO_MAXIMO_DA_MENSAGEM)
    with ServidorImap([grande]) as servidor:
        for nome, valor in ambiente_do_imap(servidor).items():
            monkeypatch.setenv(nome, valor)
        dados = lido(buscar(ana, data_inicio="2026-07-15", data_fim="2026-08-15"))
    assert dados["mensagens"][0]["texto"] == f"Assunto: Anexo enorme\n{TRECHO_DE_MENSAGEM_GRANDE}"
    assert not any("BODY.PEEK[]" in comando for comando in servidor.comandos)


@pytest.mark.parametrize(
    ("argumentos", "trecho"),
    [
        ({"data_inicio": "2026-01-01", "data_fim": "2026-10-15"}, "até 180 dias"),
        ({"limite": 11}, "entre 1 e 10"),
        ({"limite": 0}, "entre 1 e 10"),
    ],
)
def test_periodo_e_limite_fora_do_permitido(caixa, ana, argumentos, trecho):
    resposta = buscar(ana, **argumentos)
    assert resposta["tipo_erro"] == "parametro_invalido" and trecho in resposta["mensagem"]
    assert caixa.comandos == []


def test_lojista_de_outra_carteira_e_negado_antes_de_conectar(caixa, ana):
    resposta = catalogo.executar(BUSCAR, {"id_cliente": "M00005"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "permissao_negada"
    assert caixa.comandos == []


def test_endereco_de_teste_da_demo_entra_como_remetente(caixa, ana, monkeypatch):
    monkeypatch.setenv("EMAIL_DESTINO_TESTE", "pedro.teste@stonelab.example")
    buscar(ana)
    busca = next(c for c in caixa.comandos if c.startswith("SEARCH"))
    assert '"pedro.teste@stonelab.example"' in busca and contato("M00001", "socio") in busca


def test_senha_errada_vira_integracao_indisponivel_sem_vazar_nada(caixa, ana, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("EMAIL_IMAP_SENHA", "outra-senha-de-teste")
    resposta = buscar(ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    texto = json.dumps([resposta, integracoes.estado_integracoes()], ensure_ascii=False) + caplog.text
    assert "outra-senha-de-teste" not in texto and "127.0.0.1" not in texto


def test_pasta_inexistente_e_configuracao_invalida(caixa, ana, monkeypatch):
    monkeypatch.setenv("EMAIL_IMAP_PASTA", "Arquivo")
    assert buscar(ana)["tipo_erro"] == "integracao_indisponivel"


def test_falha_simulada_nao_conecta(caixa, ana):
    ligar("email_leitura")
    assert buscar(ana)["tipo_erro"] == "integracao_indisponivel"
    assert caixa.comandos == []


def test_testar_conta_a_pasta_sem_ler_mensagem(caixa):
    linhas = []
    principal(["testar", "email_leitura"], ambiente={**os.environ, "MODO_TERMINAL": "1"}, escrever=linhas.append)
    assert "tem 4 mensagens" in linhas[0]
    assert not any(c.startswith("FETCH") for c in caixa.comandos)


# --- configuração, desligado e simulado ---------------------------------------------------------------------


def test_sem_host_fica_desligada_e_some_do_modelo(ana):
    assert EMAIL_LEITURA.modo() == "desligado"
    assert BUSCAR not in catalogo.ferramentas_liberadas(ana, AGENTE)


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("EMAIL_IMAP_SEGURANCA", "nenhuma"),  # sem criptografia fora do localhost
        ("EMAIL_IMAP_PORTA", "²"),
        ("EMAIL_IMAP_USUARIO", "joão@stonelab.example"),
        ("EMAIL_IMAP_PASTA", 'INBOX" DELETE "x'),
    ],
)
def test_configuracao_errada_some_do_modelo(ana, monkeypatch, variavel, valor):
    ambiente = {
        "EMAIL_IMAP_HOST": "imap.stonelab.example", "EMAIL_IMAP_USUARIO": "caixa@stonelab.example",
        "EMAIL_IMAP_SENHA": SENHA, variavel: valor,
    }
    for nome, item in ambiente.items():
        monkeypatch.setenv(nome, item)
    assert EMAIL_LEITURA.saude() == "configuracao_invalida"
    assert BUSCAR not in catalogo.ferramentas_liberadas(ana, AGENTE)


def test_modo_simulado_le_as_mensagens_do_mundo_simulado(engine, monkeypatch):
    monkeypatch.setenv("EMAIL_LEITURA_MODO", "simulado")
    ouvidoria = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["analista_ouvidoria"])
    dados = lido(catalogo.executar(BUSCAR, {"id_cliente": "M00007"}, ouvidoria, AGENTE))
    assert dados["fonte"] == FONTE_SIMULADA and dados["total"] == 1
    mensagem = dados["mensagens"][0]
    assert mensagem["texto"].startswith("Assunto: Chamado CH000066: ") and "****" not in mensagem["texto"]
    assert mensagem["data_hora"] == "2026-10-05T09:00-03:00"


def test_cobranca_nao_le_emails_de_lojista(engine, caixa):
    cobranca = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["analista_cobranca"])
    assert BUSCAR not in catalogo.ferramentas_liberadas(cobranca, AGENTE)


# --- partes puras -------------------------------------------------------------------------------------------


def test_data_e_remetentes_no_formato_do_imap():
    assert data_do_imap(date(2026, 10, 5)) == "05-Oct-2026"
    assert criterio_de_remetentes(["a@x.example"]) == ["FROM", '"a@x.example"']
    assert criterio_de_remetentes(["a@x.example", "b@x.example", "c@x.example"]) == [
        "OR", "FROM", '"a@x.example"', "OR", "FROM", '"b@x.example"', "FROM", '"c@x.example"',
    ]
