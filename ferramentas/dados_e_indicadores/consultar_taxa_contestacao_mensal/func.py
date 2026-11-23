"""Taxa de chargeback da Stone por mês, somando todos os lojistas (indicador agregado da base analítica)."""

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.indicadores import PADRAO_MES, mes_menos, meses_entre

MESES_PADRAO = 6
MESES_MAXIMOS = 24


class ConsultarTaxaContestacaoMensal(Ferramenta):
    nome = "consultar_taxa_contestacao_mensal"
    descricao_para_pessoa = "Mostra a taxa de chargeback da Stone mês a mês e se passou do limite do monitoramento."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N2"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "mes_inicio": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
        "mes_fim": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
    }

    def rodar(self, argumentos, usuario):
        fim = argumentos.get("mes_fim", dados_sinteticos.HOJE_DO_MOCK.strftime("%Y-%m"))
        inicio = argumentos.get("mes_inicio", mes_menos(fim, MESES_PADRAO - 1) if PADRAO_MES.fullmatch(fim) else fim)
        if not (PADRAO_MES.fullmatch(inicio) and PADRAO_MES.fullmatch(fim)):
            raise ErroFerramenta("parametro_invalido", "Use o mês no formato AAAA-MM, como 2026-09.")
        meses = meses_entre(inicio, fim)
        if meses < 1:
            raise ErroFerramenta("parametro_invalido", "O mes_inicio deve ser igual ou anterior ao mes_fim.")
        if meses > MESES_MAXIMOS:
            raise ErroFerramenta("parametro_invalido", f"O período pode ter no máximo {MESES_MAXIMOS} meses.")
        resposta = dados_sinteticos.contestacoes_por_mes(inicio, fim)
        return {
            "mes_inicio": inicio,
            "mes_fim": fim,
            "data_corte": resposta["data_corte"],
            "meses": resposta["itens"],
            "limite_de_monitoramento": dados_sinteticos.percentual(dados_sinteticos.LIMITE_DE_CHARGEBACK_DO_MONITORAMENTO),
        }


FERRAMENTA = ConsultarTaxaContestacaoMensal()
