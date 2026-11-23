"""Receitas, perdas e resultado da Stone num período, com as vendas por modalidade (KAN-14, caso de uso 4)."""

from ferramentas import dados_sinteticos
from ferramentas.base import Ferramenta
from ferramentas.indicadores import periodo_pedido

DIAS_PADRAO = 7
AVISO = (
    "Base analítica: os números vão até a data_corte (ontem). As vendas de hoje ficam de fora; para elas, "
    "use as consultas de vendas do lojista."
)


class ResumirReceitaPeriodo(Ferramenta):
    nome = "resumir_receita_periodo"
    descricao_para_pessoa = "Monta o resumo de receitas, perdas e resultado da Stone num período, como o relatório semanal."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        inicio, fim = periodo_pedido(argumentos, DIAS_PADRAO)
        resultado = dados_sinteticos.resumo_de_resultado(inicio, fim)
        vendas = dados_sinteticos.resumo_de_vendas(inicio, fim)
        return {
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            **resultado,
            "vendas_por_modalidade": vendas["modalidades"],
            "vendas_total": vendas["total"],
            "aviso": AVISO,
        }


FERRAMENTA = ResumirReceitaPeriodo()
