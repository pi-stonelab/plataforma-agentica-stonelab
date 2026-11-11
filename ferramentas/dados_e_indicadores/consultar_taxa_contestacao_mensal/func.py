from ferramentas.base import Ferramenta


class ConsultarTaxaContestacaoMensal(Ferramenta):
    nome = "consultar_taxa_contestacao_mensal"
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N2"
    areas_permitidas = ("dados", "financeiro")
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: bigquery, de onde saem os indicadores no mock (KAN-28)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = ConsultarTaxaContestacaoMensal()
