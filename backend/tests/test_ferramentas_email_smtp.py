"""Envio de e-mail por SMTP (`ferramentas/email_smtp.py`), contra um servidor SMTP de verdade em socket local.

Prova o que chegou ao servidor (comandos e mensagem), não só o retorno: que a senha não vai sem TLS, que
nada segue sem o STARTTLS exigido, que quebra de linha não vira cabeçalho, que falha antes do envio diz
"nada foi enviado" e falha depois dele diz "pode ter saído", e que a fila de prévias não trava durante o envio.
"""

import json
import logging
import threading
import time
from email.message import EmailMessage

import pytest
from ferramentas import catalogo, confirmacoes, email_smtp, governanca
from ferramentas.base import EfeitoIncerto, ErroFerramenta
from mock.falhas import ligar

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_smtp import SENHA, USUARIO, ServidorSmtp, porta_fechada

ENVIAR = "enviar_email"
NADA_SAIU = confirmacoes.mensagem_nada_saiu(catalogo.carregar()[ENVIAR])
AGENTE = (ENVIAR,)
PEDIDO = {"id_cliente": "M00001", "assunto": "Liquidação de 14/10", "corpo": "Olá, a liquidação falhou. Ação: conferir."}
REMETENTE = "plataforma@stonelab.example"
PARA = "financeiro@padaria.example"
DESTINO_TESTE = "pedro@pessoal.example"


def ambiente(porta, **extra):
    base = {
        "EMAIL_SMTP_HOST": "127.0.0.1",
        "EMAIL_SMTP_PORTA": str(porta),
        "EMAIL_SMTP_SEGURANCA": "nenhuma",
        "EMAIL_REMETENTE": REMETENTE,
    }
    return {**base, **extra}


def config(porta, **extra):
    return email_smtp.configuracao(ambiente(porta, **extra))


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


def ligar_smtp(monkeypatch, porta, **extra):
    for nome, valor in ambiente(porta, **extra).items():
        monkeypatch.setenv(nome, valor)


def preparar_e_confirmar(usuario, argumentos=PEDIDO):
    previa = catalogo.executar(ENVIAR, argumentos, usuario, AGENTE)
    assert previa["status"] == "ok", previa
    return confirmacoes.confirmar(previa["dados"]["confirmacao_id"], usuario)


# --- configuração ---------------------------------------------------------------------------------


def test_sem_host_o_envio_fica_desligado_e_nem_a_previa_e_montada(ana, monkeypatch):
    assert email_smtp.configuracao({}) is None
    monkeypatch.setenv("EMAIL_SMTP_HOST", "")
    assert ENVIAR not in catalogo.ferramentas_liberadas(ana, AGENTE)  # o modelo nem vê a ferramenta
    resposta = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)
    aviso = "O envio de e-mail não está ligado nesta plataforma. Avise o usuário e não tente de novo."
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("ferramenta_inativa", aviso)
    assert "EMAIL_SMTP_HOST" not in resposta["mensagem"]  # o texto sobre o .env fica só no terminal
    assert confirmacoes.pendentes(ana) == []


def test_host_apagado_depois_da_previa_nao_envia(ana, monkeypatch):
    confirmacao_id = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]["confirmacao_id"]
    monkeypatch.setenv("EMAIL_SMTP_HOST", "")
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert (resultado["tipo_erro"], resultado["mensagem"]) == ("integracao_indisponivel", f"{email_smtp.MENSAGEM_DESLIGADO} {confirmacoes.MENSAGEM_PREVIA_CONTINUA}")


def test_porta_vazia_usa_a_padrao_de_cada_seguranca():
    base = {"EMAIL_SMTP_HOST": "smtp.exemplo.example", "EMAIL_REMETENTE": REMETENTE}
    assert email_smtp.configuracao(base).porta == 587
    assert email_smtp.configuracao({**base, "EMAIL_SMTP_SEGURANCA": "ssl"}).porta == 465
    assert email_smtp.configuracao({**base, "EMAIL_SMTP_SEGURANCA": "STARTTLS"}).seguranca == "starttls"


