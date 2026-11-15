"""Lista os marcadores de pendência do repositório, agrupados por pessoa.

Formato (um só para todas as frentes; busque pelo seu nome com `grep -rn "A FAZER (Marcelo"`):

    `[A FAZER (quem, frente, card): o que fazer]`
    `[DECIDIR (quem, frente, card): o que decidir]`

Exemplo entre crases, como os dois acima, não conta como pendência. `frente` e `card` são
opcionais; `quem` pode ter várias pessoas ("Marcelo e Isabel"). O marcador pode quebrar linha num
comentário. Quem faz o item apaga o marcador no mesmo commit; ninguém apaga o
marcador de outra pessoa. O texto nunca leva dado de lojista nem segredo. O catálogo tira os
marcadores do texto que vai ao modelo (`catalogo.PADRAO_MARCADOR`).

Uso, na raiz do repositório:

    python -m ferramentas.pendencias                 # tudo, por pessoa
    python -m ferramentas.pendencias --pessoa Marcelo
    python -m ferramentas.pendencias --antigos       # quantos marcadores do formato antigo sobram
    python -m ferramentas.pendencias --salvar docs/pendencias.md
"""

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parent.parent
EXTENSOES = (".py", ".md")
PASTAS_IGNORADAS = {"__pycache__", "dados_locais", "Claude outputs", "node_modules", "venv"}
INICIO = re.compile(r"\[(A FAZER|DECIDIR) \(")
MARCADOR = re.compile(
    r"\[(?P<tipo>A FAZER|DECIDIR) \((?P<cabecalho>[^)\]]+)\): (?P<texto>[^\]]+)\]", re.DOTALL
)
ANTIGO = re.compile(r"\[(?:aqui conectamos|preencher)")
QUEBRA_DE_COMENTARIO = re.compile(r"\s*\n\s*#?\s*")


@dataclass(frozen=True)
class Pendencia:
    tipo: str
    pessoas: tuple
    frente: str
    card: str
    texto: str
    arquivo: str
    linha: int


def _arquivos(raiz):
    for arquivo in sorted(raiz.rglob("*")):
        partes = arquivo.relative_to(raiz).parts
        if any(p.startswith(".") or p in PASTAS_IGNORADAS for p in partes):
            continue
        if arquivo.suffix in EXTENSOES and arquivo.is_file():
            yield arquivo


def _pessoas(quem):
    return tuple(nome.strip() for nome in re.split(r",| e ", quem) if nome.strip())


def ler(raiz=RAIZ_DO_REPOSITORIO):
    """Devolve (pendências, fora_do_formato, antigos). `fora_do_formato` lista "arquivo:linha"."""
    pendencias, fora_do_formato, antigos = [], [], defaultdict(int)
    for arquivo in _arquivos(raiz):
        texto = arquivo.read_text("utf-8", errors="replace")
        nome = arquivo.relative_to(raiz).as_posix()
        antigos[nome] += len(ANTIGO.findall(texto))
        for inicio in INICIO.finditer(texto):
            if texto[max(inicio.start() - 1, 0)] == "`":  # exemplo de formato, não pendência
                continue
            linha = texto.count("\n", 0, inicio.start()) + 1
            achado = MARCADOR.match(texto, inicio.start())
            if achado is None:
                fora_do_formato.append(f"{nome}:{linha}")
                continue
            campos = [c.strip() for c in achado["cabecalho"].split(",")]
            quem, frente, card = (campos + ["", ""])[:3]
            if len(campos) > 3:
                frente, card = ", ".join(campos[1:-1]), campos[-1]
            corpo = QUEBRA_DE_COMENTARIO.sub(" ", achado["texto"]).strip()
            pendencias.append(Pendencia(achado["tipo"], _pessoas(quem), frente, card, corpo, nome, linha))
    return pendencias, fora_do_formato, {k: v for k, v in antigos.items() if v}


def por_pessoa(pendencias):
    grupos = defaultdict(list)
    for pendencia in pendencias:
        for pessoa in pendencia.pessoas:
            grupos[pessoa].append(pendencia)
    return dict(sorted(grupos.items()))


def em_markdown(pendencias, fora_do_formato, pessoa=None):
    linhas = ["# Pendências marcadas no código", "", "Gerado por `python -m ferramentas.pendencias`.", ""]
    grupos = por_pessoa(pendencias)
    if pessoa is not None:
        grupos = {pessoa: grupos.get(pessoa, [])}
    for nome, itens in grupos.items():
        linhas += [f"## {nome} ({len(itens)})", ""]
        for p in itens:
            origem = ", ".join(c for c in (p.frente, p.card) if c)
            cabecalho = f"{p.tipo} ({origem})" if origem else p.tipo
            linhas.append(f"- {cabecalho}: {p.texto} (`{p.arquivo}:{p.linha}`)")
        linhas.append("")
    if fora_do_formato:
        linhas += ["## Fora do formato", ""] + [f"- `{local}`" for local in fora_do_formato] + [""]
    return "\n".join(linhas)


def principal(argumentos=None):
    analisador = argparse.ArgumentParser(description="Pendências marcadas no código, por pessoa.")
    analisador.add_argument("--pessoa", help="só as pendências desta pessoa")
    analisador.add_argument("--antigos", action="store_true", help="conta os marcadores do formato antigo")
    analisador.add_argument("--salvar", help="grava o resultado em markdown (UTF-8) neste arquivo")
    escolhas = analisador.parse_args(argumentos)
    pendencias, fora_do_formato, antigos = ler()
    if escolhas.antigos:
        for nome, quantidade in sorted(antigos.items()):
            print(f"{quantidade:4d}  {nome}")
        print(f"{sum(antigos.values()):4d}  no total")
        return
    texto = em_markdown(pendencias, fora_do_formato, escolhas.pessoa)
    if escolhas.salvar:
        Path(escolhas.salvar).write_text(texto + "\n", "utf-8")
        print(f"{len(pendencias)} pendências gravadas em {escolhas.salvar}")
    else:
        print(texto)


if __name__ == "__main__":
    principal()
