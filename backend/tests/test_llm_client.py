"""Testes do LLMClient. Nenhum chama o servidor de verdade: o Ollama é simulado."""

import json
import threading
import time

import httpx
import pytest
from agentes.agente_atendimento.agente import PARADA_DO_MODELO, ModeloIndisponivel

from app.llm_client import ErroLLM, LLMClient, LLMClientMock, criar_cliente, juntar_pedacos

URL_SECRETA = "http://ollama-secreto.teste"


def cliente_com(responder, **extras) -> LLMClient:
    """LLMClient cujo 'servidor' é a função `responder(request) -> httpx.Response`."""
    opcoes = {"tentativas": 3, "espera_entre_tentativas": 0, **extras}
    return LLMClient(URL_SECRETA, "qwen-teste", transporte=httpx.MockTransport(responder), **opcoes)


def pedacos(*linhas) -> bytes:
    return "".join(json.dumps(linha) + "\n" for linha in linhas).encode()


def resposta_ollama(texto, entrada=10, saida=5):
    """Resposta em pedaços, como o Ollama manda com stream: true (o texto em dois pedaços)."""
    meio = len(texto) // 2
    return httpx.Response(
        200,
        content=pedacos(
            {"model": "qwen-teste", "response": texto[:meio], "done": False},
            {
                "model": "qwen-teste",
                "response": texto[meio:],
                "done": True,
                "prompt_eval_count": entrada,
                "eval_count": saida,
            },
        ),
    )


def test_gerar_junta_os_pedacos_conta_tokens_e_envia_corpo_certo():
    recebidos = []

    def servidor(request):
        recebidos.append(json.loads(request.content))
        return resposta_ollama("<think>rascunho</think> FINAL: oi", entrada=42, saida=7)

    resposta = cliente_com(servidor).gerar("pergunta", sistema="regras", opcoes={"num_ctx": 8192})

    assert resposta.texto == "FINAL: oi"  # bloco <think> removido, pedaços juntos
    assert (resposta.tokens_entrada, resposta.tokens_saida) == (42, 7)
    corpo = recebidos[0]
    assert corpo["model"] == "qwen-teste"
    assert corpo["system"] == "regras"
    assert corpo["stream"] is True
    assert corpo["think"] is False
    # Padrão do agente (temperatura 0 e parada em "Observação:") somado às opções de quem chamou.
    assert corpo["options"] == {"temperature": 0, "stop": [PARADA_DO_MODELO], "num_ctx": 8192}


def test_resposta_cortada_sem_done_tenta_de_novo_e_depois_desiste():
    chamadas = []

    def servidor(request):
        chamadas.append(1)
        return httpx.Response(200, content=pedacos({"response": "USAR: consultar_cl", "done": False}))

    with pytest.raises(ErroLLM) as erro:
        cliente_com(servidor).gerar("x")
    assert erro.value.tipo == "indisponivel"
    assert len(chamadas) == 3  # o motor nunca recebe uma ação pela metade


def test_erro_no_meio_do_stream_nao_vaza_o_texto_do_servidor():
    def servidor(request):
        return httpx.Response(200, content=pedacos({"error": "detalhe interno do servidor"}))

    with pytest.raises(ErroLLM) as erro:
        cliente_com(servidor, tentativas=1).gerar("x")
    assert "detalhe interno" not in str(erro.value)


def test_juntar_pedacos_confere_o_prazo_total_a_cada_pedaco():
    relogio = iter([0.0, 5.0, 11.0])
    linhas = [json.dumps({"response": "a", "done": False})] * 3

    with pytest.raises(ErroLLM) as erro:
        juntar_pedacos(linhas, prazo=10.0, agora=lambda: next(relogio))
    assert erro.value.tipo == "tempo_esgotado"


def test_envia_cabecalhos_do_cloudflare_so_quando_configurados():
    cabecalhos = []

    def servidor(request):
        cabecalhos.append(request.headers)
        return resposta_ollama("ok")

    cliente_com(servidor, cf_client_id="id-falso", cf_client_secret="segredo-falso").gerar("x")
    cliente_com(servidor).gerar("x")

    assert cabecalhos[0]["CF-Access-Client-Id"] == "id-falso"
    assert cabecalhos[0]["CF-Access-Client-Secret"] == "segredo-falso"
    assert "CF-Access-Client-Id" not in cabecalhos[1]


def test_tenta_de_novo_quando_servidor_falha_e_depois_responde():
    chamadas = []

    def servidor(request):
        chamadas.append(1)
        return httpx.Response(524) if len(chamadas) < 3 else resposta_ollama("ok")

    assert cliente_com(servidor).gerar("x").texto == "ok"
    assert len(chamadas) == 3


