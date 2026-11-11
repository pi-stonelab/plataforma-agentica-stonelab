from ferramentas.base import Ferramenta


class CriarEventoAgenda(Ferramenta):
    nome = "criar_evento_agenda"
    area = "documentos_e_agenda"
    acesso = "escrita"
    integracoes = ("google_workspace", "microsoft_365")
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("agenda",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: google_workspace, como a conta de cada pessoa é ligada]
        # [preencher: microsoft_365, como a conta de cada pessoa é ligada]
        return super().rodar(argumentos, usuario)


FERRAMENTA = CriarEventoAgenda()
