"""O agente da frente 3 (`rodar_turno`) rodando com o nosso LLMClient e o catálogo da frente 4.

Prova que as peças se encaixam sem o servidor do professor: o modelo é simulado.
"""

import json

import httpx
from agentes.agente_atendimento import agente as modulo_agente
from ferramentas import governanca

from app.llm_client import LLMClient, LLMClientMock

from . import apoio_agente as apoio

USUARIO_N2 = governanca.usuario_do_cargo("F0011", "coordenador_financeiro", ())


def test_turno_conclui_com_o_mock():
    chamar = LLMClientMock().como_chamar_modelo()

    turno = modulo_agente.rodar_turno(
        "Oi", USUARIO_N2, modulo_agente.FERRAMENTAS_DO_AGENTE, chamar_modelo=chamar
    )

    assert turno.tipo == "final"
    assert turno.resposta.startswith("[modo mock]")


def test_turno_usa_ferramenta_de_verdade_pelo_llm_client():
    """O 'modelo' segue um roteiro; a ferramenta roda de verdade no catálogo."""
    apoio.mundo()
    roteiro = iter(
        [
            "PENSAMENTO: ver áreas.\nLER: ",
            "PENSAMENTO: área financeira.\nLER: financeiro",
            "PENSAMENTO: ler a ferramenta.\nLER: financeiro/consultar_transacoes_cliente",
            'PENSAMENTO: consultar.\nUSAR: consultar_transacoes_cliente | {"id_cliente": "M00001", "limite": 2}',
            "PENSAMENTO: pronto.\nFINAL: O cliente M00001 tem transações recentes.",
        ]
    )
    corpos = []

    def servidor(request):
        corpos.append(json.loads(request.content))
        linha = {"response": next(roteiro), "done": True, "prompt_eval_count": 1, "eval_count": 1}
        return httpx.Response(200, content=(json.dumps(linha) + "\n").encode())

    cliente = LLMClient(
        "http://ollama.teste",
        "qwen-teste",
        transporte=httpx.MockTransport(servidor),
        espera_entre_tentativas=0,
    )
    usos = []
    chamar = cliente.como_chamar_modelo(ao_responder=usos.append)

    turno = modulo_agente.rodar_turno(
        "Transações do M00001?",
        USUARIO_N2,
        modulo_agente.FERRAMENTAS_DO_AGENTE,
        chamar_modelo=chamar,
        contexto={"execucao_id": "exec-teste"},
    )

    assert turno.tipo == "final"
    assert turno.resposta == "O cliente M00001 tem transações recentes."
    assert any("'consultar_transacoes_cliente' executada: ok" in passo for passo in turno.trajetoria)
    assert '"status": "ok"' in corpos[-1]["prompt"]  # o resultado da ferramenta voltou ao modelo
    assert all(c["system"] == modulo_agente.SISTEMA for c in corpos)  # o protocolo vai como system
    assert all(c["options"]["stop"] == [modulo_agente.PARADA_DO_MODELO] for c in corpos)
    assert len(usos) == 5  # cada chamada ao modelo foi contabilizada


def test_modelo_fora_do_ar_encerra_o_turno_sem_vazar_a_url():
    def servidor(request):
        raise httpx.ConnectError("sem rota para http://ollama-secreto.teste", request=request)

    cliente = LLMClient(
        "http://ollama-secreto.teste",
        "qwen-teste",
        transporte=httpx.MockTransport(servidor),
        espera_entre_tentativas=0,
    )

    turno = modulo_agente.rodar_turno(
        "Oi", USUARIO_N2, modulo_agente.FERRAMENTAS_DO_AGENTE, chamar_modelo=cliente.como_chamar_modelo()
    )

    assert (turno.tipo, turno.motivo) == ("limite", "modelo_indisponivel")
    assert "ollama-secreto" not in turno.resposta