def test_desiste_depois_das_tentativas_com_tempo_esgotado():
    chamadas = []

    def servidor(request):
        chamadas.append(1)
        raise httpx.ReadTimeout("demorou", request=request)

    with pytest.raises(ErroLLM) as erro:
        cliente_com(servidor).gerar("x")
    assert erro.value.tipo == "tempo_esgotado"
    assert len(chamadas) == 3


def test_tempo_limite_vira_o_timeout_da_chamada():
    timeouts = []

    def servidor(request):
        timeouts.append(request.extensions["timeout"]["read"])
        return resposta_ollama("ok")

    cliente = cliente_com(servidor, timeout_segundos=300)
    cliente.gerar("x", tempo_limite=42)
    cliente.gerar("x")  # sem tempo_limite: vale o teto
    cliente.gerar("x", tempo_limite=9999)  # maior que o teto: vale o teto

    assert timeouts[0] == pytest.approx(42, abs=1)
    assert timeouts[1] == pytest.approx(300, abs=1)
    assert timeouts[2] == pytest.approx(300, abs=1)


def test_sem_prazo_restante_nao_chama_o_servidor():
    chamadas = []
    relogio = iter([0.0, 100.0, 100.0])

    def servidor(request):
        chamadas.append(1)
        return resposta_ollama("ok")

    cliente = cliente_com(servidor, relogio=lambda: next(relogio))
    with pytest.raises(ErroLLM) as erro:
        cliente.gerar("x", tempo_limite=10)
    assert erro.value.tipo == "tempo_esgotado"
    assert chamadas == []


def test_credencial_recusada_nao_tenta_de_novo():
    chamadas = []

    def servidor(request):
        chamadas.append(1)
        return httpx.Response(403)

    with pytest.raises(ErroLLM) as erro:
        cliente_com(servidor).gerar("x")
    assert erro.value.tipo == "credenciais"
    assert len(chamadas) == 1


def test_pedaco_sem_campo_response_vira_erro():
    with pytest.raises(ErroLLM) as erro:
        cliente_com(lambda request: httpx.Response(200, content=pedacos({"oi": 1}))).gerar("x")
    assert erro.value.tipo == "resposta_invalida"


def test_erro_e_modelo_indisponivel_sem_a_url():
    def servidor(request):
        raise httpx.ConnectError(f"falhou ao conectar em {URL_SECRETA}", request=request)

    with pytest.raises(ModeloIndisponivel) as erro:
        cliente_com(servidor).gerar("x")
    assert isinstance(erro.value, ErroLLM)
    assert "ollama-secreto" not in str(erro.value)


def test_respeita_limite_de_chamadas_simultaneas():
    trava = threading.Lock()
    estado = {"agora": 0, "pico": 0}

    def servidor(request):
        with trava:
            estado["agora"] += 1
            estado["pico"] = max(estado["pico"], estado["agora"])
        time.sleep(0.05)
        with trava:
            estado["agora"] -= 1
        return resposta_ollama("ok")

    cliente = cliente_com(servidor, max_simultaneas=2)
    threads = [threading.Thread(target=cliente.gerar, args=("x",)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert estado["pico"] == 2


def test_listar_modelos():
    def servidor(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "b"}, {"name": "a"}]})

    assert cliente_com(servidor).listar_modelos() == ["a", "b"]


def test_como_chamar_modelo_tem_o_formato_do_motor_e_avisa_tokens():
    avisos, corpos = [], []

    def servidor(request):
        corpos.append(json.loads(request.content))
        return resposta_ollama("FINAL: oi", 3, 2)

    chamar = cliente_com(servidor).como_chamar_modelo(ao_responder=avisos.append)

    assert chamar("protocolo", "pergunta", tempo_limite=30) == "FINAL: oi"
    assert corpos[0]["system"] == "protocolo"
    assert corpos[0]["prompt"] == "pergunta"
    assert avisos[0].tokens_entrada == 3


def test_sem_url_exige_configuracao():
    with pytest.raises(ErroLLM) as erro:
        LLMClient("", "qwen")
    assert erro.value.tipo == "configuracao"


def test_criar_cliente_em_modo_mock():
    class Config:
        llm_modo = "mock"

    assert isinstance(criar_cliente(Config()), LLMClientMock)


def test_criar_cliente_le_llm_url_e_llm_modelo():
    class Config:
        llm_modo = "ollama"
        llm_url = "http://modelo.teste"
        llm_modelo = "qwen-x"
        cf_access_client_id = None
        cf_access_client_secret = None
        llm_timeout_segundos = 60.0
        llm_tentativas = 2
        llm_max_simultaneas = 4

    cliente = criar_cliente(Config())
    assert isinstance(cliente, LLMClient)
    assert (cliente.modelo, cliente.timeout_segundos, cliente.tentativas) == ("qwen-x", 60.0, 2)
