"""Liquidações (depósitos diários) de um lojista: valor, situação e motivo da falha."""

from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import Ferramenta


class ConsultarLiquidacoesCliente(Ferramenta):
    nome = "consultar_liquidacoes_cliente"
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("liquidacao",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        pedido = lojista.preparar(usuario, argumentos, com_periodo=True)
        liquidacoes, total = dados_sinteticos.buscar_liquidacoes(
            pedido.codigo, pedido.data_inicio, pedido.data_fim, pedido.limite
        )
        return {
            "codigo": pedido.codigo,
            "liquidacoes": liquidacoes,
            "total_encontrado": total,
            "truncado": total > len(liquidacoes),
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConsultarLiquidacoesCliente()
