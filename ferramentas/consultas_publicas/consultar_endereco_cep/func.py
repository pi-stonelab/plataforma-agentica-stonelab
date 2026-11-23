import re

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes.apis_publicas.conector import CONECTOR as APIS_PUBLICAS

PADRAO_CEP = re.compile(r"[0-9]{5}-?[0-9]{3}")


class ConsultarEnderecoCep(Ferramenta):
    nome = "consultar_endereco_cep"
    area = "consultas_publicas"
    acesso = "leitura"
    integracoes = ("apis_publicas",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("endereco_publico",)
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"cep": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        if not PADRAO_CEP.fullmatch(argumentos["cep"]):
            raise ErroFerramenta("parametro_invalido", "O cep deve ser como 01310-100.")
        endereco = APIS_PUBLICAS.endereco(argumentos["cep"].replace("-", ""))
        if endereco is None:
            raise ErroFerramenta("nao_encontrado", "CEP não encontrado.")
        return endereco


FERRAMENTA = ConsultarEnderecoCep()
