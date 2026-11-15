"""Testes do LLMClient. Nenhum chama o servidor de verdade: o Ollama é simulado."""

import json
import threading
import time

import httpx
import pytest

from app.llm_client import ErroLLM, LLMClient, LLMClientMock, criar_cliente


def cliente_com(responder, **extras) -> LLMClient:
    """LLMClient cujo 'servidor' é a função `responder(request) -> httpx.Response`."""
    opcoes = {"tentativas": 3, "espera_entre_tentativas": 0, **extras}
    return LLMClient(
        "http://ollama.teste", "qwen-teste", transporte=httpx.MockTransport(responder), **opcoes
    )


def resposta_ollama(texto, entrada=10, saida=5):
    return httpx.Response(
        200,
        json={
            "model": "qwen-teste",
            "response": texto,
            "prompt_eval_count": entrada,
            "eval_count": saida,
        },
    )


def test_gerar_devolve_texto_tokens_e_envia_corpo_certo():
    recebidos = []

    def servidor(request):
        recebidos.append(json.loads(request.content))
        return resposta_ollama("<think>rascunho</think> FINAL: oi", entrada=42, saida=7)

    resposta = cliente_com(servidor).gerar("pergunta", sistema="regras", opcoes={"temperature": 0})

    assert resposta.texto == "FINAL: oi"  # bloco <think> removido
    assert (resposta.tokens_entrada, resposta.tokens_saida) == (42, 7)
    corpo = recebidos[0]
    assert corpo["model"] == "qwen-teste"
    assert corpo["system"] == "regras"
    assert corpo["stream"] is False
    assert corpo["options"] == {"temperature": 0}


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
        return httpx.Response(503) if len(chamadas) < 3 else resposta_ollama("ok")

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


def test_credencial_recusada_nao_tenta_de_novo():
    chamadas = []

    def servidor(request):
        chamadas.append(1)
        return httpx.Response(403)

    with pytest.raises(ErroLLM) as erro:
        cliente_com(servidor).gerar("x")
    assert erro.value.tipo == "credenciais"
    assert len(chamadas) == 1


def test_resposta_sem_campo_response_vira_erro():
    with pytest.raises(ErroLLM) as erro:
        cliente_com(lambda request: httpx.Response(200, json={"oi": 1})).gerar("x")
    assert erro.value.tipo == "resposta_invalida"


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


def test_como_chamar_modelo_entrega_texto_e_avisa_tokens():
    avisos = []
    chamar = cliente_com(lambda r: resposta_ollama("FINAL: oi", 3, 2)).como_chamar_modelo(
        ao_responder=avisos.append
    )

    assert chamar("x") == "FINAL: oi"
    assert avisos[0].tokens_entrada == 3


def test_sem_host_exige_configuracao():
    with pytest.raises(ErroLLM) as erro:
        LLMClient("", "qwen")
    assert erro.value.tipo == "configuracao"


def test_criar_cliente_em_modo_mock():
    class Config:
        llm_modo = "mock"

    assert isinstance(criar_cliente(Config()), LLMClientMock)
