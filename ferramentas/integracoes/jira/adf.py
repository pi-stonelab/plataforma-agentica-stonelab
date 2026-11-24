"""Atlassian Document Format (ADF): o formato de texto rico das descrições e comentários do Jira Cloud (API v3).

`texto_do_adf` lê o documento e devolve texto simples (parágrafos separados por linha em branco). Só o texto
de verdade entra: links, imagens, cartões e menções viram um marcador curto, nunca a URL nem o nome da pessoa. `adf_do_texto` faz o caminho
de volta para o que a plataforma escreve (parágrafos e quebras de linha, sem formatação nem link).
Formato: https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/
"""

PROFUNDIDADE_MAXIMA = 20
BLOCOS = frozenset(
    {"paragraph", "heading", "blockquote", "codeBlock", "listItem", "bulletList", "orderedList", "panel",
     "table", "tableRow", "tableCell", "tableHeader", "rule", "expand", "nestedExpand", "taskList", "taskItem",
     "decisionList", "decisionItem", "mediaSingle", "mediaGroup"}
)
MARCADORES = {
    "media": "[anexo]",
    "inlineCard": "[link]",
    "blockCard": "[link]",
    "embedCard": "[link]",
    "mention": "[menção]",  # o `text` da menção é o nome da pessoa: nome de colega não sai daqui
}


def _texto_do_no(no, profundidade, pedacos):
    if profundidade > PROFUNDIDADE_MAXIMA or not isinstance(no, dict):
        return
    tipo = no.get("type")
    atributos = no.get("attrs") if isinstance(no.get("attrs"), dict) else {}
    if tipo == "text" and isinstance(no.get("text"), str):
        pedacos.append(no["text"])
    elif tipo == "hardBreak":
        pedacos.append("\n")
    elif tipo in MARCADORES:
        pedacos.append(MARCADORES[tipo])
    elif tipo in ("emoji", "status", "date") and isinstance(atributos.get("text"), str):
        pedacos.append(atributos["text"])
    filhos = no.get("content")
    for filho in filhos if isinstance(filhos, list) else ():
        _texto_do_no(filho, profundidade + 1, pedacos)
    if tipo in BLOCOS:
        pedacos.append("\n\n")


def texto_do_adf(documento, tamanho_maximo):
    """Texto simples do documento ADF, cortado em `tamanho_maximo` (com "…" quando corta). None vira ""."""
    pedacos = []
    _texto_do_no(documento, 0, pedacos)
    linhas = "".join(pedacos).split("\n")
    texto = "\n".join(linha.rstrip() for linha in linhas)
    while "\n\n\n" in texto:
        texto = texto.replace("\n\n\n", "\n\n")
    texto = texto.strip()
    return texto if len(texto) <= tamanho_maximo else texto[: tamanho_maximo - 1].rstrip() + "…"


def adf_do_texto(texto):
    """Documento ADF com um parágrafo por bloco separado por linha em branco e `hardBreak` em cada quebra."""
    paragrafos = []
    for bloco in texto.replace("\r\n", "\n").split("\n\n"):
        linhas = bloco.split("\n")
        if not any(linha.strip() for linha in linhas):
            continue
        conteudo = []
        for indice, linha in enumerate(linhas):
            if indice:
                conteudo.append({"type": "hardBreak"})
            if linha:
                conteudo.append({"type": "text", "text": linha})
        paragrafos.append({"type": "paragraph", "content": conteudo})
    return {"type": "doc", "version": 1, "content": paragrafos}
