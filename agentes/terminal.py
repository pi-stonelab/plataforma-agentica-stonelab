"""Modo terminal dos agentes: conversa de teste no console, só para desenvolvimento local.

Fica fora do motor (`agente_atendimento/agente.py`) de propósito: aqui moram o modelo chamado direto
(sem o `LLMClient` do back-end) e o diretório de funcionários do mock, e o motor não deve depender
de nenhum dos dois. No produto, o back-end entrega o `Usuario` e o `chamar_modelo`.

Uso (com `MODO_TERMINAL=1` e `ID_USUARIO` no .env):
    python -m agentes.terminal              # agente de atendimento
    python -m agentes.terminal geral        # agente geral
"""

import argparse
import logging
import os
import re
import uuid
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from agentes.agente_atendimento import agente as motor
from agentes.agente_geral import agente as geral
from ferramentas import governanca

# [PENDENTE da etapa de ferramentas: quando `ferramentas/` expuser `buscar_funcionario` na fachada,
# troque só estes dois imports e a chamada em `buscar_usuario_no_diretorio`; o resto não muda.]
from mock.banco import criar_engine, url_padrao
from mock.consultas import buscar_funcionario

load_dotenv()

LLM_URL = os.environ.get("LLM_URL", "")  # só do .env; sem valor padrão no código
LLM_MODELO = os.environ.get("LLM_MODELO", "qwen3.8:27b")
SITUACAO_ATIVA = "ativo"  # DOC-MOCK §8.4: desligado e afastado não usam a plataforma
SEGUNDOS_POR_CHAMADA = 120  # timeout de uma chamada avulsa; dentro de um turno vale o tempo que sobra


@dataclass(frozen=True)
class AgenteDoTerminal:
    """O que muda de um agente para outro: id (para log e registro), ferramentas e prompt."""

    agente_id: str
    ferramentas: tuple[str, ...]
    sistema: str


AGENTES = {
    "atendimento": AgenteDoTerminal(motor.AGENTE_ID, motor.FERRAMENTAS_DO_AGENTE, motor.SISTEMA),
    "geral": AgenteDoTerminal(geral.AGENTE_ID, geral.FERRAMENTAS_DO_AGENTE, geral.SISTEMA),
}


# ---------- QUEM ESTÁ USANDO O AGENTE ----------
def buscar_usuario_no_diretorio(id_usuario, engine=None):
    """PONTO ÚNICO de ligação do modo terminal com o diretório de funcionários do mock (O12).

    Devolve o `governanca.Usuario` montado pelo cargo (nível, área e carteiras vêm do cargo e do
    time do diretório) ou None se o id não existe ou o funcionário não está ativo (desligado,
    afastado ou qualquer outra situação): negar por padrão. Sem `engine`, usa o SQLite local do mock.
    Diretório fora do ar não vira "não encontrado": levanta ValueError.
    """
    try:
        funcionario = buscar_funcionario(engine or criar_engine(url_padrao()), id_usuario)
    except (ConnectionError, SQLAlchemyError):
        raise ValueError("Diretório de funcionários indisponível.") from None
    if funcionario is None or funcionario["situacao"] != SITUACAO_ATIVA:
        return None
    return governanca.usuario_do_cargo(
        funcionario["id"], funcionario["cargo"], tuple(funcionario["carteiras"])
    )


def usuario_do_ambiente(ambiente=os.environ, buscar_no_diretorio=buscar_usuario_no_diretorio):
    """Monta o funcionário do modo terminal só pelo ID_USUARIO do .env; o perfil vem do diretório.

    Nível, área e carteira NÃO são lidos do ambiente (O12). No produto real, o back-end valida
    o login e entrega o Usuario já pronto ao agente. ID ausente, inválido ou desconhecido: não sobe.
    """
    id_usuario = ambiente.get("ID_USUARIO", "").strip()
    if not motor.IDENTIFICADOR_SEGURO_RE.match(id_usuario):
        raise ValueError("Defina ID_USUARIO no .env (letras, dígitos, '_' ou '-').")
    usuario = buscar_no_diretorio(id_usuario)
    if usuario is None:
        raise ValueError("ID_USUARIO não encontrado no diretório de funcionários.")
    return usuario


