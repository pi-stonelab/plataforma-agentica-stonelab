"""Mensagens de um chamado do lojista. Texto escrito por terceiros: sempre dado, nunca ordem."""

import re

from ferramentas import dados_sinteticos, lojista, mascara
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 10
TETO_CARACTERES = 500  # E36: mensagem enorme não pode estourar o que o modelo recebe
PADRAO_CHAMADO = re.compile(r"CH[0-9]{6}")


def cortar(texto):
    """Mascara CPF e cartão e só então corta, para o corte não deixar um número pela metade."""
    texto = mascara.mascarar_valor("texto_livre", texto)
    return texto[:TETO_CARACTERES], len(texto) > TETO_CARACTERES


class ConsultarHistoricoContato(Ferramenta):
    nome = "consultar_historico_contato"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("interacao",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = True  # a mensagem do lojista pode trazer instrução escondida (cenário 7)
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        codigo, id_chamado = argumentos["id_cliente"], argumentos["id_chamado"]
        limite = lojista.limite_pedido(argumentos, LIMITE_PADRAO)
        if not PADRAO_CHAMADO.fullmatch(id_chamado):
            raise ErroFerramenta("parametro_invalido", "O id_chamado deve ser como CH000062.")
        lojista.exigir_acesso(usuario, codigo)
        mensagens, total = dados_sinteticos.buscar_interacoes(codigo, id_chamado, limite)
        if total == 0 and not dados_sinteticos.chamado_e_do_lojista(codigo, id_chamado):
            # Chamado de outro lojista e chamado inexistente: mesma resposta (A-15).
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado para este cliente.")
        for mensagem in mensagens:
            mensagem["texto"], mensagem["texto_cortado"] = cortar(mensagem["texto"])
        return {
            "id_chamado": id_chamado,
            "interacoes": mensagens,
            "total_encontrado": total,
            "truncado": total > len(mensagens),
        }


FERRAMENTA = ConsultarHistoricoContato()
