from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta


class ConsultarCliente(Ferramenta):
    nome = "consultar_cliente"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral",)
    sensibilidade = "pessoal"
    conteudo_terceiros = True  # o nome fantasia é texto do lojista: pode trazer instrução (E32)
    status = "ativa"
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        lojista.exigir_acesso(usuario, codigo)
        cliente = dados_sinteticos.buscar_cliente(codigo)
        if cliente is None:
            raise ErroFerramenta("nao_encontrado", "Lojista não encontrado.")
        return cliente


FERRAMENTA = ConsultarCliente()
