from ferramentas.base import Ferramenta


class BuscarClientes(Ferramenta):
    nome = "buscar_clientes"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral", "atendimento")
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [aqui conectamos com crm: banco simulado do back-end (KAN-32, Marcelo e Isabel)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = BuscarClientes()
