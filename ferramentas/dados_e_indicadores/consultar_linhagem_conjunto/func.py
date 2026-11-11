from ferramentas.base import Ferramenta


class ConsultarLinhagemConjunto(Ferramenta):
    nome = "consultar_linhagem_conjunto"
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


FERRAMENTA = ConsultarLinhagemConjunto()
