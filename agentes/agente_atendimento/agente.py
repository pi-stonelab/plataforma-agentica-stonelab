import json
import os
import re
import uuid

import requests
from dotenv import load_dotenv

from ferramentas import catalogo, governanca

load_dotenv()

# ---------- CONFIGURAÇÃO ----------
BASE_URL = "https://llm.thiagomedeiros.dev"
MODELO = "qwen3.8:27b"
MAX_PASSOS = 8          # agora há mais etapas (índice -> ferramenta -> uso -> resposta)
MAX_CHARS_MD = 6000     # limite de texto de cada leitura e de cada resultado enviado ao modelo

NOME_EMPRESA = "Stone"
AGENTE_ID = "agente_atendimento"

# Ferramentas que este agente pode usar. O catálogo ainda confere o nível e a área do funcionário.
# [aqui conectamos com agentes: lista vinda da configuração do agente, KAN-55]
FERRAMENTAS_DO_AGENTE = (
    "consultar_cliente",
    "consultar_transacoes_cliente",
    "calcular_multa_atraso",
    "consultar_endereco_cep",
    "solicitar_ferramenta_ausente",
)

# ---------- PROTOCOLO DO AGENTE ----------
SISTEMA = """Você é um assistente interno da {EMPRESA}. Ajuda funcionários a consultar dados e fazer cálculos usando ferramentas, com educação, clareza e sem inventar informações.

A cada passo, responda EXATAMENTE neste formato:

PENSAMENTO: <uma ou duas frases explicando seu raciocínio>
<UMA ação da lista abaixo>

Ações disponíveis (use apenas UMA por resposta):
LER: <caminho>   (vazio lê o índice de áreas; uma área, como financeiro, lista as ferramentas dela; uma ferramenta, como financeiro/calcular_multa_atraso, mostra a descrição e os parâmetros)
USAR: <nome_da_ferramenta> | <argumentos em JSON, em uma única linha>
PERGUNTAR: <pergunta ao funcionário>
FINAL: <resposta final ao funcionário>

Regras de trabalho (siga esta ordem):
1. Ao receber um pedido, use LER com o caminho vazio para ver as áreas.
2. Entre na área adequada e depois leia a ferramenta (LER: <area>/<ferramenta>). Só assim você saberá como ela funciona.
3. Só use USAR em uma ferramenta que você já leu. Use exatamente os parâmetros descritos nela.
4. Se faltar um dado (ex.: o código do cliente) ou algo estiver ambíguo, use PERGUNTAR. Nunca chute.
5. Se nenhuma ferramenta servir ao pedido, diga isso no FINAL, cite só as ferramentas que você viu e sugira a mais próxima. Antes de encerrar, use PERGUNTAR para oferecer o registro de um pedido de ferramenta nova. Se o funcionário aceitar, leia e use plataforma/solicitar_ferramenta_ausente e informe só o código do pedido, sem prometer aviso, prazo ou resposta de ninguém.
6. Se uma ferramenta devolver permissao_negada, ou se um caminho não for encontrado, diga no FINAL que você não tem acesso a isso. Não sugira outro jeito de obter o mesmo dado e nunca peça ao funcionário que adivinhe nomes de ferramentas.
7. Se a ferramenta devolver erro de parâmetro ou "não encontrado" para um dado (ex.: cliente inexistente), corrija o que for seu ou use PERGUNTAR. Nunca invente dados de clientes, valores ou prazos; use somente o que as ferramentas devolverem.
8. Nunca escreva "Observação:" você mesmo; o sistema a fornecerá."""
SISTEMA = SISTEMA.replace("{EMPRESA}", NOME_EMPRESA)

# Encontra a primeira ação escrita pelo modelo (ignora qualquer coisa inventada depois dela).
ACAO_RE = re.compile(r"^\s*(LER|USAR|PERGUNTAR|FINAL)\b[ \t]*:?[ \t]*", flags=re.MULTILINE)


