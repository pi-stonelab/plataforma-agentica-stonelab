"""Base das integrações: disjuntor, conector, cliente HTTP, estado e o comando do terminal.

O cliente HTTP é testado contra um servidor HTTP de verdade em 127.0.0.1 (`apoio_http.py`): redirecionamento,
tamanho, JSON quebrado, 429, 500 e tempo esgotado são respostas reais na rede local.
"""

import json
import logging
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from ferramentas import catalogo, integracoes
from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http as http
from ferramentas.integracoes.__main__ import CABECALHO, principal
from ferramentas.integracoes.conector import (
    CREDENCIAIS,
    FALHAS_PARA_PAUSAR,
    SAUDES,
    SEGUNDOS_DE_FALHA_RECENTE,
    SEGUNDOS_DE_PAUSA,
    Conector,
    ConfiguracaoInvalida,
    DestinoNaoPermitido,
    Disjuntor,
    IntegracaoDesligada,
    IntegracaoPausada,
)
from ferramentas.integracoes.registro import CONECTORES
from mock.falhas import desligar_todas, ligar

from .apoio_http import JSON, ServidorHttp

SEGREDO = "segredo-que-nunca-aparece-123"


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


@pytest.fixture(autouse=True)
def estado_limpo():
    integracoes.reiniciar()
    desligar_todas()
    yield
    integracoes.reiniciar()
    desligar_todas()


def falhar():
    raise ConnectionError("caiu")


def falhar_com_segredo():
    raise ConnectionError(f"https://usuario:{SEGREDO}@servico.example/x?token={SEGREDO}")


# --- disjuntor ------------------------------------------------------------------------------------


def test_disjuntor_pausa_depois_de_tres_falhas_seguidas_e_nao_chama_durante_a_pausa():
    relogio = Relogio()
    conector = Conector(relogio)
    chamadas = []
    for _ in range(FALHAS_PARA_PAUSAR):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", lambda: chamadas.append(1) or falhar())
    with pytest.raises(IntegracaoPausada):
        conector.chamar("teste", lambda: chamadas.append(1))
    assert len(chamadas) == FALHAS_PARA_PAUSAR
    assert isinstance(IntegracaoPausada(), ConnectionError)  # a ferramenta responde integracao_indisponivel


def test_disjuntor_sucesso_zera_a_contagem():
    conector = Conector(Relogio())
    for _ in range(FALHAS_PARA_PAUSAR - 1):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", falhar)
    assert conector.chamar("teste", lambda: "ok") == "ok"
    for _ in range(FALHAS_PARA_PAUSAR - 1):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", falhar)
    assert conector.chamar("teste", lambda: "ok") == "ok"


def test_depois_da_pausa_uma_chamada_testa_e_volta_ao_normal():
    relogio = Relogio()
    conector = Conector(relogio)
    for _ in range(FALHAS_PARA_PAUSAR):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", falhar)
    relogio.agora += SEGUNDOS_DE_PAUSA
    assert conector.chamar("teste", lambda: "voltou") == "voltou"
    assert conector.chamar("teste", lambda: "normal") == "normal"


def test_depois_da_pausa_a_chamada_de_teste_que_falha_pausa_de_novo():
    relogio = Relogio()
    conector = Conector(relogio)
    for _ in range(FALHAS_PARA_PAUSAR):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", falhar)
    relogio.agora += SEGUNDOS_DE_PAUSA
    with pytest.raises(ConnectionError):
        conector.chamar("teste", falhar)
    with pytest.raises(IntegracaoPausada):
        conector.chamar("teste", lambda: "não roda")
    relogio.agora += SEGUNDOS_DE_PAUSA - 1
    with pytest.raises(IntegracaoPausada):
        conector.chamar("teste", lambda: "não roda")


def test_so_uma_chamada_de_teste_por_vez_depois_da_pausa():
    relogio = Relogio()
    disjuntor = Disjuntor(relogio)
    for _ in range(FALHAS_PARA_PAUSAR):
        disjuntor.falha()
    relogio.agora += SEGUNDOS_DE_PAUSA
    liberadas, recusadas = [], []
    barreira = threading.Barrier(8)

    def tentar():
        barreira.wait()
        try:
            disjuntor.liberar()
            liberadas.append(1)
        except IntegracaoPausada:
            recusadas.append(1)

    linhas = [threading.Thread(target=tentar) for _ in range(8)]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()
    assert (len(liberadas), len(recusadas)) == (1, 7)