@pytest.mark.parametrize(
    ("variavel", "valores"),
    [
        ("EMAIL_SMTP_HOST", {"EMAIL_SMTP_HOST": "smtp://smtp.exemplo.example"}),
        ("EMAIL_SMTP_SEGURANCA", {"EMAIL_SMTP_SEGURANCA": "tls"}),
        ("EMAIL_SMTP_SEGURANCA", {"EMAIL_SMTP_HOST": "smtp.exemplo.example", "EMAIL_SMTP_SEGURANCA": "nenhuma"}),
        ("EMAIL_SMTP_PORTA", {"EMAIL_SMTP_PORTA": "abc"}),
        ("EMAIL_SMTP_PORTA", {"EMAIL_SMTP_PORTA": "70000"}),
        ("EMAIL_SMTP_PORTA", {"EMAIL_SMTP_PORTA": "²"}),  # isdigit aceita, int recusa
        ("EMAIL_SMTP_PORTA", {"EMAIL_SMTP_PORTA": "５８７"}),  # dígitos de largura cheia
        ("EMAIL_REMETENTE", {"EMAIL_REMETENTE": ""}),
        ("EMAIL_REMETENTE", {"EMAIL_REMETENTE": "a@b.example, c@d.example"}),
        ("EMAIL_SMTP_USUARIO e EMAIL_SMTP_SENHA", {"EMAIL_SMTP_USUARIO": USUARIO}),
        ("EMAIL_SMTP_USUARIO e EMAIL_SMTP_SENHA", {"EMAIL_SMTP_SENHA": SENHA}),
        ("EMAIL_SMTP_USUARIO", {"EMAIL_SMTP_USUARIO": "joão", "EMAIL_SMTP_SENHA": SENHA}),
        ("EMAIL_SMTP_SENHA", {"EMAIL_SMTP_USUARIO": USUARIO, "EMAIL_SMTP_SENHA": "maçã-de-teste"}),
        ("EMAIL_DESTINO_TESTE", {"EMAIL_DESTINO_TESTE": "eu@pessoal.example\nBcc: x@y.example"}),
    ],
)
def test_configuracao_errada_diz_a_variavel_e_nunca_o_valor(variavel, valores, caplog):
    with caplog.at_level(logging.WARNING), pytest.raises(email_smtp.ConfiguracaoInvalida) as erro:
        email_smtp.configuracao(ambiente(1025, **valores))
    assert str(erro.value) == f"{variavel} inválida no .env."
    for valor in filter(None, valores.values()):
        assert valor not in str(erro.value) and valor not in caplog.text


def test_sem_tls_so_no_localhost():
    assert email_smtp.configuracao(ambiente(1025, EMAIL_SMTP_HOST="localhost")).seguranca == "nenhuma"
    with pytest.raises(email_smtp.ConfiguracaoInvalida):
        email_smtp.configuracao(ambiente(1025, EMAIL_SMTP_HOST="smtp.gmail.com"))


def test_a_senha_nao_aparece_na_representacao_da_configuracao():
    lida = config(1025, EMAIL_SMTP_USUARIO=USUARIO, EMAIL_SMTP_SENHA=SENHA)
    assert lida.senha == SENHA
    assert SENHA not in repr(lida)


# --- envio, contra o servidor de teste ------------------------------------------------------------


def test_envia_texto_puro_do_remetente_fixo_ao_destinatario_do_cadastro():
    with ServidorSmtp() as servidor:
        id_mensagem = email_smtp.enviar(PARA, "Liquidação de 14/10", "Olá, ação: conferir.", config(servidor.porta))
    (recebida,) = servidor.mensagens
    assert id_mensagem.startswith("MSG-") and len(id_mensagem) == 16
    assert (recebida["From"], recebida["To"], recebida["Subject"]) == (f"Stone <{REMETENTE}>", PARA, "Liquidação de 14/10")
    assert recebida["Reply-To"] is None  # sem funcionário, ninguém além da plataforma
    assert recebida["Message-ID"] == f"<{id_mensagem.lower()}@stonelab.example>"
    assert recebida.get_content_type() == "text/plain"
    assert recebida.get_content().strip() == "Olá, ação: conferir."
    assert "AUTH" not in servidor.comandos  # sem usuário configurado, não há login


