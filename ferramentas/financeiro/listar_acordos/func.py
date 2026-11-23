"""Acordos de renegociação (cobrança): de um lojista ou de todos, por situação, do maior para o menor."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta


class ListarAcordos(Ferramenta):
    nome = "listar_acordos"
    descricao_para_pessoa = "Lista os acordos de renegociação, como os que esperam a aprovação do coordenador."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cobranca",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": False},
        "situacao": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        situacao, codigo = argumentos.get("situacao"), argumentos.get("id_cliente")
        if situacao is not None and situacao not in dados_sinteticos.SITUACOES_ACORDO:
            raise ErroFerramenta(
                "parametro_invalido",
                "A situacao deve ser pendente_aprovacao, ativo, quitado, quebrado ou recusado.",
            )
        limite = lojista.limite_pedido(argumentos)
        if codigo is not None:
            lojista.exigir_acesso(usuario, codigo)
        elif lojista.carteiras_do_escopo(usuario) is not None:
            raise ErroFerramenta("parametro_invalido", "Informe o id_cliente: seu cargo não lista acordos de todos.")
        acordos, total = dados_sinteticos.buscar_acordos(codigo, situacao, limite)
        return {"acordos": acordos, "total_encontrado": total, "truncado": total > len(acordos)}


FERRAMENTA = ListarAcordos()