# ---------- QUEM ESTÁ USANDO O AGENTE ----------
def usuario_do_ambiente(ambiente=os.environ):
    """Monta o funcionário a partir do .env, só para teste no terminal.

    No produto real, o back-end valida o login e entrega o Usuario já pronto ao agente.
    Falta qualquer dado ou valor inválido: o agente não sobe.
    """
    id_usuario = ambiente.get("ID_USUARIO", "").strip()
    nivel = ambiente.get("NIVEL", "").strip().upper()
    area = ambiente.get("AREA", "").strip().lower()
    if not id_usuario or nivel not in governanca.NIVEIS or area not in governanca.AREAS_USUARIO:
        raise ValueError(
            "Defina ID_USUARIO, NIVEL (N1 ou N2) e AREA "
            f"({', '.join(governanca.AREAS_USUARIO)}) no .env."
        )
    carteira = tuple(c.strip() for c in ambiente.get("CARTEIRA", "").split(",") if c.strip())
    return governanca.Usuario(id_usuario, nivel, area, carteira)


# ---------- ESTADO DE UM ATENDIMENTO ----------
class Atendimento:
    def __init__(self, usuario):
        self.usuario = usuario
        self.execucao_id = uuid.uuid4().hex
        self.indice_lido = False
        self.lidas = set()       # ferramentas cuja descrição já foi lida e estava liberada

    def ler(self, caminho):
        caminho = caminho.strip()
        if caminho and not self.indice_lido:
            return "erro: leia primeiro o índice (LER com o caminho vazio).", "bloqueado: índice não lido"
        texto = catalogo.ler(caminho, self.usuario, FERRAMENTAS_DO_AGENTE)[:MAX_CHARS_MD]
        if texto == catalogo.MENSAGEM_INDISPONIVEL:
            return texto, "caminho não encontrado ou não liberado"
        if not caminho:
            self.indice_lido = True
            return texto, "índice lido"
        nome = caminho.split("/")[-1]
        if nome in catalogo.ferramentas_liberadas(self.usuario, FERRAMENTAS_DO_AGENTE):
            self.lidas.add(nome)
        return texto, f"'{caminho}' lido"

    def usar(self, nome, argumentos_texto, passo):
        if nome not in self.lidas:
            return "erro: leia a ferramenta (LER: <area>/<ferramenta>) antes de usá-la.", "bloqueado: ferramenta não lida"
        try:
            args = json.loads(argumentos_texto)
            if not isinstance(args, dict):
                raise TypeError("os argumentos devem ser um objeto JSON")
        except (ValueError, TypeError) as e:
            return f"erro: argumentos inválidos ({e}).", "argumentos inválidos"

        contexto = {"agente_id": AGENTE_ID, "execucao_id": self.execucao_id, "passo": passo}
        resultado = catalogo.executar(nome, args, self.usuario, FERRAMENTAS_DO_AGENTE, contexto)
        texto = json.dumps(resultado, ensure_ascii=False, default=str)[:MAX_CHARS_MD]
        resumo = resultado["status"] if resultado["tipo_erro"] is None else resultado["tipo_erro"]
        return texto, f"'{nome}' executada: {resumo}"


# ---------- CHAMADA AO LLM ----------
def montar_headers():
    return {
        "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
        "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
        "Content-Type": "application/json",
    }


def chamar_llm(prompt: str) -> str:
    payload = {
        "model": MODELO,
        "system": SISTEMA,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "stop": ["Observação:"],  # impede o modelo de inventar o resultado
        },
    }
    r = requests.post(
        f"{BASE_URL}/api/generate", headers=montar_headers(), json=payload, timeout=120
    )
    r.raise_for_status()
    texto = r.json()["response"]
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- SAÍDA PARA O USUÁRIO ----------
def mostrar(rotulo: str, texto: str):
    print(f"  [{rotulo}] {texto}")


