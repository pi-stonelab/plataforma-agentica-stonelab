"""Taxa de chargeback da Stone por mês, somando todos os lojistas (indicador agregado da base analítica)."""

from ferramentas import dados_sinteticos
from ferramentas.base import Ferramenta
from ferramentas.indicadores import periodo_em_meses

MESES_PADRAO = 6
MESES_MAXIMOS = 24


def tendencia_da_taxa(meses):
    """"subindo", "caindo" ou "estavel", comparando o último mês com o primeiro que tem taxa. Sem dois, None."""
    taxas = [mes["taxa_chargeback_percentual"] for mes in meses if mes["taxa_chargeback_percentual"] is not None]
    if len(taxas) < 2 or taxas[-1] == taxas[0]:
        return None if len(taxas) < 2 else "estavel"
    return "subindo" if taxas[-1] > taxas[0] else "caindo"


class ConsultarTaxaContestacaoMensal(Ferramenta):
    nome = "consultar_taxa_contestacao_mensal"
    descricao_para_pessoa = "Mostra a taxa de chargeback da Stone mês a mês e se ela está subindo ou caindo."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N2"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("tendencia",)
    parametros = {
        "mes_inicio": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
        "mes_fim": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
    }

    def rodar(self, argumentos, usuario):
        inicio, fim = periodo_em_meses(argumentos, MESES_PADRAO, MESES_MAXIMOS)
        resposta = dados_sinteticos.contestacoes_por_mes(inicio, fim)
        return {
            "mes_inicio": inicio,
            "mes_fim": fim,
            "data_corte": resposta["data_corte"],
            "meses": resposta["itens"],
            "tendencia": tendencia_da_taxa(resposta["itens"]),
        }


FERRAMENTA = ConsultarTaxaContestacaoMensal()
