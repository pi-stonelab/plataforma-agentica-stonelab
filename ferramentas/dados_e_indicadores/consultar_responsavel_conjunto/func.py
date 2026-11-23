"""Quem responde por um conjunto de dados: o sistema dono da tabela."""

from ferramentas import dicionario
from ferramentas.base import Ferramenta

ORIENTACAO = (
    "O responsável é o sistema dono da tabela: dúvidas e correções do dado vão para o time que opera esse sistema."
)


class ConsultarResponsavelConjunto(Ferramenta):
    nome = "consultar_responsavel_conjunto"
    descricao_para_pessoa = "Diz de que sistema é uma tabela de dados, para saber a quem perguntar sobre ela."
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
            "sistema": tabela["sistema"],
            "nome_do_sistema": tabela["nome_do_sistema"],
            "orientacao": ORIENTACAO,
        }


FERRAMENTA = ConsultarResponsavelConjunto()
