from ferramentas.base import Ferramenta


class EntregarArquivo(Ferramenta):
    nome = "entregar_arquivo"
    area = "documentos_e_agenda"
    acesso = "escrita"
    integracoes = ("anexos",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [aqui conectamos com anexos: upload do chat (Larissa e Marcelo)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = EntregarArquivo()