def test_erro_do_nosso_lado_nao_conta_como_falha_da_integracao():
    conector = Conector(Relogio())
    for _ in range(FALHAS_PARA_PAUSAR + 2):
        with pytest.raises(KeyError):
            conector.chamar("teste", lambda: {}["x"])
    assert conector.chamar("teste", lambda: "ok") == "ok"


def test_um_servico_fora_do_ar_nao_pausa_o_outro():
    conector = integracoes.conector("apis_publicas")
    for _ in range(FALHAS_PARA_PAUSAR):
        with pytest.raises(ConnectionError):
            conector.chamar("teste", falhar, servico="viacep")
    with pytest.raises(IntegracaoPausada):
        conector.chamar("teste", lambda: "x", servico="viacep")
    assert conector.chamar("teste", lambda: "ptax responde", servico="ptax") == "ptax responde"


def test_log_da_falha_leva_so_integracao_servico_etapa_e_tipo(caplog):
    caplog.set_level(logging.DEBUG)
    conector = integracoes.conector("apis_publicas")
    for _ in range(FALHAS_PARA_PAUSAR):
        with pytest.raises(ConnectionError):
            conector.chamar("consultar_cep", falhar_com_segredo, servico="viacep")
    texto = caplog.text
    assert SEGREDO not in texto
    assert "integracao=apis_publicas servico=viacep etapa=consultar_cep tipo=ConnectionError" in texto
    assert "integracao pausada: integracao=apis_publicas servico=viacep segundos=60" in texto


# --- modo, configuração e saúde --------------------------------------------------------------------


class _ComModo(Conector):
    nome = "exemplo"
    variavel_modo = "EXEMPLO_MODO"


@pytest.mark.parametrize(
    ("valor", "modo"),
    [("", "real"), ("real", "real"), (" Simulado ", "simulado"), ("desligado", "desligado"), ("talvez", "desligado")],
)
def test_modo_vem_do_env_e_valor_estranho_desliga(valor, modo):
    assert _ComModo().modo({"EXEMPLO_MODO": valor}) == modo


def test_saude_reflete_desligado_falha_simulada_pausa_e_ok():
    crm = integracoes.conector("crm")
    assert crm.saude() == "ok"
    ligar("crm")
    assert crm.saude() == "indisponivel"
    desligar_todas()
    apis = integracoes.conector("apis_publicas")
    assert apis.saude({"APIS_PUBLICAS_MODO": "desligado"}) == "desligada"
    assert apis.saude({"VIACEP_URL": "http://fora.example"}) == "configuracao_invalida"
    with pytest.raises(ConnectionError):
        apis.chamar("teste", falhar, servico="ptax")
    assert apis.saude() == "indisponivel"
    for _ in range(FALHAS_PARA_PAUSAR - 1):
        with pytest.raises(ConnectionError):
            apis.chamar("teste", falhar, servico="ptax")
    assert apis.saude() == "pausada"


def test_exigir_ligado_recusa_desligado_e_mal_configurado():
    apis = integracoes.conector("apis_publicas")
    with pytest.raises(IntegracaoDesligada):
        apis.exigir_ligado({"APIS_PUBLICAS_MODO": "desligado"})
    with pytest.raises(ConfiguracaoInvalida) as erro:
        apis.exigir_ligado({"BCB_PTAX_URL": "ftp://olinda.example"})
    assert str(erro.value) == "BCB_PTAX_URL inválida no .env."
    assert apis.exigir_ligado({"APIS_PUBLICAS_MODO": "simulado", "VIACEP_URL": "lixo"}) == "simulado"


# --- cliente HTTP, contra um servidor de verdade em 127.0.0.1 ------------------------------------------


def _respostas(metodo, caminho):
    if caminho == "/ok":
        return 200, JSON, b'{"ok": true}'
    if caminho == "/vazio":
        return 204, {}, b""
    if caminho == "/grande":
        return 200, JSON, b'{"x": "' + b"a" * (http.LIMITE_DE_BYTES + 10) + b'"}'
    if caminho == "/quebrado":
        return 200, JSON, b'{"ok": tru'
    if caminho == "/muitos":
        return 429, JSON, b'{"erro": "limite"}'
    if caminho == "/caiu":
        return 500, JSON, b'{"erro": "interno"}'
    if caminho == "/nao-tem":
        return 404, {"Content-Type": "text/html"}, b"<h1>404</h1>"
    if caminho == "/mesma-origem":
        return 302, {"Location": "/ok"}, b""
    if caminho == "/outra-origem":
        return 302, {"Location": caminho_em_outro_host["url"]}, b""
    if caminho == "/em-circulo":
        return 302, {"Location": "/em-circulo"}, b""
    return 404, JSON, b"{}"