# ---------- O LOOP DO AGENTE ----------
def agente(pergunta, usuario, chamar_modelo=chamar_llm):
    historico = f"Pergunta do funcionário: {pergunta}"
    atendimento = Atendimento(usuario)
    trajetoria = []

    for passo in range(1, MAX_PASSOS + 1):
        print(f"\n--- passo {passo} ---")
        resposta = chamar_modelo(historico)
        m = ACAO_RE.search(resposta)

        if not m:
            mostrar("PENSAMENTO", resposta or "(vazio)")
            obs = "formato inválido: use PENSAMENTO + uma das ações (LER, USAR, PERGUNTAR, FINAL)."
            mostrar("SISTEMA", obs)
            trajetoria.append(f"Passo {passo}: resposta fora do formato")
            historico += f"\n{resposta}\nObservação: {obs}"
            continue

        acao = m.group(1)
        resto = resposta[m.end():]
        primeira_linha = resto.splitlines()[0].strip() if resto.strip() else ""
        pensamento = re.sub(r"^\s*PENSAMENTO:\s*", "", resposta[: m.start()]).strip()
        if pensamento:
            mostrar("PENSAMENTO", pensamento)

        # Guarda no histórico só até o fim da ação (descarta qualquer coisa inventada depois).
        if acao == "FINAL":
            registro = resposta[: m.end()] + resto
        else:
            registro = resposta[: m.end()] + primeira_linha

        if acao == "FINAL":
            final = resto.strip()
            if not atendimento.indice_lido:
                obs = "erro: antes de responder, consulte as ferramentas com LER."
                resumo = "bloqueado: FINAL sem consultar o índice"
                mostrar("SISTEMA", obs)
            elif not final:
                obs, resumo = "erro: FINAL vazio.", "FINAL vazio"
            else:
                trajetoria.append(f"Passo {passo}: resposta final entregue")
                return final, trajetoria

        elif acao == "LER":
            mostrar("AÇÃO", f"lendo '{primeira_linha or 'índice'}'")
            obs, resumo = atendimento.ler(primeira_linha)
            mostrar("RESULTADO", resumo)

        elif acao == "USAR":
            partes = re.match(r"^(?:[a-z0-9_]+/)?([a-z0-9_]+)\s*\|\s*(.*)$", primeira_linha)
            if not partes:
                obs, resumo = "erro: use 'USAR: <ferramenta> | <json>'.", "USAR em formato inválido"
            else:
                nome, args = partes.group(1), partes.group(2)
                mostrar("AÇÃO", f"usando '{nome}' com {args}")
                obs, resumo = atendimento.usar(nome, args, passo)
            mostrar("RESULTADO", resumo)

        else:  # PERGUNTAR
            mostrar("AÇÃO", "preciso de uma informação do funcionário")
            print(f"\nAgente: {primeira_linha}")
            resp_usuario = input("Você: ").strip()
            obs = f"resposta do funcionário: {resp_usuario}"
            resumo = f"funcionário respondeu: {resp_usuario}"

        trajetoria.append(f"Passo {passo}: {acao} -> {resumo[:150]}")
        historico += f"\n{registro}\nObservação: {obs}"

    return "Não consegui concluir a consulta. Tente reformular o pedido ou abra um chamado interno.", trajetoria
    # [ALTERAR: definir com o grupo o que acontece ao estourar o limite de passos]


if __name__ == "__main__":
    funcionario = usuario_do_ambiente()
    print(
        f"Assistente {NOME_EMPRESA} (funcionário {funcionario.id_usuario}, "
        f"{funcionario.nivel}, {funcionario.area}). Digite 'sair' para encerrar."
    )
    while True:
        pergunta = input("\nVocê: ").strip()
        if pergunta.lower() in ("sair", "exit"):
            break
        if not pergunta:
            continue
        resposta_final, trajetoria = agente(pergunta, funcionario)
        print("\n=== TRAJETÓRIA ===")
        for linha in trajetoria:
            print(" •", linha)
        print("\nAgente:", resposta_final)
