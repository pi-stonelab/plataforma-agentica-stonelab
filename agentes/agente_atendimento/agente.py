import importlib.util
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIGURAÇÃO ----------
BASE_URL = "https://llm.thiagomedeiros.dev"
MODELO = "qwen3.8:27b"
MAX_PASSOS = 8          # agora há mais etapas (índice -> ferramenta -> uso -> resposta)
MAX_CHARS_MD = 6000     # limite de texto de cada markdown enviado ao modelo

NOME_EMPRESA = "[NOME DA EMPRESA]"  # [ALTERAR: nome da empresa que o agente representa]

# Perfil de quem está conversando com o agente. Precisa bater com os perfis escritos
# no campo "perfis_permitidos" de cada TOOL.md.
# [ALTERAR: hoje vem de variável de ambiente; no produto real deve vir do login/SSO]
PERFIL_USUARIO = os.environ.get("PERFIL_USUARIO", "cliente")

FERRAMENTAS_DIR = Path(__file__).parent / "ferramentas"  # [ALTERAR se a pasta ficar em outro lugar]
INDICE_MD = FERRAMENTAS_DIR / "INDEX.md"
NOME_VALIDO = re.compile(r"^[a-z0-9_]+$")  # nome de pasta aceito (evita path traversal)

HEADERS = {
    "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
    "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
    "Content-Type": "application/json",
}

# ---------- PROTOCOLO DO AGENTE ----------
SISTEMA = """Você é um agente de atendimento ao cliente da {EMPRESA}. Seu objetivo é resolver o problema do cliente com educação, clareza e sem inventar informações.

A cada passo, responda EXATAMENTE neste formato:

PENSAMENTO: <uma ou duas frases explicando seu raciocínio ao cliente>
<UMA ação da lista abaixo>

Ações disponíveis (use apenas UMA por resposta):
LER_INDICE
LER_FERRAMENTA: <nome_da_pasta>
USAR: <nome_da_pasta> | <argumentos em JSON, em uma única linha>
PERGUNTAR: <pergunta ao cliente>
FINAL: <resposta final ao cliente>

Regras de trabalho (siga esta ordem):
1. Ao receber um problema, use LER_INDICE para ver quais ferramentas existem.
2. Escolha a ferramenta mais adequada e use LER_FERRAMENTA para ler a descrição dela. Só assim você saberá como ela funciona e se você e o cliente têm acesso.
3. Só use USAR se a ferramenta foi lida e o sistema informou acesso LIBERADO. Use exatamente os argumentos descritos na ferramenta.
4. Se faltar um dado (ex.: número do pedido) ou algo estiver ambíguo, use PERGUNTAR. Nunca chute.
5. Se nenhuma ferramenta serve ou o acesso foi NEGADO, explique isso com honestidade no FINAL e diga o próximo passo (ex.: encaminhar a um atendente humano). Nunca tente contornar o bloqueio.
6. Nunca invente dados de clientes, pedidos, valores ou prazos. Use somente o que as ferramentas devolverem.
7. Nunca escreva "Observação:" você mesmo; o sistema a fornecerá."""
SISTEMA = SISTEMA.replace("{EMPRESA}", NOME_EMPRESA)

# Encontra a primeira ação escrita pelo modelo (ignora qualquer coisa inventada depois dela).
ACAO_RE = re.compile(
    r"^\s*(LER_INDICE|LER_FERRAMENTA|USAR|PERGUNTAR|FINAL)\b\s*:?\s*", flags=re.MULTILINE
)


