import ast
import operator
import os
import re

import requests

BASE_URL = "https://llm.thiagomedeiros.dev"
MODELO = "qwen3.8:27b"
MAX_PASSOS = 5

HEADERS = {
    "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
    "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
    "Content-Type": "application/json",
}

# Instruções que ensinam o modelo o "protocolo" do agente.
SISTEMA = """Você é um agente. Responda SEMPRE em UMA destas duas formas, e nada além:

CALCULAR: <expressão matemática>
FINAL: <resposta final para o usuário>

Use CALCULAR quando precisar de uma conta. O resultado voltará como "Observação:".
Use FINAL somente quando já souber a resposta.
Nunca escreva "Observação:" você mesmo."""


# ---------- FERRAMENTA ----------
# Calculadora segura: aceita só números e + - * / ** (nada de eval perigoso).
OPERADORES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _avaliar(no):
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return no.value
    if isinstance(no, ast.BinOp) and type(no.op) in OPERADORES:
        return OPERADORES[type(no.op)](_avaliar(no.left), _avaliar(no.right))
    if isinstance(no, ast.UnaryOp) and type(no.op) in OPERADORES:
        return OPERADORES[type(no.op)](_avaliar(no.operand))
    raise ValueError("expressão não permitida")


def calculadora(expressao: str) -> str:
    try:
        return str(_avaliar(ast.parse(expressao.strip(), mode="eval").body))
    except Exception as e:
        return f"erro: {e}"


# ---------- CHAMADA AO LLM ----------
def chamar_llm(prompt: str) -> str:
    payload = {
        "model": MODELO,
        "system": SISTEMA,
        "prompt": prompt,
        "stream": False,
        "think": False,  # desliga o "raciocínio" do qwen3, se suportado
        "options": {
            "temperature": 0,
            "stop": ["Observação:"],  # impede o modelo de inventar o resultado
        },
    }
    r = requests.post(f"{BASE_URL}/api/generate", headers=HEADERS, json=payload, timeout=120)
    r.raise_for_status()
    texto = r.json()["response"]
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- O LOOP DO AGENTE ----------
def agente(pergunta: str) -> str:
    historico = f"Pergunta: {pergunta}"

    for passo in range(1, MAX_PASSOS + 1):
        resposta = chamar_llm(historico)
        print(f"\n[passo {passo}] modelo: {resposta}")

        final = re.search(r"FINAL:\s*(.+)", resposta, flags=re.DOTALL)
        if final:
            return final.group(1).strip()

        conta = re.search(r"CALCULAR:\s*(.+)", resposta)
        if conta:
            resultado = calculadora(conta.group(1))
        else:
            resultado = "formato inválido, use CALCULAR: ou FINAL:"

        print(f"[passo {passo}] ferramenta: {resultado}")
        historico += f"\n{resposta}\nObservação: {resultado}"

    return "Atingi o limite de passos sem terminar."


if __name__ == "__main__":
    print("Agente pronto. Digite 'sair' para encerrar.")
    while True:
        pergunta = input("\nVocê: ").strip()
        if pergunta.lower() in ("sair", "exit"):
            break
        if not pergunta:
            continue
        print("\nAgente:", agente(pergunta))