caminho_em_outro_host = {"url": ""}


@pytest.fixture(scope="module")
def servidor():
    with ServidorHttp(_respostas) as rodando:
        caminho_em_outro_host["url"] = f"http://localhost:{rodando.porta}/ok"  # outro host, mesma máquina
        yield rodando


def test_http_devolve_o_json_e_o_status(servidor):
    assert http.pedir("GET", servidor.url + "/ok") == http.RespostaHttp(200, {"ok": True})
    assert http.pedir("GET", servidor.url + "/vazio") == http.RespostaHttp(204, None)


def test_http_404_volta_para_quem_chamou_sem_exigir_json(servidor):
    assert http.pedir("GET", servidor.url + "/nao-tem") == http.RespostaHttp(404, None)


@pytest.mark.parametrize(
    ("caminho", "erro"),
    [
        ("/grande", http.RespostaInvalida),
        ("/quebrado", http.RespostaInvalida),
        ("/muitos", http.LimiteDePedidos),
        ("/caiu", ConnectionError),
        ("/outra-origem", ConnectionError),
        ("/em-circulo", ConnectionError),
    ],
)
def test_http_resposta_que_nao_serve_vira_falha_de_integracao(servidor, caminho, erro):
    with pytest.raises(erro) as levantado:
        http.pedir("GET", servidor.url + caminho)
    assert isinstance(levantado.value, ConnectionError)
    assert "127.0.0.1" not in str(levantado.value) and caminho not in str(levantado.value)


def test_http_segue_redirecionamento_da_mesma_origem(servidor):
    antes = len(servidor.pedidos)
    assert http.pedir("GET", servidor.url + "/mesma-origem").dados == {"ok": True}
    assert servidor.pedidos[antes:] == [("GET", "/mesma-origem"), ("GET", "/ok")]


def test_http_redirecionamento_para_outro_host_nao_e_seguido(servidor):
    antes = len(servidor.pedidos)
    with pytest.raises(ConnectionError):
        http.pedir("GET", servidor.url + "/outra-origem")
    assert servidor.pedidos[antes:] == [("GET", "/outra-origem")]


def test_http_tempo_esgotado_vira_timeout():
    with ServidorHttp(_respostas, atraso=1.0) as lento, pytest.raises(TimeoutError):
        http.pedir("GET", lento.url + "/ok", tempo_limite=0.2)


def test_http_porta_fechada_vira_falha_de_conexao():
    with ServidorHttp(_respostas) as rodando:
        url = rodando.url
    with pytest.raises(ConnectionError):
        http.pedir("GET", url + "/ok", tempo_limite=1)


@pytest.mark.parametrize(
    "url",
    ["http://viacep.com.br/ws", "ftp://127.0.0.1/x", "file:///etc/passwd", "//127.0.0.1/x", "https:///sem-host"],
)
def test_http_recusa_sem_https_fora_do_localhost_antes_de_conectar(url):
    with pytest.raises(ConnectionError):
        http.pedir("GET", url)


@pytest.mark.parametrize(
    "valor",
    [
        "http://viacep.com.br",
        "https://usuario:senha@viacep.com.br",
        "https://viacep.com.br/?token=x",
        "https://viacep.com.br/#x",
        "https://viacep.com.br:99999",
        "viacep.com.br",
        "",
    ],
)
def test_url_base_do_env_recusa_o_que_nao_e_https_simples(valor):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        http.url_base(valor, "VIACEP_URL")
    assert str(erro.value) == "VIACEP_URL inválida no .env."
    assert "senha" not in str(erro.value)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("https://viacep.com.br/", "https://viacep.com.br"),
        (" https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata ", "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("http://localhost:8080/base", "http://localhost:8080/base"),
    ],
)
def test_url_base_do_env_aceita_https_e_http_so_no_localhost(valor, esperado):
    assert http.url_base(valor, "VIACEP_URL") == esperado


# --- registro e estado -------------------------------------------------------------------------------