# ---------- CHAMADA DIRETA AO LLM ----------
def montar_headers():
    return {
        "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
        "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
        "Content-Type": "application/json",
    }


def chamar_llm(prompt_sistema: str, prompt: str, tempo_limite: float = SEGUNDOS_POR_CHAMADA) -> str:
    """Chamada direta ao Ollama, para o terminal. No produto quem chama é o `LLMClient` do back-end.

    `tempo_limite` (segundos) é o timeout da chamada; o motor passa o que sobra do turno. Falha de
    rede ou resposta ilegível vira `ModeloIndisponivel` com mensagem genérica: a do `requests`
    traria a URL do modelo.
    """
    if not LLM_URL:
        raise RuntimeError("Defina LLM_URL no .env para usar o modelo direto (modo terminal).")
    payload = {
        "model": LLM_MODELO,
        "system": prompt_sistema,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "stop": [motor.PARADA_DO_MODELO]},
    }
    headers = montar_headers()  # fora do try: credencial ausente é erro de configuração
    try:
        r = requests.post(
            f"{LLM_URL}/api/generate", headers=headers, json=payload, timeout=tempo_limite
        )
        r.raise_for_status()
        texto = r.json()["response"]
    except (requests.RequestException, ValueError, KeyError):
        raise motor.ModeloIndisponivel("Modelo indisponível.") from None
    if not isinstance(texto, str):
        raise motor.ModeloIndisponivel("Modelo indisponível.")
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- A CONVERSA ----------
def conversar_no_terminal(funcionario, agente=AGENTES["atendimento"], chamar_modelo=None):
    """Conversa de teste: aqui sim se usa input(); a resposta do funcionário vira o próximo turno."""
    chamar_modelo = chamar_modelo or chamar_llm
    historico = []
    while True:
        mensagem = input("\nVocê: ").strip()
        if mensagem.lower() in ("sair", "exit"):
            break
        if not mensagem:
            continue
        estado = None
        while True:
            contexto = {"execucao_id": uuid.uuid4().hex, "agente_id": agente.agente_id}
            turno = motor.rodar_turno(
                mensagem, funcionario, agente.ferramentas, chamar_modelo, historico, estado,
                contexto, agente.sistema,
            )
            print("\n=== TRAJETÓRIA ===")
            for linha in turno.trajetoria:
                print(" •", linha)
            print("\nAgente:", turno.resposta)
            historico.append((mensagem, turno.resposta))
            if turno.tipo != "pergunta":
                break
            mensagem, estado = input("\nVocê: ").strip(), turno.estado


def principal(argumentos=None):
    """Ponto de entrada: `python -m agentes.terminal [atendimento|geral]`."""
    analisador = argparse.ArgumentParser(description="Conversa de teste com um agente, no terminal.")
    analisador.add_argument("agente", nargs="?", choices=sorted(AGENTES), default="atendimento")
    escolhido = analisador.parse_args(argumentos).agente
    if os.environ.get("MODO_TERMINAL") != "1":  # O12
        raise SystemExit("Modo terminal desligado. Defina MODO_TERMINAL=1 para usar.")
    if not LLM_URL:
        raise SystemExit("Defina LLM_URL no .env para usar o modelo direto (modo terminal).")
    logging.basicConfig(level=logging.INFO, format="  [%(levelname)s] %(message)s")
    try:
        funcionario = usuario_do_ambiente()
    except ValueError as erro:
        raise SystemExit(str(erro)) from erro
    print(
        f"Agente {escolhido} da {motor.NOME_EMPRESA} (funcionário {funcionario.id_usuario}, "
        f"{funcionario.nivel}, {funcionario.area}). Digite 'sair' para encerrar."
    )
    conversar_no_terminal(funcionario, AGENTES[escolhido])


if __name__ == "__main__":
    principal()
