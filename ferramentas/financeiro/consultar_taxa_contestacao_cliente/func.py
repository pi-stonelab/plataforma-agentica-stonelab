"""Taxa de chargeback de UM lojista por mês e os meses acima do limite do monitoramento (DOC-MOCK §7.6)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta
from ferramentas.indicadores import periodo_em_meses

MESES_PADRAO = 6
MESES_MAXIMOS = 24


class ConsultarTaxaContestacaoCliente(Ferramenta):
    nome = "consultar_taxa_contestacao_cliente"
    descricao_para_pessoa = "Mostra, mês a mês, a taxa de chargeback do lojista e os meses acima do limite do monitoramento de risco."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("disputa",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("mes_fim", "mes_inicio", "meses_acima_do_limite")  # texto escrito pela plataforma, não pelo lojista
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "mes_inicio": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
        "mes_fim": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 7},
    }

    def rodar(self, argumentos, usuario):
        inicio, fim = periodo_em_meses(argumentos, MESES_PADRAO, MESES_MAXIMOS)
        pedido = lojista.preparar(usuario, argumentos)
        resposta = dados_sinteticos.contestacoes_do_lojista_por_mes(pedido.codigo, inicio, fim)
        meses = resposta["itens"]
        return {
            "id_cliente": pedido.codigo,
            "mes_inicio": inicio,
            "mes_fim": fim,
            "data_corte": resposta["data_corte"],
            "limite_de_monitoramento_percentual": dados_sinteticos.taxa_percentual(
                dados_sinteticos.LIMITE_DE_CHARGEBACK_DO_MONITORAMENTO),
            "meses": meses,
            "meses_acima_do_limite": [mes["mes"] for mes in meses if mes["acima_do_limite"]],
        }


FERRAMENTA = ConsultarTaxaContestacaoCliente()
