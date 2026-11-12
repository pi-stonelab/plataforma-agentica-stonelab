"""Agente de atendimento: um turno de conversa por chamada de `rodar_turno`.

O back-end entrega o funcionário já validado, a lista de ferramentas do agente e o `chamar_modelo`.
O agente não conhece banco, login nem a camada de acesso ao agente (`seguranca/`).
"""

import json
import logging
import os
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

from ferramentas import catalogo, governanca

load_dotenv()

logger = logging.getLogger("agente_atendimento")
logger.addHandler(logging.NullHandler())  # quem usa o agente decide para onde vão os logs

# ---------- CONFIGURAÇÃO ----------
BASE_URL = os.environ.get("LLM_URL", "https://llm.thiagomedeiros.dev")
MODELO = os.environ.get("LLM_MODELO", "qwen3.8:27b")
MAX_PASSOS = 10         # KAN-38: mais de 10 etapas sem terminar interrompe o turno
MAX_REPETICOES = 3      # KAN-38: mesma ferramenta e mesmos argumentos 3 vezes seguidas = loop
MAX_CHARS_MD = 6000     # limite de texto de cada leitura e de cada resultado enviado ao modelo
MAX_TURNOS_HISTORICO = 10  # quantos pares pergunta/resposta anteriores entram no prompt

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
# O modelo deve parar aqui, senão inventa o resultado da ferramenta. Todo `chamar_modelo` (inclusive o
# `LLMClient` do back-end) precisa passar isto como "stop" ao Ollama.
PARADA_DO_MODELO = "Observação:"

MENSAGEM_LIMITE_PASSOS = (
    f"Não consegui concluir a consulta em {MAX_PASSOS} passos. "
    "Tente reformular o pedido ou abra um chamado interno."
)
MENSAGEM_REPETICAO = (
    "Interrompi a consulta: repeti a mesma ferramenta com os mesmos dados "
    f"{MAX_REPETICOES} vezes seguidas. Tente reformular o pedido ou abra um chamado interno."
)

# Encontra a primeira ação escrita pelo modelo (ignora qualquer coisa inventada depois dela).
ACAO_RE = re.compile(r"^\s*(LER|USAR|PERGUNTAR|FINAL)\b[ \t]*:?[ \t]*", flags=re.MULTILINE)


# ---------- QUEM ESTÁ USANDO O AGENTE ----------
# [etapa B/C: trocar por busca no diretório do mock pelo ID_USUARIO]
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


# ---------- RESULTADO DE UM TURNO ----------
@dataclass
class Turno:
    """O que o back-end recebe de volta.

    tipo: "final" (resposta pronta), "pergunta" (o agente precisa de um dado do funcionário)
    ou "limite" (KAN-38: passos ou repetições estouraram; `motivo` diz qual).
    trajetoria: só ação + nome/caminho + status; nunca argumentos, dados ou textos do funcionário.
    estado: dicionário JSON para o próximo turno, depois de uma "pergunta".
    """

    resposta: str
    tipo: str
    trajetoria: list[str] = field(default_factory=list)
    estado: dict = field(default_factory=dict)
    motivo: str | None = None


# Caminho e nome só entram na trajetória e no log se tiverem a forma de um caminho do catálogo.
CAMINHO_SEGURO_RE = re.compile(r"^[a-z0-9_]+(?:/[a-z0-9_]+)?$")


