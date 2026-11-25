"""Chargebacks e devoluções de Pix (MED) de um lojista, com prazo, documentos e valor retido (DOC-MOCK §7.6 e §7.7)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ListarContestacoesCliente(Ferramenta):
    nome = "listar_contestacoes_cliente"
    descricao_para_pessoa = "Lista os chargebacks e as devoluções de Pix do lojista, com o prazo e os documentos pedidos."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("disputa",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        pedido = lojista.preparar(usuario, argumentos)
        chargebacks, total_chargebacks = dados_sinteticos.buscar_chargebacks(pedido.codigo, pedido.limite)
        casos_pix, total_casos_pix = dados_sinteticos.buscar_casos_pix(pedido.codigo, pedido.limite)
        return {
            "id_cliente": pedido.codigo,
            "chargebacks": chargebacks,
            "total_de_chargebacks": total_chargebacks,
            "casos_pix": casos_pix,
            "total_de_casos_pix": total_casos_pix,
            "truncado": total_chargebacks > len(chargebacks) or total_casos_pix > len(casos_pix),
        }


FERRAMENTA = ListarContestacoesCliente()