def test_quem_confirmou_aparece_no_nome_e_no_responder_para():
    funcionario = {"nome": "Ana Beatriz Souza", "email": "ana@stonesim.example"}
    with ServidorSmtp() as servidor:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta), funcionario)
    (recebida,) = servidor.mensagens
    assert recebida["From"] == f"Ana via Stone <{REMETENTE}>"
    assert recebida["Reply-To"] == "ana@stonesim.example" and recebida["To"] == PARA
    assert "Souza" not in recebida.as_string()  # só o primeiro nome


@pytest.mark.parametrize(
    "funcionario",
    [
        {"nome": "Ana\r\nBcc: espiao@fora.example", "email": "ana@stonesim.example"},
        {"nome": "Ana", "email": "ana@stonesim.example\r\nBcc: espiao@fora.example"},
        {"nome": "Ana", "email": "ana@a.example, espiao@fora.example"},
        {"nome": None, "email": None},
    ],
)
def test_nome_ou_email_estranho_do_funcionario_nao_vira_cabecalho(funcionario):
    with ServidorSmtp() as servidor:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta), funcionario)
    (recebida,) = servidor.mensagens
    assert "espiao@fora.example" not in str(recebida["Bcc"]) + str(recebida["Reply-To"])
    assert recebida["Bcc"] is None
    assert recebida["Reply-To"] in (None, "ana@stonesim.example")


def test_destino_de_teste_recebe_tudo_com_aviso_e_o_contato_original_mascarado():
    with ServidorSmtp() as servidor:
        email_smtp.enviar(PARA, "Assunto", "Corpo.", config(servidor.porta, EMAIL_DESTINO_TESTE=DESTINO_TESTE))
    (recebida,) = servidor.mensagens
    assert recebida["To"] == DESTINO_TESTE
    assert recebida["Subject"] == "[TESTE] Assunto"
    assert "f***@padaria.example" in recebida.get_content()
    assert PARA not in recebida.as_string()


def test_login_so_com_usuario_e_senha_certos():
    with ServidorSmtp() as servidor:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta, EMAIL_SMTP_USUARIO=USUARIO, EMAIL_SMTP_SENHA=SENHA))
    assert servidor.comandos.count("AUTH") == 1 and len(servidor.mensagens) == 1
    with ServidorSmtp() as servidor, pytest.raises(email_smtp.EnvioIndisponivel) as erro:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta, EMAIL_SMTP_USUARIO=USUARIO, EMAIL_SMTP_SENHA="errada"))
    assert erro.value.etapa == "conexao"
    assert "MAIL" not in servidor.comandos and servidor.mensagens == []


def test_starttls_exigido_e_servidor_sem_ele_nada_segue_nem_a_senha():
    """Sem volta para texto puro: o cliente para antes do login e antes de mandar qualquer coisa."""
    exigindo_tls = {"EMAIL_SMTP_SEGURANCA": "starttls", "EMAIL_SMTP_USUARIO": USUARIO, "EMAIL_SMTP_SENHA": SENHA}
    with ServidorSmtp() as servidor, pytest.raises(email_smtp.EnvioIndisponivel) as erro:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta, **exigindo_tls))
    assert erro.value.etapa == "conexao"
    assert {"AUTH", "MAIL", "DATA"}.isdisjoint(servidor.comandos)


def test_destinatario_recusado_quer_dizer_que_nada_saiu():
    with ServidorSmtp(modo="recusar_destino") as servidor, pytest.raises(email_smtp.EnvioIndisponivel) as erro:
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta))
    assert erro.value.etapa == "recusa" and servidor.mensagens == []
    assert isinstance(erro.value, ConnectionError)


def test_conexao_que_cai_depois_do_texto_vira_envio_incerto():
    with ServidorSmtp(modo="cair_no_data") as servidor, pytest.raises(EfeitoIncerto):
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta))
    assert "DATA" in servidor.comandos


