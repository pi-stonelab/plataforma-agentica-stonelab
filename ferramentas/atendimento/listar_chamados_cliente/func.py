"""Chamados de um lojista (sem o texto das mensagens): categoria, prioridade, situação e idade."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ListarChamadosCliente(Ferramenta):
    nome = "listar_chamados_cliente"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("chamado",)
    sensibilidade = "pessoal"
    conteudo_terceiros = (
        False  # só códigos e listas fechadas; o resumo e as mensagens ficam de fora
    )
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        pedido = lojista.preparar(usuario, argumentos)
        chamados, total = dados_sinteticos.buscar_chamados(pedido.codigo, pedido.limite)
        return {
            "codigo": pedido.codigo,
            "chamados": chamados,
            "total_encontrado": total,
            "truncado": total > len(chamados),
        }


FERRAMENTA = ListarChamadosCliente()
