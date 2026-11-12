"""Faturas vencidas de um lojista, com os dias de atraso e a soma dos valores."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ListarFaturasEmAtraso(Ferramenta):
    nome = "listar_faturas_em_atraso"
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cobranca",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        lojista.exigir_acesso(usuario, codigo)
        faturas, total, valor_total = dados_sinteticos.buscar_faturas_em_atraso(codigo)
        return {
            "codigo": codigo,
            "faturas": faturas,
            "total_encontrado": total,
            "truncado": total > len(faturas),
            "valor_total": valor_total,
        }


FERRAMENTA = ListarFaturasEmAtraso()