# ---------- ESTADO DE UM ATENDIMENTO ----------
class Atendimento:
    def __init__(self, usuario, ferramentas_do_agente, execucao_id, agente_id, estado=None):
        self.usuario = usuario
        self.ferramentas_do_agente = tuple(ferramentas_do_agente)
        self.execucao_id = execucao_id
        self.agente_id = agente_id
        self.indice_lido = False
        self.lidas = set()          # ferramentas cuja descrição já foi lida e estava liberada
        self.caminhos_lidos = []    # os mesmos caminhos, na ordem, para guardar no estado
        self.descricoes_retomadas = []
        self._retomar(estado)

    def _retomar(self, estado):
        """Refaz as travas de um turno anterior. O estado é só uma dica: cada caminho é relido
        no catálogo, que confere de novo o que está liberado agora para este funcionário."""
        if not isinstance(estado, dict) or estado.get("indice_lido") is not True:
            return
        self.indice_lido = True
        caminhos = estado.get("ferramentas_lidas")
        for caminho in caminhos[:20] if isinstance(caminhos, list) else []:
            texto, _ = self.ler(caminho) if isinstance(caminho, str) else ("", "")
            if caminho in self.caminhos_lidos:
                self.descricoes_retomadas.append(f"[{caminho}]\n{texto}")

    def estado(self):
        return {"indice_lido": self.indice_lido, "ferramentas_lidas": list(self.caminhos_lidos)}

    def ler(self, caminho):
        caminho = caminho.strip()
        if caminho and not self.indice_lido:
            return "erro: leia primeiro o índice (LER com o caminho vazio).", "bloqueado: índice não lido"
        if caminho and not CAMINHO_SEGURO_RE.match(caminho):
            return catalogo.MENSAGEM_INDISPONIVEL, "caminho não encontrado ou não liberado"
        texto = catalogo.ler(caminho, self.usuario, self.ferramentas_do_agente)[:MAX_CHARS_MD]
        if texto == catalogo.MENSAGEM_INDISPONIVEL:
            return texto, "caminho não encontrado ou não liberado"
        if not caminho:
            self.indice_lido = True
            return texto, "índice lido"
        nome = caminho.split("/")[-1]
        liberadas = catalogo.ferramentas_liberadas(self.usuario, self.ferramentas_do_agente)
        if nome in liberadas:
            self.lidas.add(nome)
            if caminho not in self.caminhos_lidos:
                self.caminhos_lidos.append(caminho)
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

        contexto = {"agente_id": self.agente_id, "execucao_id": self.execucao_id, "passo": passo}
        resultado = catalogo.executar(nome, args, self.usuario, self.ferramentas_do_agente, contexto)
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


def chamar_llm(prompt_sistema: str, prompt: str) -> str:
    """Chamada direta ao Ollama, para o terminal. No produto quem chama é o `LLMClient` do back-end."""
    payload = {
        "model": MODELO,
        "system": prompt_sistema,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "stop": [PARADA_DO_MODELO]},
    }
    r = requests.post(
        f"{BASE_URL}/api/generate", headers=montar_headers(), json=payload, timeout=120
    )
    r.raise_for_status()
    texto = r.json()["response"]
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------- O PROMPT DO TURNO ----------
def montar_prompt(pergunta, historico, atendimento):
    """Conversa anterior + (se houver) o que já foi lido + a mensagem atual."""
    partes = []
    anteriores = [(str(p)[:MAX_CHARS_MD], str(r)[:MAX_CHARS_MD]) for p, r in historico]
    if anteriores:
        linhas = []
        for dita, respondida in anteriores[-MAX_TURNOS_HISTORICO:]:
            linhas += [f"Funcionário: {dita}", f"Assistente: {respondida}"]
        partes.append("Conversa anterior (do mais antigo ao mais recente):\n" + "\n".join(linhas))
    if atendimento.indice_lido:
        aviso = "Nota do sistema: neste atendimento você já leu o índice de áreas; não precisa relê-lo."
        if atendimento.descricoes_retomadas:
            aviso += (
                " Você também já leu as ferramentas abaixo e pode usar USAR nelas direto:\n\n"
                + "\n\n".join(atendimento.descricoes_retomadas)
            )
        partes.append(aviso)
    partes.append(f"Pergunta do funcionário: {pergunta}")
    return "\n\n".join(partes)


def _alvo_seguro(texto):
    """Caminho/nome para trajetória e log; qualquer outra coisa vira um marcador."""
    return texto if CAMINHO_SEGURO_RE.match(texto) else "<fora do padrão>"


def _assinatura(nome, argumentos_texto):
    """Identifica 'mesma ferramenta, mesmos argumentos' sem guardar nem logar o conteúdo."""
    try:
        argumentos = json.dumps(json.loads(argumentos_texto), sort_keys=True)
    except ValueError:
        argumentos = argumentos_texto.strip()
    return nome, argumentos


