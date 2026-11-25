"""Lê um chamado interno no Jira (projeto liberado no .env): resumo, situação, descrição e últimos comentários."""

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.mascara import mascarar_valor
from ferramentas.mensagens_internas import TEXTO_QUE_SAI, liberados_para_o_agente


def _sem_email(texto):
    """Texto que chega do Jira: e-mail, CPF, cartão e telefone mascarados antes de ir ao modelo."""
    return mascarar_valor(TEXTO_QUE_SAI, texto) if isinstance(texto, str) else texto


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

    def situacao_para_o_agente(self):
        return liberados_para_o_agente(JIRA, "Projetos", JIRA.destinos()[0])

    def rodar(self, argumentos, usuario):
        chave = JIRA.chave_para_ferramenta(argumentos["chave"])
        chamado = JIRA.chamado(chave)
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira.")
        comentarios = [{**c, "texto": _sem_email(c["texto"])} for c in chamado.get("comentarios", [])]
        return {**chamado, "resumo": _sem_email(chamado["resumo"]), "texto": _sem_email(chamado["texto"]),
                "comentarios": comentarios}


FERRAMENTA = ConsultarChamadoJira()
