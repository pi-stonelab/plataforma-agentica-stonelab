"""Lê um chamado interno no Jira (projeto liberado no .env): resumo, situação, descrição e últimos comentários."""

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA


class ConsultarChamadoJira(Ferramenta):
    nome = "consultar_chamado_jira"
    area = "chamados_internos"
    acesso = "leitura"
    integracoes = ("jira",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("chamado_interno",)
    sensibilidade = "interna"
    conteudo_terceiros = True
    status = "ativa"
    descricao_para_pessoa = "Mostra um chamado interno do Jira: situação, descrição e os últimos comentários."
    parametros = {"chave": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 20}}

    def rodar(self, argumentos, usuario):
        chave = JIRA.chave_para_ferramenta(argumentos["chave"])
        chamado = JIRA.chamado(chave)
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira.")
        return chamado


FERRAMENTA = ConsultarChamadoJira()
