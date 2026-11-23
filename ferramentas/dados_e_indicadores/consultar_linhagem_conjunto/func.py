"""De onde vem um conjunto de dados e quais conjuntos derivam dele (a linhagem do dicionário)."""

from ferramentas import dicionario
from ferramentas.base import Ferramenta


class ConsultarLinhagemConjunto(Ferramenta):
    nome = "consultar_linhagem_conjunto"
    descricao_para_pessoa = "Mostra de que tabelas um dado é calculado e quais relatórios dependem dele."
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
        return {"tabela": tabela["tabela"], "origem": tabela["origem"], "derivados": tabela["derivados"]}


FERRAMENTA = ConsultarLinhagemConjunto()