def test_toda_integracao_das_fichas_tem_conector_e_todo_conector_tem_ferramenta():
    usadas = {nome for f in catalogo.carregar().values() for nome in f.integracoes}
    assert usadas == set(CONECTORES)


def test_estado_tem_os_campos_combinados_internas_primeiro():
    estado = integracoes.estado_integracoes()
    assert [set(item) for item in estado] == [
        {"nome", "rotulo", "tipo", "credencial", "modo", "configurado", "saude", "servicos", "ferramentas"}
    ] * len(estado)
    tipos = [item["tipo"] for item in estado]
    assert tipos == sorted(tipos, key=lambda t: t != "interno")
    por_nome = {item["nome"]: item for item in estado}
    assert por_nome["apis_publicas"]["ferramentas"] == ["consultar_cotacao_moeda", "consultar_endereco_cep"]
    assert por_nome["email"]["ferramentas"] == ["enviar_email"]
    assert por_nome["crm"]["modo"] == "simulado" and por_nome["crm"]["tipo"] == "interno"
    assert por_nome["jira"]["saude"] == "desligada"
    assert por_nome["apis_publicas"]["servicos"] == [
        {"nome": "viacep", "saude": "sem_chamadas"},
        {"nome": "ptax", "saude": "sem_chamadas"},
    ]
    assert all(item["saude"] in SAUDES and item["credencial"] in CREDENCIAIS for item in estado)
    json.dumps(estado)  # só texto, número e lista


def test_estado_nunca_mostra_valor_do_env():
    ambiente = {
        "EMAIL_SMTP_HOST": "smtp.segredo.example",
        "EMAIL_SMTP_USUARIO": SEGREDO,
        "EMAIL_SMTP_SENHA": SEGREDO,
        "EMAIL_REMETENTE": "plataforma@stonelab.example",
        "VIACEP_URL": f"https://{SEGREDO}.example",
        "BCB_PTAX_URL": "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata",
    }
    texto = json.dumps(integracoes.estado_integracoes(ambiente))
    assert SEGREDO not in texto and "smtp.segredo" not in texto


def test_email_sem_host_esta_desligado_e_com_host_esta_configurado():
    email = integracoes.conector("email")
    assert (email.modo({}), email.configurado({}), email.saude({})) == ("desligado", False, "desligada")
    ambiente = {"EMAIL_SMTP_HOST": "smtp.example.test", "EMAIL_REMETENTE": "plataforma@stonelab.example"}
    assert (email.modo(ambiente), email.configurado(ambiente), email.saude(ambiente)) == ("real", True, "sem_chamadas")
    ligar("email")
    assert email.saude(ambiente) == "indisponivel"


# --- terminal --------------------------------------------------------------------------------------


def test_comando_estado_lista_todas_as_integracoes():
    linhas = []
    principal(["estado"], escrever=linhas.append)
    assert linhas[0] == CABECALHO
    for nome in CONECTORES:
        assert any(linha.startswith(nome + " ") for linha in linhas), nome
    apis = next(linha for linha in linhas if linha.startswith("apis_publicas"))
    assert apis.endswith("sem chamadas ainda")
    assert any("- viacep" in linha for linha in linhas) and any("- ptax" in linha for linha in linhas)
    assert any("Ainda não implementada" in linha for linha in linhas)  # jira, slack...


def test_comando_testar_exige_modo_terminal_e_chama_o_servico():
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "apis_publicas"], ambiente={})
    assert "MODO_TERMINAL" in str(erro.value)
    linhas = []
    principal(["testar", "apis_publicas"], ambiente={**os.environ, "MODO_TERMINAL": "1"}, escrever=linhas.append)
    assert linhas == ["APIs públicas (CEP e câmbio) (modo real): ViaCEP e PTAX responderam (7 moedas no Banco Central)."]


def test_comando_testar_explica_a_falha_sem_detalhe():
    with ServidorHttp(_respostas) as rodando:
        url = rodando.url
    ambiente = {"MODO_TERMINAL": "1", "VIACEP_URL": url, "BCB_PTAX_URL": url}
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "apis_publicas"], ambiente=ambiente)
    assert str(erro.value) == (
        "Não consegui falar com APIs públicas (CEP e câmbio). Confira a internet ou use APIS_PUBLICAS_MODO=simulado."
    )
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "email"], ambiente={"MODO_TERMINAL": "1"})
    assert "EMAIL_SMTP_HOST" in str(erro.value)
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "jira"], ambiente={"MODO_TERMINAL": "1"})
    assert str(erro.value).startswith("Jira:")


