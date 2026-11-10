from ferramentas.base import Ferramenta


class EnviarMensagemSlack(Ferramenta):
    nome = "enviar_mensagem_slack"
    area = "comunicacao"
    acesso = "escrita"
    integracoes = ("slack",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("comunicacao",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: slack, canais permitidos]
        return super().rodar(argumentos, usuario)


FERRAMENTA = EnviarMensagemSlack()
