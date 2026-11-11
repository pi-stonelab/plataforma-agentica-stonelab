from ferramentas.base import Ferramenta


class ResumirReceitaPeriodo(Ferramenta):
    nome = "resumir_receita_periodo"
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N1"
    areas_permitidas = ("dados", "financeiro")
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: bigquery, de onde saem os indicadores no mock (KAN-28)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = ResumirReceitaPeriodo()
