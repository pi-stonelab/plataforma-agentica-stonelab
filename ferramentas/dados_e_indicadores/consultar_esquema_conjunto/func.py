"""As colunas de um conjunto de dados (tabela), com tipo, descrição e se o dado é restrito."""

from ferramentas import dicionario
from ferramentas.base import Ferramenta


class ConsultarEsquemaConjunto(Ferramenta):
    nome = "consultar_esquema_conjunto"
    descricao_para_pessoa = "Mostra as colunas de uma tabela de dados e quais guardam dado pessoal ou restrito."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("datahub",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("metadado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"conjunto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 60}}

    def rodar(self, argumentos, usuario):
        tabela = dicionario.conjunto(argumentos["conjunto"])
        return {
            "tabela": tabela["tabela"],
            "descricao_da_tabela": tabela["descricao_da_tabela"],
            "colunas": tabela["colunas"],
        }


FERRAMENTA = ConsultarEsquemaConjunto()
