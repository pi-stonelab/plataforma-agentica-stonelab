import re

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes.apis_publicas.conector import CONECTOR as APIS_PUBLICAS

PADRAO_CEP_ENTRADA = re.compile(r"[0-9]{2}\.?[0-9]{3}-?[0-9]{3}")  # 01310-100, 01310100 ou 01.310-100


def _com_hifen(cep):
    return f"{cep[:5]}-{cep[5:]}"


def _mensagem_nao_encontrado():
    if APIS_PUBLICAS.modo() != "simulado":
        return "CEP não encontrado."
    exemplos = [_com_hifen(cep) for cep in sorted(dados_sinteticos.ENDERECOS)]
    return f"No modo de demonstração só há os CEPs {', '.join(exemplos[:-1])} e {exemplos[-1]}."


class ConsultarEnderecoCep(Ferramenta):
    nome = "consultar_endereco_cep"
    area = "consultas_publicas"
    acesso = "leitura"
    integracoes = ("apis_publicas",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("endereco_publico",)
    sensibilidade = "publica"
    conteudo_terceiros = True  # logradouro e bairro vêm de um serviço de fora (ViaCEP): dado, não instrução
    status = "ativa"
    descricao_para_pessoa = "Mostra a rua, o bairro e a cidade de um CEP."
    parametros = {"cep": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        if not PADRAO_CEP_ENTRADA.fullmatch(argumentos["cep"].strip()):
            raise ErroFerramenta("parametro_invalido", "Use o CEP com 8 dígitos, como 01310-100.")
        digitos = re.sub(r"[.-]", "", argumentos["cep"].strip())
        endereco = APIS_PUBLICAS.endereco(digitos)
        if endereco is None:
            raise ErroFerramenta("nao_encontrado", _mensagem_nao_encontrado())
        return {**endereco, "cep": _com_hifen(endereco["cep"])}


FERRAMENTA = ConsultarEnderecoCep()
