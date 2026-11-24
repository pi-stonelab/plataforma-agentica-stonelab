"""Fila de chamados abertos de quem pergunta, pelo prazo: os atrasados primeiro (sem o texto das mensagens)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ListarMeusChamados(Ferramenta):
    nome = "listar_meus_chamados"
    descricao_para_pessoa = (
        "Lista os chamados abertos que estão com você, do prazo mais curto para o mais longo, com lojista, categoria, "
        "prioridade, situação e se o prazo já estourou."
    )
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("chamado",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False  # só códigos e listas fechadas; o resumo e as mensagens ficam de fora
    status = "ativa"
    parametros = {"limite": {"tipo": "inteiro", "obrigatorio": False}}

    def rodar(self, argumentos, usuario):
        limite = lojista.limite_pedido(argumentos)
        chamados, total = dados_sinteticos.buscar_chamados_do_responsavel(
            usuario.id_usuario, lojista.carteiras_do_escopo(usuario), limite
        )
        for chamado in chamados:
            chamado["id_cliente"] = chamado.pop("id_lojista")  # o nome que o modelo vê
        return {
            "chamados": chamados,
            "total_encontrado": total,
            "truncado": total > len(chamados),
            "atrasados": sum(1 for chamado in chamados if chamado["prazo_estourado"]),
        }


FERRAMENTA = ListarMeusChamados()
