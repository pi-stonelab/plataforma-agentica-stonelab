import re

from ferramentas import dados_sinteticos, governanca
from ferramentas.base import ErroFerramenta, Ferramenta

PADRAO_ID_CLIENTE = re.compile(r"CLI-[0-9]{4}")


class ConsultarCliente(Ferramenta):
    nome = "consultar_cliente"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        id_cliente = argumentos["id_cliente"]
        if not PADRAO_ID_CLIENTE.fullmatch(id_cliente):
            raise ErroFerramenta("parametro_invalido", "O id_cliente deve ser como CLI-0001.")
        if not governanca.cliente_no_escopo(usuario, id_cliente):
            raise ErroFerramenta("permissao_negada", "Cliente fora da sua carteira.")
        # [aqui conectamos com crm: banco simulado do back-end (KAN-32, Marcelo e Isabel)]
        cliente = dados_sinteticos.buscar_cliente(id_cliente)
        if cliente is None:
            raise ErroFerramenta("nao_encontrado", "Cliente não encontrado.")
        return cliente


FERRAMENTA = ConsultarCliente()
