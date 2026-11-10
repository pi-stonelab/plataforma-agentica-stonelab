from ferramentas.base import Ferramenta


class ConsultarCotacaoMoeda(Ferramenta):
    nome = "consultar_cotacao_moeda"
    area = "consultas_publicas"
    acesso = "leitura"
    integracoes = ("apis_publicas",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("cambio",)
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: apis_publicas, quais APIs, por exemplo CEP e câmbio]
        return super().rodar(argumentos, usuario)


FERRAMENTA = ConsultarCotacaoMoeda()
