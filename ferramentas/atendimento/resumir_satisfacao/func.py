"""Notas e comentários da pesquisa de satisfação (CSAT) no período. Comentário é texto do lojista."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 10
NOTAS = range(1, 6)


class ResumirSatisfacao(Ferramenta):
    nome = "resumir_satisfacao"
    descricao_para_pessoa = "Resume as notas e os comentários da pesquisa de satisfação dos lojistas."
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("satisfacao",)
    sensibilidade = "pessoal"
    conteudo_terceiros = True  # o comentário pode trazer instrução escondida (E32)
    status = "ativa"
    parametros = {
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "fila": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "nota_maxima": {"tipo": "inteiro", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        data_inicio, data_fim = argumentos.get("data_inicio"), argumentos.get("data_fim")
        fila, nota_maxima = argumentos.get("fila"), argumentos.get("nota_maxima")
        limite = lojista.limite_pedido(argumentos, LIMITE_PADRAO)
        lojista.conferir_ordem_das_datas(data_inicio, data_fim)
        if fila is not None and fila not in dados_sinteticos.FILAS:
            raise ErroFerramenta("parametro_invalido", "A fila deve ser varejo, pme, contas_chave ou ouvidoria.")
        if nota_maxima is not None and nota_maxima not in NOTAS:
            raise ErroFerramenta("parametro_invalido", "A nota_maxima deve ficar entre 1 e 5.")
        carteira = _carteira_do_recorte(usuario)
        resumo = dados_sinteticos.resumo_satisfacao(data_inicio, data_fim, fila, carteira=carteira)
        comentarios, total = dados_sinteticos.buscar_comentarios_satisfacao(
            data_inicio, data_fim, fila, nota_maxima, limite, carteira=carteira
        )
        for comentario in comentarios:
            comentario["comentario"], _ = lojista.cortar_mensagem(comentario["comentario"])
        return {
            "resumo": resumo,
            "comentarios": comentarios,
            "total_encontrado": total,
            "truncado": total > len(comentarios),
        }


def _carteira_do_recorte(usuario):
    """Quem vê todas as carteiras lê tudo (None). Quem vê só o time precisa de uma carteira só: a consulta de
    satisfação recorta por uma. Hoje só cargos com todas as carteiras têm a categoria `satisfacao`."""
    carteiras = lojista.carteiras_do_escopo(usuario)
    if carteiras is None:
        return None
    if len(carteiras) == 1:
        return carteiras[0]
    raise ErroFerramenta("permissao_negada", "Seu cargo não lê a satisfação de mais de uma carteira.")


FERRAMENTA = ResumirSatisfacao()
