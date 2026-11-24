"""Leitura do dicionário de dados do mock (o DataHub simulado): tabelas, colunas, sistema dono e origem.

Só descreve o esquema, nunca lê dado. As quatro ferramentas do DataHub usam estas funções.
"""

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta


def conjuntos():
    """As tabelas do mock, cada uma com o nome do sistema dono e quem deriva dela."""
    tabelas = dados_sinteticos.dicionario_de_dados()
    derivados = {}
    for tabela in tabelas:
        for origem in tabela["origem"]:
            derivados.setdefault(origem, []).append(tabela["tabela"])
    return [
        tabela
        | {
            "nome_do_sistema": dados_sinteticos.DESCRICAO_DOS_SISTEMAS.get(tabela["sistema"], tabela["sistema"]),
            "derivados": sorted(derivados.get(tabela["tabela"], [])),
        }
        for tabela in tabelas
    ]


def conjunto(nome):
    """A tabela pelo nome exato; `nao_encontrado` se não existe."""
    for tabela in conjuntos():
        if tabela["tabela"] == nome:
            return tabela
    raise ErroFerramenta("nao_encontrado", "Conjunto de dados não encontrado. Use buscar_conjuntos_dados para achar o nome.")
