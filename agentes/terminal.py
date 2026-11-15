"""Modo terminal dos agentes: conversa de teste no console, só para desenvolvimento local.

Fica fora do motor (`agente_atendimento/agente.py`) de propósito: aqui moram o modelo chamado direto
(sem o `LLMClient` do back-end) e o diretório de funcionários do mock, e o motor não deve depender
de nenhum dos dois. No produto, o back-end entrega o `Usuario` e o `chamar_modelo`.

Uso (com `MODO_TERMINAL=1` e `ID_USUARIO` no .env):
    python -m agentes.terminal              # agente de atendimento
    python -m agentes.terminal geral        # agente geral
"""

import argparse
import inspect
import logging
import math
import os
import re
import uuid
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

from agentes.agente_atendimento import agente as motor
from agentes.agente_geral import agente as geral
from ferramentas import confirmacoes, diretorio

load_dotenv()

LLM_URL = os.environ.get("LLM_URL", "")  # só do .env; sem valor padrão no código
MODELO_PADRAO = "qwen3.8:27b"


def modelo_do_ambiente(ambiente=os.environ):
    """`LLM_MODELO` do .env. Vazio (como no .env.example) vale o padrão: um nome vazio faria o servidor recusar."""
    return ambiente.get("LLM_MODELO", "").strip() or MODELO_PADRAO


LLM_MODELO = modelo_do_ambiente()
SEGUNDOS_POR_CHAMADA = 120  # timeout de uma chamada avulsa; dentro de um turno vale o tempo que sobra


def segundos_por_turno_do_ambiente(ambiente=os.environ):
    """Prazo de um turno no terminal: `LLM_SEGUNDOS_POR_TURNO` do .env, sempre dentro do teto do motor.

    Sem valor (ou inválido), vale o teto: o modelo local mede dezenas de segundos por chamada, e o padrão
    do motor (120 s) estoura. O prazo continua existindo; o terminal só não o aperta mais que o motor deixa."""
    teto = motor.SEGUNDOS_MAXIMOS_POR_TURNO
    try:
        valor = float(ambiente.get("LLM_SEGUNDOS_POR_TURNO", "").strip().replace(",", "."))
    except ValueError:
        return teto
    return min(valor, teto) if math.isfinite(valor) and valor > 0 else teto


PENSAMENTO_RE = re.compile(r"^[ \t]*PENSAMENTO[ \t]*:[ \t]*(.+)$", flags=re.MULTILINE)


def mostrando_o_pensamento(chamar_modelo, escrever=print):
    """Embrulha o `chamar_modelo` e escreve a linha `PENSAMENTO:` de cada resposta, assim que ela chega.

    O prompt do agente já pede essa linha antes de cada ação; o motor a ignora e a trajetória não a guarda
    (ela é texto livre, pode citar dado). Aqui ela só aparece na tela de quem testa, sem log nem arquivo.
    O embrulho repassa `tempo_limite` só se o modelo de dentro declara esse parâmetro, como o motor faz."""
    repassa_tempo = "tempo_limite" in inspect.signature(chamar_modelo).parameters

    def chamar(prompt_sistema, prompt, tempo_limite=None):
        opcoes = {"tempo_limite": tempo_limite} if repassa_tempo else {}
        resposta = chamar_modelo(prompt_sistema, prompt, **opcoes)
        achado = PENSAMENTO_RE.search(resposta) if isinstance(resposta, str) else None
        if achado:
            escrever(f"  Pensamento: {achado.group(1).strip()}")
        return resposta

    return chamar


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
def buscar_usuario_no_diretorio(id_usuario):
    """PONTO ÚNICO de ligação do modo terminal com o diretório de funcionários do mock (O12).

    Devolve o `governanca.Usuario` montado pelo cargo ou None se o id não existe ou o funcionário não
    está ativo (a regra é de `ferramentas.diretorio`, a mesma que o back-end usa): negar por padrão.
    O banco é o da fachada `ferramentas.dados_sinteticos` (`MOCK_DATABASE_URL` ou o SQLite local);
    quem quiser outro chama `dados_sinteticos.configurar(...)`. Diretório fora do ar não vira "não
    encontrado": levanta ValueError.
    """
    try:
        return diretorio.buscar_usuario(id_usuario)
    except ConnectionError:
        raise ValueError("Diretório de funcionários indisponível.") from None


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


def _modelo_indisponivel(erro):
    """`ModeloIndisponivel` de mensagem genérica, com `causa` para diagnóstico: o tipo da falha ou, se o
    servidor respondeu com erro, "HTTP <código>". Nunca o texto do erro: o do `requests` traz a URL."""
    resposta = getattr(erro, "response", None)
    codigo = getattr(resposta, "status_code", None)
    excecao = motor.ModeloIndisponivel("Modelo indisponível.")
    excecao.causa = f"HTTP {codigo}" if isinstance(codigo, int) else type(erro).__name__
    return excecao


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
    except (requests.RequestException, ValueError, KeyError) as erro:
        raise _modelo_indisponivel(erro) from None
    if not isinstance(texto, str):
        raise _modelo_indisponivel(TypeError())
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- PRÉVIAS ESPERANDO CONFIRMAÇÃO (escrita em duas fases) ----------
def revisar_previas(funcionario, ler=None, escrever=print):
    """Mostra as prévias que esperam este funcionário e pergunta o que fazer com cada uma.

    É o papel que o cartão de revisão terá na interface: quem confirma é a pessoa, nunca o modelo.
    """
    ler = ler or input  # resolvido na hora da chamada, para os testes poderem trocar o input()
    for previa in confirmacoes.pendentes(funcionario):
        para = previa.get("para", {})
        cabecalho = f"{previa['confirmacao_id']} ({previa['ferramenta']}, vale até {previa['expira_em']})"
        escrever(f"\n=== PRÉVIA {cabecalho} ===")
        escrever(f"Para: {para.get('email')} ({para.get('papel')} de {para.get('codigo')})")
        escrever(f"Assunto: {previa.get('assunto')}")
        escrever(previa.get("corpo", ""))
        escolha = ler("Enviar? [s] envia, [n] descarta, Enter deixa para depois: ").strip().lower()
        if escolha == "s":
            resultado = confirmacoes.confirmar(previa["confirmacao_id"], funcionario)
        elif escolha == "n":
            resultado = confirmacoes.cancelar(previa["confirmacao_id"], funcionario)
        else:
            continue
        id_mensagem = (resultado["dados"] or {}).get("id_mensagem")
        detalhe = f" ({id_mensagem}, caixa de saída simulada)" if id_mensagem else ""
        escrever(f"  {resultado['mensagem']}{detalhe}")


# ---------- A CONVERSA ----------
def conversar_no_terminal(funcionario, agente=AGENTES["atendimento"], chamar_modelo=None):
    """Conversa de teste: aqui sim se usa input(); a resposta do funcionário vira o próximo turno."""
    chamar_modelo = mostrando_o_pensamento(chamar_modelo or chamar_llm)
    historico = []
    while True:
        mensagem = input("\nVocê: ").strip()
        if mensagem.lower() in ("sair", "exit"):
            break
        if not mensagem:
            continue
        estado = None
        while True:
            contexto = {
                "execucao_id": uuid.uuid4().hex,
                "agente_id": agente.agente_id,
                "segundos_por_turno": segundos_por_turno_do_ambiente(),
            }
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
        revisar_previas(funcionario)


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
