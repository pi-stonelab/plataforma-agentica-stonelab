import re

from ferramentas import mascara
from ferramentas.base import ErroFerramenta, Ferramenta

PADRAO_NOME = re.compile(r"[a-z][a-z0-9_]{2,59}")
LIMITE_PEDIDOS = 1000
# [aqui conectamos com o back-end e o Jira: automação semanal que envia os pedidos acumulados a um card único, KAN-27]
PEDIDOS = []


class SolicitarFerramentaAusente(Ferramenta):
    nome = "solicitar_ferramenta_ausente"
    area = "plataforma"
    acesso = "escrita"
    integracoes = ()
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("pedido_plataforma",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "nome_sugerido": {"tipo": "texto", "obrigatorio": True},
        "descricao": {"tipo": "texto", "obrigatorio": True},
    }

    def rodar(self, argumentos, usuario):
        nome_sugerido, descricao = argumentos["nome_sugerido"], argumentos["descricao"]
        if not PADRAO_NOME.fullmatch(nome_sugerido) or not descricao:
            raise ErroFerramenta(
                "parametro_invalido", "Use nome_sugerido em minúsculas e descrição."
            )
        if len(PEDIDOS) >= LIMITE_PEDIDOS:
            raise ErroFerramenta("integracao_indisponivel", "A fila de pedidos está cheia.")
        descricao = mascara.mascarar_valor("texto_livre", descricao)  # MED-1: a fila vai ao Jira
        id_pedido = f"PED-{len(PEDIDOS) + 1:04d}"
        PEDIDOS.append(
            {"id_pedido": id_pedido, "nome_sugerido": nome_sugerido, "descricao": descricao}
        )
        vezes = sum(pedido["nome_sugerido"] == nome_sugerido for pedido in PEDIDOS)
        return {"id_pedido": id_pedido, "nome_sugerido": nome_sugerido, "vezes_pedida": vezes}


FERRAMENTA = SolicitarFerramentaAusente()