def test_comando_testar_diz_como_corrigir_a_configuracao():
    ambiente = {"MODO_TERMINAL": "1", "VIACEP_URL": "http://fora.example"}
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "apis_publicas"], ambiente=ambiente)
    assert str(erro.value).endswith("VIACEP_URL inválida: use https:// e só o endereço base, sem ? nem #. Vazia usa a oficial.")
    with pytest.raises(SystemExit) as erro:
        principal(["testar", "apis_publicas"], ambiente={"MODO_TERMINAL": "1", "APIS_PUBLICAS_MODO": "simulada"})
    assert "APIS_PUBLICAS_MODO com um valor que não existe. Use real, simulado ou desligado." in str(erro.value)
    assert "fora.example" not in str(erro.value)


def test_modo_invalido_avisa_uma_vez_so(caplog):
    conector = integracoes.conector("apis_publicas")
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            assert conector.modo({"APIS_PUBLICAS_MODO": "simulada"}) == "desligado"
    assert sum("modo de integracao invalido" in r.getMessage() for r in caplog.records) <= 1


# --- saúde por serviço e falha recente ---------------------------------------------------------------


class _DoisServicos(Conector):
    nome = "teste"
    rotulo = "Teste"
    servicos = ("a", "b")


def test_saude_por_servico_e_a_pior_vale_para_o_conector():
    conector = _DoisServicos(Relogio())
    assert conector.saude_por_servico({}) == {"a": "sem_chamadas", "b": "sem_chamadas"}
    conector.chamar("teste", lambda: None, servico="a")
    with pytest.raises(ConnectionError):
        conector.chamar("teste", falhar, servico="b")
    assert conector.saude_por_servico({}) == {"a": "ok", "b": "indisponivel"}
    assert conector.saude({}) == "indisponivel"
    assert list(SAUDES) == sorted(SAUDES, key=SAUDES.index)  # da pior para a melhor


def test_falha_antiga_sem_chamada_depois_nao_acusa_mais():
    relogio = Relogio()
    conector = Conector(relogio)
    with pytest.raises(ConnectionError):
        conector.chamar("teste", falhar)
    assert conector.saude({}) == "indisponivel"
    relogio.agora += SEGUNDOS_DE_FALHA_RECENTE
    assert conector.saude({}) == "ok"  # o alerta não fica ligado horas por uma falha só


# --- destino permitido e URL montada (base do bloco E) -------------------------------------------------


def test_destino_so_dentro_da_lista_permitida():
    conector = Conector()
    assert conector.exigir_destino(" #financeiro ", ["#financeiro", "#atendimento"]) == "#financeiro"
    for pedido in ("#outro", "", None, 42, "#financeiro;#outro"):
        with pytest.raises(DestinoNaoPermitido):
            conector.exigir_destino(pedido, ["#financeiro", " "])
    with pytest.raises(DestinoNaoPermitido):
        conector.exigir_destino("#financeiro", [])


@pytest.mark.parametrize("segmento", ["../admin", "a/b", "x?token=1", "x#frag", "%2e%2e", "ç"])
def test_montar_url_codifica_cada_pedaco_e_nao_sai_da_base(segmento):
    url = http.montar_url("https://servico.example/api/v1", "issue", segmento)
    assert url.startswith("https://servico.example/api/v1/issue/")
    resto = url.removeprefix("https://servico.example/api/v1/issue/")
    assert "/" not in resto and "?" not in resto and "#" not in resto


@pytest.mark.parametrize("segmento", ["", ".", ".."])
def test_montar_url_recusa_segmento_que_sobe_ou_some(segmento):
    with pytest.raises(ValueError):
        http.montar_url("https://servico.example/api", segmento)


def test_todo_conector_declara_credencial_e_suas_variaveis_estao_no_env_example():
    exemplo = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    for nome, conector in CONECTORES.items():
        assert conector.credencial in CREDENCIAIS, nome
        for variavel in conector.variaveis:
            assert f"{variavel}=" in exemplo, (nome, variavel)


def test_aviso_de_integracao_desligada_nao_fala_do_env():
    for nome, conector in CONECTORES.items():
        aviso = conector.aviso_desligada()
        assert aviso.endswith("Avise o usuário e não tente de novo."), nome
        assert ".env" not in aviso and "_" not in aviso.split(".")[0], nome


