import importlib
import re
from pathlib import Path
from time import monotonic

from ferramentas import governanca
from ferramentas.base import montar_registro, resposta

NOME_ARQUIVO_INSTRUCOES = "agents.md"
MENSAGEM_INDISPONIVEL = "Caminho não encontrado ou não liberado para você."
RAIZ = Path(__file__).parent
PADRAO_MARCADOR = re.compile(r"\s*\[(?:aqui conectamos|preencher)[^\]]*\]")
PADRAO_TITULO_VAZIO = re.compile(r"^## .*\n\s*(?=^## |\Z)", re.MULTILINE)
FERRAMENTAS = {}


def carregar():
    """Importa as func.py uma vez e devolve {nome: ferramenta}."""
    if not FERRAMENTAS:
        for arquivo in sorted(RAIZ.glob("*/*/func.py")):
            area, nome = arquivo.parts[-3], arquivo.parts[-2]
            modulo = importlib.import_module(f"ferramentas.{area}.{nome}.func")
            FERRAMENTAS[modulo.FERRAMENTA.nome] = modulo.FERRAMENTA
    return FERRAMENTAS


def _buscar(nome):
    return carregar().get(nome) if isinstance(nome, str) else None


def _camada_bloqueio(nome, usuario, ferramentas_do_agente):
    ferramenta = _buscar(nome)
    if ferramenta is None:
        return "desconhecida"
    permitidas = (
        ferramentas_do_agente if isinstance(ferramentas_do_agente, (tuple, list, set)) else ()
    )
    if nome not in permitidas:
        return "agente"
    if governanca.motivo_bloqueio(ferramenta, usuario) is not None:
        return "usuario"
    return None if ferramenta.esta_ativa() else "inativa"


def ferramentas_liberadas(usuario, ferramentas_do_agente):
    # [aqui conectamos com agentes: lista de ferramentas da configuração do agente, KAN-55]
    camadas = {n: _camada_bloqueio(n, usuario, ferramentas_do_agente) for n in carregar()}
    return sorted(nome for nome, camada in camadas.items() if camada is None)


def _ler_arquivo(pasta):
    return (pasta / NOME_ARQUIVO_INSTRUCOES).read_text("utf-8").split("## Para quem mantém")[0]


def _primeira_frase(pasta):
    """Primeira frase do primeiro parágrafo depois do título, usada nas listas."""
    try:
        texto = _ler_arquivo(pasta)
    except OSError:
        return ""
    paragrafos = [p for p in texto.split("\n\n") if p.strip() and not p.startswith("#")]
    if not paragrafos:
        return ""
    paragrafo = " ".join(paragrafos[0].split())
    return re.split(r"(?<=\.)\s", paragrafo)[0]


def _lista(pasta, titulo, itens):
    """Troca o corpo da seção `## titulo` pela lista dos itens liberados."""
    linhas = "\n".join(f"- `{nome}`: {_primeira_frase(destino)}" for nome, destino in itens)
    padrao = re.compile(rf"(## {titulo}\n).*?(?=\n## |\Z)", re.DOTALL)
    return padrao.sub(lambda m: f"{m.group(1)}\n{linhas}\n", _ler_arquivo(pasta))


def _texto_do_caminho(caminho, liberadas):
    """Texto do nível pedido; ValueError se o caminho não existe ou não está liberado."""
    ferramentas = carregar()
    areas = sorted({ferramentas[n].area for n in liberadas})
    if caminho == "":
        return _lista(RAIZ, "Áreas", [(a, RAIZ / a) for a in areas])
    if caminho in areas:
        itens = [(n, RAIZ / caminho / n) for n in liberadas if ferramentas[n].area == caminho]
        return _lista(RAIZ / caminho, "Ferramentas", itens)
    nome = caminho.split("/")[-1]
    if nome in liberadas:
        area = ferramentas[nome].area
        if caminho in (nome, f"{area}/{nome}"):
            return _ler_arquivo(RAIZ / area / nome)
    raise ValueError


def ler(caminho, usuario, ferramentas_do_agente):
    """Texto para o modelo: raiz (""), área ou ferramenta, só com o que está liberado."""
    liberadas = ferramentas_liberadas(usuario, ferramentas_do_agente)
    try:
        texto = _texto_do_caminho(str(caminho).strip(), liberadas)
    except (OSError, ValueError):
        return MENSAGEM_INDISPONIVEL
    texto = PADRAO_TITULO_VAZIO.sub("", PADRAO_MARCADOR.sub("", texto))
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def executar(nome, argumentos, usuario, ferramentas_do_agente, contexto=None):
    """Roda a ferramenta se ela está liberada; senão responde como se não existisse."""
    camada = _camada_bloqueio(nome, usuario, ferramentas_do_agente)
    if camada is None:
        return carregar()[nome].executar(argumentos, usuario, contexto)
    resultado = resposta("erro", None, "Ferramenta não encontrada.", "ferramenta_inexistente")
    registro = montar_registro(_buscar(nome), usuario, contexto, resultado, camada, monotonic())
    governanca.registrar(registro)
    return resultado
