from ferramentas.base import Ferramenta


class EnviarEmail(Ferramenta):
    nome = "enviar_email"
    area = "comunicacao"
    acesso = "escrita"
    integracoes = ("google_workspace", "microsoft_365")
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("comunicacao",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: google_workspace, como a conta de cada pessoa é ligada]
        # [preencher: microsoft_365, como a conta de cada pessoa é ligada]
        return super().rodar(argumentos, usuario)


FERRAMENTA = EnviarEmail()