def test_servidor_que_demora_alem_do_limite_depois_do_texto_vira_envio_incerto(monkeypatch):
    monkeypatch.setattr(email_smtp, "TEMPO_LIMITE", 0.3)
    with ServidorSmtp(modo="lento_no_data", atraso=1.0) as servidor, pytest.raises(EfeitoIncerto):
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta))


def test_servidor_fora_do_ar_quer_dizer_que_nada_saiu():
    with pytest.raises(email_smtp.EnvioIndisponivel) as erro:
        email_smtp.enviar(PARA, "A", "B", config(porta_fechada()))
    assert erro.value.etapa == "conexao"


@pytest.mark.parametrize(
    "para",
    ["a@x.example, b@y.example", "a@x.example\r\nBcc: b@y.example", "sem-arroba", "", None],
)
def test_destinatario_que_nao_e_um_endereco_so_nao_conecta(para):
    with ServidorSmtp() as servidor, pytest.raises(ErroFerramenta) as erro:
        email_smtp.enviar(para, "A", "B", config(servidor.porta))
    assert erro.value.tipo_erro == "nao_encontrado"
    assert servidor.comandos == []


def test_quebra_de_linha_no_assunto_nao_vira_cabecalho():
    with ServidorSmtp() as servidor, pytest.raises(ErroFerramenta) as erro:
        email_smtp.enviar(PARA, "Oi\r\nBcc: espiao@fora.example", "B", config(servidor.porta))
    assert erro.value.tipo_erro == "parametro_invalido"
    assert servidor.comandos == []


def test_falha_simulada_do_mock_vale_tambem_para_o_smtp():
    ligar("email")
    with ServidorSmtp() as servidor, pytest.raises(ConnectionError):
        email_smtp.enviar(PARA, "A", "B", config(servidor.porta))
    assert servidor.comandos == []


def test_logs_das_falhas_levam_so_etapa_e_tipo(caplog, monkeypatch):
    monkeypatch.setattr(email_smtp, "TEMPO_LIMITE", 0.3)
    extra = {"EMAIL_SMTP_USUARIO": USUARIO, "EMAIL_SMTP_SENHA": "errada"}
    with caplog.at_level(logging.DEBUG):
        for modo, credenciais in (("", extra), ("recusar_destino", {}), ("cair_no_data", {})):
            with ServidorSmtp(modo=modo) as servidor, pytest.raises((ConnectionError, EfeitoIncerto)):
                email_smtp.enviar(PARA, "Assunto secreto", "Corpo secreto", config(servidor.porta, **credenciais))
    assert caplog.text
    for proibido in ("127.0.0.1", USUARIO, "errada", PARA, REMETENTE, "secreto"):
        assert proibido not in caplog.text


# --- o enviar_email com o SMTP ligado ------------------------------------------------------------


def test_o_agente_nunca_ve_o_email_do_funcionario(ana):
    previa = json.dumps(catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE), default=str)
    assert "stonesim.example" not in previa


def test_diretorio_fora_do_ar_na_hora_do_envio_quer_dizer_que_nada_saiu(ana, monkeypatch):
    with ServidorSmtp() as servidor:
        ligar_smtp(monkeypatch, servidor.porta)
        confirmacao_id = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]["confirmacao_id"]
        ligar("diretorio")
        resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["status"] == "erro" and servidor.mensagens == []


def test_fase_1_recusa_assunto_com_quebra_de_linha(ana):
    resposta = catalogo.executar(ENVIAR, {**PEDIDO, "assunto": "Oi\nBcc: x@fora.example"}, ana, AGENTE)
    assert resposta["tipo_erro"] == "parametro_invalido"
    assert confirmacoes.pendentes(ana) == []


def test_confirmar_envia_por_smtp(ana, monkeypatch):
    with ServidorSmtp() as servidor:
        ligar_smtp(monkeypatch, servidor.porta)
        resultado = preparar_e_confirmar(ana)
    assert resultado["status"] == "ok", resultado
    (recebida,) = servidor.mensagens
    assert recebida["Subject"] == PEDIDO["assunto"] and recebida["To"].endswith("@lojistas.example")
    assert recebida["Reply-To"].endswith("@stonesim.example") and " via Stone <" in recebida["From"]
    assert resultado["dados"]["id_mensagem"].startswith("MSG-")
    registro = json.dumps(governanca.REGISTROS, default=str)
    for conteudo in (recebida["To"], recebida["Reply-To"], PEDIDO["assunto"], PEDIDO["corpo"]):
        assert conteudo not in registro


