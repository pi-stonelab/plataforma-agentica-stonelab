from ferramentas.base import Ferramenta


class BuscarConjuntosDados(Ferramenta):
    nome = "buscar_conjuntos_dados"
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("datahub",)
    nivel_minimo = "N1"
    areas_permitidas = ("dados", "financeiro")
    categorias_dados = ("metadado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: datahub, catálogo simulado de conjuntos de dados (KAN-28)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = BuscarConjuntosDados()
