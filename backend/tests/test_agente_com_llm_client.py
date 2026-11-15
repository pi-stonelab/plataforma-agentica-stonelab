"""O agente da frente 3 rodando com o nosso LLMClient e o catálogo da frente 4.

Prova que as peças se encaixam sem o servidor do professor: o modelo é simulado.
"""

import json

import httpx
from agentes.agente_atendimento import agente as modulo_agente
from ferramentas import governanca

from app.llm_client import LLMClient, LLMClientMock

USUARIO_N2 = governanca.Usuario("teste-n2", "N2", "atendimento")


def test_agente_conclui_com_o_mock():
    chamar = LLMClientMock().como_chamar_modelo(sistema=modulo_agente.SISTEMA)

    resposta, trajetoria = modulo_agente.agente("Oi", USUARIO_N2, chamar_modelo=chamar)

    assert resposta.startswith("[modo mock]")
    assert trajetoria[-1].endswith("resposta final entregue")


def test_agente_usa_ferramenta_de_verdade_pelo_llm_client():
    """O 'modelo' segue um roteiro; a ferramenta roda de verdade no catálogo."""
    roteiro = iter(
        [
            "PENSAMENTO: ver áreas.\nLER: ",
            "PENSAMENTO: área financeira.\nLER: financeiro",
            "PENSAMENTO: ler a ferramenta.\nLER: financeiro/consultar_transacoes_cliente",
            'PENSAMENTO: consultar.\nUSAR: consultar_transacoes_cliente | {"id_cliente": "CLI-0001", "limite": 2}',
            "PENSAMENTO: pronto.\nFINAL: O cliente CLI-0001 tem transações recentes.",
        ]
    )
    prompts = []

    def servidor(request):
        prompts.append(json.loads(request.content)["prompt"])
        return httpx.Response(
            200, json={"response": next(roteiro), "prompt_eval_count": 1, "eval_count": 1}
        )

    cliente = LLMClient(
        "http://ollama.teste",
        "qwen-teste",
        transporte=httpx.MockTransport(servidor),
        espera_entre_tentativas=0,
    )
    usos = []
    chamar = cliente.como_chamar_modelo(sistema=modulo_agente.SISTEMA, ao_responder=usos.append)

    resposta, trajetoria = modulo_agente.agente(
        "Transações do CLI-0001?", USUARIO_N2, chamar_modelo=chamar
    )

    assert resposta == "O cliente CLI-0001 tem transações recentes."
    assert any("'consultar_transacoes_cliente' executada: ok" in passo for passo in trajetoria)
    assert '"status": "ok"' in prompts[-1]  # o resultado da ferramenta voltou ao modelo
    assert len(usos) == 5  # cada chamada ao modelo foi contabilizada