# ---------- O TURNO DO AGENTE ----------
class Rodada:
    """O que muda durante um turno: trajetória e contagem de repetições. Cada `tratar_*` roda
    uma ação e devolve (observação, resumo, alvo) para o passo seguinte, ou um `Turno` que encerra."""

    def __init__(self, atendimento, execucao_id, agente_id):
        self.atendimento = atendimento
        self.execucao_id = execucao_id
        self.agente_id = agente_id
        self.trajetoria = []
        self.ultima_assinatura = None
        self.repeticoes = 0

    def terminar(self, resposta, tipo, motivo=None):
        logger.info(
            "turno encerrado execucao_id=%s agente_id=%s tipo=%s motivo=%s passos=%d",
            self.execucao_id, self.agente_id, tipo, motivo, len(self.trajetoria),
        )
        return Turno(resposta, tipo, self.trajetoria, self.atendimento.estado(), motivo)

    def tratar_formato_invalido(self, passo):
        logger.info("passo=%d execucao_id=%s resposta fora do formato", passo, self.execucao_id)
        self.trajetoria.append(f"Passo {passo}: resposta fora do formato")
        return "formato inválido: use PENSAMENTO + uma das ações (LER, USAR, PERGUNTAR, FINAL)."

    def tratar_final(self, passo, final):
        if not self.atendimento.indice_lido:
            obs = "erro: antes de responder, consulte as ferramentas com LER."
            return obs, "bloqueado: FINAL sem consultar o índice", ""
        if not final:
            return "erro: FINAL vazio.", "FINAL vazio", ""
        self.trajetoria.append(f"Passo {passo}: resposta final entregue")
        logger.info("passo=%d execucao_id=%s acao=FINAL", passo, self.execucao_id)
        return self.terminar(final, "final")

    def tratar_ler(self, primeira_linha):
        obs, resumo = self.atendimento.ler(primeira_linha)
        alvo = _alvo_seguro(primeira_linha) if primeira_linha else "índice"
        return obs, resumo, alvo

    def tratar_usar(self, passo, primeira_linha):
        partes = re.match(r"^(?:[a-z0-9_]+/)?([a-z0-9_]+)\s*\|\s*(.*)$", primeira_linha)
        if not partes:
            return "erro: use 'USAR: <ferramenta> | <json>'.", "USAR em formato inválido", ""
        nome, args = partes.group(1), partes.group(2)
        if self._repetiu(nome, args) >= MAX_REPETICOES:  # KAN-38: para antes de executar a 3ª vez
            return self._parar_por_repeticao(passo, nome)
        obs, resumo = self.atendimento.usar(nome, args, passo)
        return obs, resumo, nome

    def _repetiu(self, nome, args):
        """Quantas vezes seguidas esta mesma ferramenta com os mesmos argumentos apareceu."""
        assinatura = _assinatura(nome, args)
        self.repeticoes = self.repeticoes + 1 if assinatura == self.ultima_assinatura else 1
        self.ultima_assinatura = assinatura
        return self.repeticoes

    def _parar_por_repeticao(self, passo, nome):
        self.trajetoria.append(
            f"Passo {passo}: USAR -> limite: mesma ferramenta e mesmos argumentos "
            f"{MAX_REPETICOES} vezes seguidas"
        )
        logger.warning(
            "passo=%d execucao_id=%s acao=USAR ferramenta=%s repeticao=%d",
            passo, self.execucao_id, nome, self.repeticoes,
        )
        return self.terminar(MENSAGEM_REPETICAO, "limite", "repeticao")

    def tratar_perguntar(self, passo, primeira_linha):
        """Encerra o turno; o funcionário responde no turno seguinte."""
        if not primeira_linha:
            return "erro: PERGUNTAR vazio.", "PERGUNTAR vazio", ""
        self.trajetoria.append(f"Passo {passo}: PERGUNTAR -> aguardando o funcionário")
        logger.info("passo=%d execucao_id=%s acao=PERGUNTAR", passo, self.execucao_id)
        return self.terminar(primeira_linha, "pergunta")

    def tratar(self, passo, acao, resto, primeira_linha):
        if acao == "FINAL":
            return self.tratar_final(passo, resto.strip())
        if acao == "LER":
            return self.tratar_ler(primeira_linha)
        if acao == "USAR":
            return self.tratar_usar(passo, primeira_linha)
        return self.tratar_perguntar(passo, primeira_linha)


def _separar_acao(resposta, encontro):
    """Da resposta do modelo tira (ação, resto depois dela, primeira linha do resto)."""
    resto = resposta[encontro.end():]
    primeira_linha = resto.splitlines()[0].strip() if resto.strip() else ""
    return encontro.group(1), resto, primeira_linha


