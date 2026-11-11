import re

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta, Ferramenta

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
        # [aqui conectamos com apis_publicas: consulta real de CEP, hoje dados sintéticos]
        endereco = dados_sinteticos.buscar_endereco(argumentos["cep"].replace("-", ""))
        if endereco is None:
            raise ErroFerramenta("nao_encontrado", "CEP não encontrado.")
        return endereco


FERRAMENTA = ConsultarEnderecoCep()