# --- cliente HTTP: log, escrita incerta, 4xx e prazo total --------------------------------------------


def test_httpx_nao_escreve_a_url_no_log(servidor, caplog):
    with caplog.at_level(logging.DEBUG):
        http.pedir("GET", servidor.url + f"/bot{SEGREDO}/ok", parametros={"chat_id": SEGREDO})
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert SEGREDO not in caplog.text


def _respostas_de_escrita(metodo, caminho):
    status = {"/recusado": 400, "/sem-credencial": 401, "/proibido": 403, "/caiu": 500, "/gateway": 502}
    return status.get(caminho, 201), JSON, b'{"ok": true}'


def test_escrita_que_chegou_e_ficou_sem_resposta_pode_ter_saido():
    with ServidorHttp(_respostas_de_escrita, atraso=1.0) as lento:
        with pytest.raises(EfeitoIncerto):
            http.pedir("POST", lento.url + "/mensagem", corpo={"texto": "oi"}, tempo_limite=0.3)
        assert lento.pedidos == [("POST", "/mensagem")]  # o servidor recebeu
    with ServidorHttp(_respostas_de_escrita, atraso=1.0) as lento, pytest.raises(TimeoutError):
        http.pedir("GET", lento.url + "/mensagem", tempo_limite=0.3)  # leitura: só tempo esgotado


def test_escrita_que_nem_conectou_e_nada_saiu():
    with ServidorHttp(_respostas_de_escrita) as rodando:
        url = rodando.url
    with pytest.raises(ConnectionError) as erro:
        http.pedir("POST", url + "/mensagem", corpo={}, tempo_limite=1)
    assert not isinstance(erro.value, EfeitoIncerto)


@pytest.mark.parametrize(("caminho", "escrita", "leitura"), [
    ("/caiu", EfeitoIncerto, ConnectionError),
    ("/gateway", EfeitoIncerto, ConnectionError),
    ("/sem-credencial", http.CredencialRecusada, http.CredencialRecusada),
    ("/proibido", http.CredencialRecusada, http.CredencialRecusada),
])
def test_status_de_erro_na_escrita_e_na_leitura(caminho, escrita, leitura):
    with ServidorHttp(_respostas_de_escrita) as rodando:
        with pytest.raises(escrita):
            http.pedir("POST", rodando.url + caminho, corpo={})
        with pytest.raises(leitura):
            http.pedir("GET", rodando.url + caminho)


def test_pedido_recusado_4xx_e_parametro_invalido_e_nao_pausa_a_integracao():
    conector = Conector(Relogio())
    with ServidorHttp(_respostas_de_escrita) as rodando:
        for _ in range(FALHAS_PARA_PAUSAR + 1):
            with pytest.raises(ErroFerramenta) as erro:
                conector.chamar("teste", lambda: http.pedir("GET", rodando.url + "/recusado"))
            assert erro.value.tipo_erro == "parametro_invalido"
        assert conector.chamar("teste", lambda: http.pedir("GET", rodando.url + "/ok")).status == 201
    assert conector.saude({}) == "ok"


class _Gotejando(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "12")
        self.end_headers()
        for byte in b'{"ok": true}':
            self.wfile.write(bytes([byte]))
            self.wfile.flush()
            time.sleep(0.15)

    def log_message(self, *args):
        return


def test_prazo_total_vale_para_o_pedido_inteiro_nao_por_leitura():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Gotejando)
    servidor.daemon_threads = True
    linha = threading.Thread(target=servidor.serve_forever, daemon=True)
    linha.start()
    try:
        inicio = time.monotonic()
        with pytest.raises(TimeoutError):
            http.pedir("GET", f"http://127.0.0.1:{servidor.server_address[1]}/", tempo_limite=0.5)
        assert time.monotonic() - inicio < 1.2  # sem o prazo total, levaria uns 1,8 s
    finally:
        servidor.shutdown()
        servidor.server_close()


# --- a suíte não sai do computador --------------------------------------------------------------------


def test_a_suite_recusa_conexao_fora_do_loopback_e_ignora_proxy():
    assert not any(v.lower() in ("http_proxy", "https_proxy", "all_proxy") for v in os.environ)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexao, pytest.raises(ConnectionRefusedError):
        conexao.connect(("203.0.113.10", 443))  # endereço de documentação (TEST-NET-3), nunca roteado
