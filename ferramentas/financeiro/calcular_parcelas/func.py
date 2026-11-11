from ferramentas.base import Ferramenta


class CalcularParcelas(Ferramenta):
    nome = "calcular_parcelas"
    area = "financeiro"
    acesso = "calculo"
    integracoes = ()
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ()
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: cálculo, ver agents.md]
        return super().rodar(argumentos, usuario)


FERRAMENTA = CalcularParcelas()