def test_envio_incerto_nao_diz_que_nada_saiu_e_a_previa_nao_volta(ana, monkeypatch):
    with ServidorSmtp(modo="cair_no_data") as servidor:
        ligar_smtp(monkeypatch, servidor.porta)
        previa = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]
        resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
        de_novo = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["mensagem"] == confirmacoes.MENSAGEM_EFEITO_INCERTO
    assert "Nada foi enviado" not in resultado["mensagem"]
    assert de_novo["tipo_erro"] == "nao_encontrado"  # uso único: ninguém reenvia sem querer


def test_servidor_fora_ou_configuracao_errada_dizem_que_nada_saiu(ana, monkeypatch):
    ligar_smtp(monkeypatch, porta_fechada())
    assert preparar_e_confirmar(ana)["mensagem"] == NADA_SAIU
    confirmacao_id = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]["confirmacao_id"]
    monkeypatch.setenv("EMAIL_SMTP_PORTA", "abc")
    assert confirmacoes.confirmar(confirmacao_id, ana)["mensagem"] == NADA_SAIU


def test_fila_de_previas_nao_fica_travada_enquanto_o_smtp_demora(ana, monkeypatch):
    with ServidorSmtp(modo="lento_no_data", atraso=0.8) as servidor:
        ligar_smtp(monkeypatch, servidor.porta)
        primeira = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]["confirmacao_id"]
        segunda = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)["dados"]["confirmacao_id"]
        envio = threading.Thread(target=confirmacoes.confirmar, args=(primeira, ana))
        envio.start()
        time.sleep(0.2)  # o envio está esperando o servidor
        inicio = time.monotonic()
        restantes = [p["confirmacao_id"] for p in confirmacoes.pendentes(ana)]
        cancelada = confirmacoes.cancelar(segunda, ana)
        demora = time.monotonic() - inicio
        envio.join()
    assert envio.is_alive() is False and len(servidor.mensagens) == 1
    assert restantes == [segunda] and cancelada["status"] == "ok"
    assert demora < 0.5


# --- teste manual pelo terminal ------------------------------------------------------------------


def test_teste_manual_exige_o_modo_terminal_e_manda_ao_endereco_dado():
    saida = []
    with ServidorSmtp() as servidor:
        with pytest.raises(SystemExit, match="MODO_TERMINAL"):
            email_smtp.principal(["--testar", DESTINO_TESTE], ambiente(servidor.porta), saida.append)
        email_smtp.principal(
            ["--testar", DESTINO_TESTE],
            ambiente(servidor.porta, MODO_TERMINAL="1", EMAIL_DESTINO_TESTE="outro@pessoal.example"),
            saida.append,
        )
    (recebida,) = servidor.mensagens
    assert recebida["To"] == DESTINO_TESTE and recebida["Subject"] == email_smtp.ASSUNTO_DO_TESTE_MANUAL
    assert saida and saida[0].startswith("Enviado (MSG-")


def test_teste_manual_explica_a_falha_sem_detalhe_tecnico():
    with pytest.raises(SystemExit) as erro:
        email_smtp.principal(["--testar", DESTINO_TESTE], ambiente(porta_fechada(), MODO_TERMINAL="1"))
    assert str(erro.value).startswith("Não enviou: falha na etapa conexao")


# --- revisão do Enrico no #20 -----------------------------------------------------------------------------

ENDERECO_COM_ACENTO = "joão@loja.example"
# O que o EmailMessage recusa em cabeçalho: tudo que o str.splitlines quebra. Fora do ASCII: \x85, \u2028, \u2029.
QUEBRAS_DE_LINHA = [chr(c) for c in range(0x110000) if len(f"a{chr(c)}b".splitlines()) > 1]
METADE_DE_PAR = "\ud800"  # um JSON do modelo pode trazer; não vira UTF-8