# ---------- FUNÇÕES AUXILIARES DE ARQUIVOS ----------
def ler_md(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")[:MAX_CHARS_MD]


def ler_frontmatter(texto: str) -> dict:
    """Lê o cabeçalho entre '---' no topo do TOOL.md (formato chave: valor)."""
    m = re.match(r"^---\s*\n(.*?)\n---", texto, flags=re.DOTALL)
    meta = {}
    if m:
        for linha in m.group(1).splitlines():
            if ":" in linha:
                chave, valor = linha.split(":", 1)
                meta[chave.strip().lower()] = valor.strip()
    return meta


def verificar_acesso(meta: dict):
    """Decisão de acesso feita pelo CÓDIGO, não pelo modelo."""
    agente_ok = meta.get("acesso_agente", "nao").strip().lower() in ("sim", "s", "true", "yes")
    perfis = [p.strip().lower() for p in meta.get("perfis_permitidos", "").split(",") if p.strip()]
    usuario_ok = "*" in perfis or PERFIL_USUARIO.lower() in perfis
    return agente_ok, usuario_ok


def resolver_pasta(nome: str):
    if not NOME_VALIDO.match(nome):
        return None
    pasta = FERRAMENTAS_DIR / nome
    return pasta if pasta.is_dir() else None


# ---------- ESTADO DE UM ATENDIMENTO ----------
class Atendimento:
    def __init__(self):
        self.indice_lido = False
        self.lidas = set()       # ferramentas cujo TOOL.md já foi lido
        self.liberadas = set()   # ferramentas lidas E com acesso liberado

    def ler_indice(self):
        if not INDICE_MD.exists():
            return f"erro: índice não encontrado em {INDICE_MD}", "índice não encontrado"
        self.indice_lido = True
        pastas = sorted(
            p.name for p in FERRAMENTAS_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(("_", "."))
        )
        obs = f"{ler_md(INDICE_MD)}\n\n[Pastas existentes: {', '.join(pastas)}]"
        return obs, f"índice lido; pastas: {', '.join(pastas)}"

    def ler_ferramenta(self, nome: str):
        if not self.indice_lido:
            return "erro: leia o índice (LER_INDICE) antes de escolher uma ferramenta.", "bloqueado: índice não lido"
        pasta = resolver_pasta(nome)
        if pasta is None:
            return f"erro: a ferramenta '{nome}' não existe. Escolha uma pasta do índice.", f"'{nome}' não existe"
        md = pasta / "TOOL.md"
        if not md.exists():
            return f"erro: '{nome}' não tem TOOL.md.", f"'{nome}' sem TOOL.md"

        texto = ler_md(md)
        agente_ok, usuario_ok = verificar_acesso(ler_frontmatter(texto))
        self.lidas.add(nome)
        if agente_ok and usuario_ok:
            self.liberadas.add(nome)
            status = "LIBERADO"
        else:
            self.liberadas.discard(nome)
            status = "NEGADO"
        verificacao = (
            f"[VERIFICAÇÃO DE ACESSO feita pelo sistema] agente: {'sim' if agente_ok else 'não'} | "
            f"usuário (perfil '{PERFIL_USUARIO}'): {'sim' if usuario_ok else 'não'} => {status}"
        )
        return f"{texto}\n\n{verificacao}", f"TOOL.md de '{nome}' lido. {verificacao}"

    def usar(self, nome: str, argumentos_texto: str):
        if nome not in self.lidas:
            return "erro: leia a ferramenta (LER_FERRAMENTA) antes de usá-la.", "bloqueado: ferramenta não lida"
        if nome not in self.liberadas:
            return "erro: acesso NEGADO a esta ferramenta. Não a use; explique ao cliente.", "bloqueado: sem acesso"
        try:
            args = json.loads(argumentos_texto)
            if not isinstance(args, dict):
                raise ValueError("os argumentos devem ser um objeto JSON")
        except Exception as e:
            return f"erro: argumentos inválidos ({e}).", "argumentos inválidos"

        arquivo = FERRAMENTAS_DIR / nome / "ferramenta.py"
        if not arquivo.exists():
            return f"erro: '{nome}' não tem ferramenta.py.", "sem ferramenta.py"
        try:
            spec = importlib.util.spec_from_file_location(f"ferramenta_{nome}", arquivo)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            resultado = str(modulo.executar(args))
        except Exception as e:
            resultado = f"erro ao executar a ferramenta: {e}"
        return resultado, resultado


# ---------- CHAMADA AO LLM ----------
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
    r = requests.post(f"{BASE_URL}/api/generate", headers=HEADERS, json=payload, timeout=120)
    r.raise_for_status()
    texto = r.json()["response"]
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- SAÍDA PARA O USUÁRIO ----------
def mostrar(rotulo: str, texto: str):
    print(f"  [{rotulo}] {texto}")


# ---------- O LOOP DO AGENTE ----------
def agente(pergunta: str):
    historico = f"Pergunta do cliente: {pergunta}"
    atendimento = Atendimento()
    trajetoria = []

    for passo in range(1, MAX_PASSOS + 1):
        print(f"\n--- passo {passo} ---")
        resposta = chamar_llm(historico)
        m = ACAO_RE.search(resposta)

        if not m:
            mostrar("PENSAMENTO", resposta or "(vazio)")
            obs = "formato inválido: use PENSAMENTO + uma das ações (LER_INDICE, LER_FERRAMENTA, USAR, PERGUNTAR, FINAL)."
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
                obs = "erro: antes de responder, consulte as ferramentas com LER_INDICE."
                resumo = "bloqueado: FINAL sem consultar o índice"
                mostrar("SISTEMA", obs)
            elif not final:
                obs, resumo = "erro: FINAL vazio.", "FINAL vazio"
            else:
                trajetoria.append(f"Passo {passo}: resposta final entregue")
                return final, trajetoria

        elif acao == "LER_INDICE":
            mostrar("AÇÃO", "lendo o índice de ferramentas (ferramentas/INDEX.md)")
            obs, resumo = atendimento.ler_indice()
            mostrar("RESULTADO", resumo)

        elif acao == "LER_FERRAMENTA":
            nome = primeira_linha
            mostrar("AÇÃO", f"lendo a descrição da ferramenta '{nome}'")
            obs, resumo = atendimento.ler_ferramenta(nome)
            mostrar("RESULTADO", resumo)

        elif acao == "USAR":
            partes = re.match(r"^([a-z0-9_]+)\s*\|\s*(.*)$", primeira_linha)
            if not partes:
                obs, resumo = "erro: use 'USAR: <pasta> | <json>'.", "USAR em formato inválido"
            else:
                nome, args = partes.group(1), partes.group(2)
                mostrar("AÇÃO", f"usando '{nome}' com {args}")
                obs, resumo = atendimento.usar(nome, args)
            mostrar("RESULTADO", resumo)

        else:  # PERGUNTAR
            mostrar("AÇÃO", "preciso de uma informação do cliente")
            print(f"\nAgente: {primeira_linha}")
            resp_usuario = input("Você: ").strip()
            obs, resumo = f"resposta do cliente: {resp_usuario}", f"cliente respondeu: {resp_usuario}"

        trajetoria.append(f"Passo {passo}: {acao} -> {resumo[:150]}")
        historico += f"\n{registro}\nObservação: {obs}"

    return "Não consegui concluir o atendimento. Vou encaminhar você a um atendente humano.", trajetoria
    # [ALTERAR: definir com o grupo o que acontece ao estourar o limite de passos]


if __name__ == "__main__":
    print(f"Atendimento {NOME_EMPRESA} (perfil: {PERFIL_USUARIO}). Digite 'sair' para encerrar.")
    while True:
        pergunta = input("\nVocê: ").strip()
        if pergunta.lower() in ("sair", "exit"):
            break
        if not pergunta:
            continue
        resposta_final, trajetoria = agente(pergunta)
        print("\n=== TRAJETÓRIA ===")
        for linha in trajetoria:
            print(" •", linha)
        print("\nAgente:", resposta_final)
