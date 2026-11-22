"""Registro dos conectores e o estado de todas as integrações (monitoramento e tela de conectores).

`estado_integracoes()` nunca leva segredo: só nome, rótulo, tipo, modo, se está configurada, a saúde e as
ferramentas do catálogo que usam a integração. Os valores do .env não aparecem em nenhum campo.
"""

import os

from ferramentas.integracoes.conector import Conector

CONECTORES = {}


def registrar(conector):
    if not isinstance(conector, Conector) or not conector.nome or conector.nome in CONECTORES:
        raise ValueError("conector inválido ou repetido")
    CONECTORES[conector.nome] = conector
    return conector


def conector(nome):
    """O conector da integração `nome`. Nome desconhecido: KeyError (erro de programação, não de uso)."""
    return CONECTORES[nome]


def nomes():
    return sorted(CONECTORES)


def _ferramentas_por_integracao():
    # Import aqui dentro: o catálogo importa as ferramentas, que importam os conectores.
    from ferramentas import catalogo

    usos = {nome: [] for nome in CONECTORES}
    for nome, ferramenta in sorted(catalogo.carregar().items()):
        for integracao in ferramenta.integracoes:
            usos.setdefault(integracao, []).append(nome)
    return usos


def estado_integracoes(ambiente=os.environ):
    """Uma linha por integração, internas primeiro.

    [A FAZER (Marcelo e Isabel, back-end, KAN-60): uma rota de leitura (sugestão: GET /integracoes) que devolve
    esta lista; o monitoramento (Enrico, KAN-38) pode ler a mesma função para alertar quando a saúde não é ok]
    """
    usos = _ferramentas_por_integracao()
    linhas = []
    for nome in sorted(CONECTORES, key=lambda n: (CONECTORES[n].tipo != "interno", n)):
        item = CONECTORES[nome]
        linhas.append(
            {
                "nome": item.nome,
                "rotulo": item.rotulo,
                "tipo": item.tipo,
                "modo": item.modo(ambiente),
                "configurado": item.configurado(ambiente),
                "saude": item.saude(ambiente),
                "ferramentas": usos.get(nome, []),
            }
        )
    return linhas


def reiniciar():
    """Zera os disjuntores de todos os conectores (testes e reinício da demo)."""
    for item in CONECTORES.values():
        item.reiniciar()
