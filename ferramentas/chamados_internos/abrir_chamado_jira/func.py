from ferramentas.base import Ferramenta


class AbrirChamadoJira(Ferramenta):
    nome = "abrir_chamado_jira"
    area = "chamados_internos"
    acesso = "escrita"
    integracoes = ("jira",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("chamado_interno",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "planejada"
    parametros = {}  # [preencher: parâmetros, ver agents.md]

    def rodar(self, argumentos, usuario):
        # [preencher: jira, projeto e permissões do Jira que a plataforma usa]
        return super().rodar(argumentos, usuario)


FERRAMENTA = AbrirChamadoJira()
