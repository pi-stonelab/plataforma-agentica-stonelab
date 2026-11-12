from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import ErroFerramenta, Ferramenta


class ConsultarTransacoesCliente(Ferramenta):
    nome = "consultar_transacoes_cliente"
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("venda",)
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
        if dados_sinteticos.buscar_cliente(pedido.codigo) is None:
            raise ErroFerramenta("nao_encontrado", "Lojista não encontrado.")
        vendas, total = dados_sinteticos.buscar_transacoes(
            pedido.codigo, pedido.data_inicio, pedido.data_fim, pedido.limite
        )
        return {
            "codigo": pedido.codigo,
            "transacoes": vendas,
            "total_encontrado": total,
            "truncado": total > len(vendas),
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConsultarTransacoesCliente()
