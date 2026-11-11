from ferramentas.base import Ferramenta


class ListarFaturasEmAtraso(Ferramenta):
    nome = "listar_faturas_em_atraso"
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("financeiro",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [aqui conectamos com sql: banco simulado do back-end (KAN-32, Marcelo e Isabel)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = ListarFaturasEmAtraso()