def test_endereco_com_acento_em_servidor_sem_smtputf8_quer_dizer_que_nada_saiu():
    with ServidorSmtp() as servidor, pytest.raises(email_smtp.EnvioIndisponivel) as erro:
        email_smtp.enviar(ENDERECO_COM_ACENTO, "A", "B", config(servidor.porta))
    assert erro.value.etapa == "suporte" and isinstance(erro.value, ConnectionError)
    assert "MAIL" not in servidor.comandos and servidor.mensagens == []


def test_confirmar_com_endereco_com_acento_diz_que_nada_foi_enviado(ana, monkeypatch):
    with ServidorSmtp() as servidor:
        ligar_smtp(monkeypatch, servidor.porta, EMAIL_DESTINO_TESTE=ENDERECO_COM_ACENTO)
        resultado = preparar_e_confirmar(ana)
    assert resultado["mensagem"] == NADA_SAIU
    assert servidor.mensagens == []


def test_a_regra_do_assunto_cobre_tudo_que_o_email_message_recusa():
    assert {"\n", "\r", "\x0b", "\x85", "\u2028", "\u2029"} <= set(QUEBRAS_DE_LINHA)
    for quebra in QUEBRAS_DE_LINHA:
        with pytest.raises(ValueError):
            EmailMessage()["Subject"] = f"a{quebra}b"
        assert not email_smtp.assunto_valido(f"a{quebra}b"), repr(quebra)


@pytest.mark.parametrize("assunto", ["Liquidação de 14/10", "Ação ✅ conferida", "Prazo\u00a0curto"])
def test_assunto_comum_continua_valendo(assunto):
    assert email_smtp.assunto_valido(assunto)


@pytest.mark.parametrize("caractere", ["\x85", "\u2028", "\u2029", METADE_DE_PAR])
def test_previa_recusa_o_assunto_que_o_envio_recusaria(ana, caractere):
    resposta = catalogo.executar(ENVIAR, {**PEDIDO, "assunto": f"Oi{caractere}Bcc: x@fora.example"}, ana, AGENTE)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("parametro_invalido", email_smtp.MENSAGEM_ASSUNTO_INVALIDO)
    assert confirmacoes.pendentes(ana) == []
    with ServidorSmtp() as servidor, pytest.raises(ErroFerramenta):
        email_smtp.enviar(PARA, f"Oi{caractere}x", "B", config(servidor.porta))
    assert servidor.comandos == []


def test_previa_recusa_o_corpo_que_o_envio_nao_conseguiria_codificar(ana):
    resposta = catalogo.executar(ENVIAR, {**PEDIDO, "corpo": f"Olá{METADE_DE_PAR}"}, ana, AGENTE)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("parametro_invalido", email_smtp.MENSAGEM_CORPO_INVALIDO)
    assert confirmacoes.pendentes(ana) == []
    with ServidorSmtp() as servidor, pytest.raises(ErroFerramenta):
        email_smtp.enviar(PARA, "A", f"Olá{METADE_DE_PAR}", config(servidor.porta))
    assert servidor.comandos == []


@pytest.mark.parametrize(
    "valores",
    [
        {"EMAIL_SMTP_PORTA": "²"},
        {"EMAIL_SMTP_USUARIO": "joão", "EMAIL_SMTP_SENHA": SENHA},
        {"EMAIL_SMTP_USUARIO": USUARIO, "EMAIL_SMTP_SENHA": "maçã-de-teste"},
    ],
)
def test_porta_ou_login_estranho_no_env_nao_vira_erro_interno(ana, monkeypatch, valores):
    ligar_smtp(monkeypatch, 1025, **valores)
    resposta = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE)
    # Mal configurada conta como desligada: o modelo ouve o aviso, sem "Erro interno" e sem falar do .env.
    assert resposta["tipo_erro"] == "ferramenta_inativa" and confirmacoes.pendentes(ana) == []
    assert ".env" not in resposta["mensagem"]
    with pytest.raises(SystemExit) as erro:
        email_smtp.principal(["--testar", DESTINO_TESTE], ambiente(1025, MODO_TERMINAL="1", **valores))
    assert str(erro.value).endswith("inválida no .env.")
