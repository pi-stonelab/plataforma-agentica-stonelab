from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 20


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
        codigo = argumentos["id_cliente"]
        data_inicio = argumentos.get("data_inicio")
        data_fim = argumentos.get("data_fim")
        limite = argumentos.get("limite", LIMITE_PADRAO)
        if not 1 <= limite <= governanca.LIMITE_LINHAS:
            raise ErroFerramenta("parametro_invalido", "O limite deve ficar entre 1 e 50.")
        if data_inicio and data_fim and data_inicio > data_fim:
            raise ErroFerramenta("parametro_invalido", "A data_inicio vem depois da data_fim.")
        lojista.exigir_acesso(usuario, codigo)
        data_inicio, data_fim = lojista.periodo_permitido(usuario, data_inicio, data_fim)
        if dados_sinteticos.buscar_cliente(codigo) is None:
            raise ErroFerramenta("nao_encontrado", "Lojista não encontrado.")
        vendas, total = dados_sinteticos.buscar_transacoes(codigo, data_inicio, data_fim, limite)
        return {
            "codigo": codigo,
            "transacoes": vendas,
            "total_encontrado": total,
            "truncado": total > len(vendas),
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConsultarTransacoesCliente()