def rodar_turno(
    pergunta: str,
    usuario,
    ferramentas_do_agente: Sequence[str],
    chamar_modelo: Callable[[str, str], str],
    historico: Sequence[tuple[str, str]] = (),
    estado: dict | None = None,
    contexto: dict | None = None,
    prompt_sistema: str = SISTEMA,
) -> Turno:
    """Roda um turno: até MAX_PASSOS chamadas ao modelo e devolve um `Turno`.

    `chamar_modelo(prompt_sistema, prompt)` devolve o texto do modelo. O prompt de sistema (o
    protocolo LER/USAR/PERGUNTAR/FINAL) vai a cada chamada; assim qualquer cliente de modelo serve.
    `historico`: pares (mensagem do funcionário, resposta do agente) dos turnos anteriores.
    `estado`: o `Turno.estado` do turno anterior, quando ele terminou em "pergunta"; sem ele
    (conversa nova) o agente precisa ler o índice e as ferramentas de novo.
    `contexto`: pode trazer `execucao_id` (senão gera um) e `agente_id`.
    Nenhum argumento de ferramenta, dado devolvido ou texto do funcionário vai para log ou trajetória.
    """
    contexto = contexto if isinstance(contexto, dict) else {}
    execucao_id = str(contexto.get("execucao_id") or uuid.uuid4().hex)
    agente_id = str(contexto.get("agente_id") or AGENTE_ID)
    atendimento = Atendimento(usuario, ferramentas_do_agente, execucao_id, agente_id, estado)
    rodada = Rodada(atendimento, execucao_id, agente_id)
    prompt = montar_prompt(pergunta, historico, atendimento)

    for passo in range(1, MAX_PASSOS + 1):
        resposta = chamar_modelo(prompt_sistema, prompt)
        encontro = ACAO_RE.search(resposta)
        if not encontro:
            obs = rodada.tratar_formato_invalido(passo)
            prompt += f"\n{resposta}\nObservação: {obs}"
            continue

        acao, resto, primeira_linha = _separar_acao(resposta, encontro)
        saida = rodada.tratar(passo, acao, resto, primeira_linha)
        if isinstance(saida, Turno):
            return saida
        obs, resumo, alvo = saida

        logger.info(
            "passo=%d execucao_id=%s acao=%s alvo=%s resultado=%s",
            passo, execucao_id, acao, alvo or "-", resumo,
        )
        rodada.trajetoria.append(f"Passo {passo}: {acao} -> {resumo[:150]}")
        # Guarda no prompt só até o fim da ação (descarta qualquer coisa inventada depois).
        registro = resposta[: encontro.end()] + (resto if acao == "FINAL" else primeira_linha)
        prompt += f"\n{registro}\nObservação: {obs}"

    return rodada.terminar(MENSAGEM_LIMITE_PASSOS, "limite", "max_passos")


def agente(
    pergunta, usuario, chamar_modelo=chamar_llm, ferramentas_do_agente=FERRAMENTAS_DO_AGENTE,
    prompt_sistema=SISTEMA,
):
    """Um turno sem histórico, para o terminal e os testes. Devolve (resposta, trajetoria)."""
    turno = rodar_turno(
        pergunta, usuario, ferramentas_do_agente, chamar_modelo, prompt_sistema=prompt_sistema
    )
    return turno.resposta, turno.trajetoria


# ---------- MODO TERMINAL ----------
def conversar_no_terminal(funcionario):
    """Conversa de teste: aqui sim se usa input(); a resposta do funcionário vira o próximo turno."""
    historico = []
    while True:
        mensagem = input("\nVocê: ").strip()
        if mensagem.lower() in ("sair", "exit"):
            break
        if not mensagem:
            continue
        estado, contexto = None, {"execucao_id": uuid.uuid4().hex}
        while True:
            turno = rodar_turno(
                mensagem, funcionario, FERRAMENTAS_DO_AGENTE, chamar_llm, historico, estado, contexto
            )
            print("\n=== TRAJETÓRIA ===")
            for linha in turno.trajetoria:
                print(" •", linha)
            print("\nAgente:", turno.resposta)
            historico.append((mensagem, turno.resposta))
            if turno.tipo != "pergunta":
                break
            mensagem, estado = input("\nVocê: ").strip(), turno.estado
            contexto = {"execucao_id": uuid.uuid4().hex}


if __name__ == "__main__":
    if os.environ.get("MODO_TERMINAL") != "1":  # O12
        raise SystemExit("Modo terminal desligado. Defina MODO_TERMINAL=1 para usar.")
    logging.basicConfig(level=logging.INFO, format="  [%(levelname)s] %(message)s")
    funcionario = usuario_do_ambiente()
    print(
        f"Assistente {NOME_EMPRESA} (funcionário {funcionario.id_usuario}, "
        f"{funcionario.nivel}, {funcionario.area}). Digite 'sair' para encerrar."
    )
    conversar_no_terminal(funcionario)
