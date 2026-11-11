from ferramentas.base import Ferramenta


class EnviarAvisoTelegram(Ferramenta):
    nome = "enviar_aviso_telegram"
    area = "comunicacao"
    acesso = "escrita"
    integracoes = ("telegram",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("comunicacao",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: telegram, chats permitidos e quem dispara o aviso (Enrico)]
        return super().rodar(argumentos, usuario)


FERRAMENTA = EnviarAvisoTelegram()
