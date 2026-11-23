"""Um chamado do lojista com o prazo do SLA e as últimas mensagens. Resumo e mensagens são de terceiros."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 5


class ConsultarChamado(Ferramenta):
    nome = "consultar_chamado"
    descricao_para_pessoa = "Mostra um chamado do lojista: situação, prazo e as últimas mensagens."
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("chamado", "interacao")
    sensibilidade = "sigilosa"
    conteudo_terceiros = True  # o resumo e as mensagens podem trazer instrução escondida (cenário 7)
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        id_chamado = argumentos["id_chamado"]
        lojista.exigir_formato_do_chamado(id_chamado)
        pedido = lojista.preparar(usuario, argumentos, limite_padrao=LIMITE_PADRAO)
        chamado = dados_sinteticos.buscar_chamado(pedido.codigo, id_chamado)
        if chamado is None:
            # Chamado de outro lojista e chamado inexistente: mesma resposta (A-15).
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado para este cliente.")
        chamado["resumo"], _ = lojista.cortar_mensagem(chamado["resumo"])
        mensagens, total = dados_sinteticos.ultimas_interacoes(pedido.codigo, id_chamado, pedido.limite)
        for mensagem in mensagens:
            mensagem["texto"], mensagem["texto_cortado"] = lojista.cortar_mensagem(mensagem["texto"])
        return {
            "codigo": pedido.codigo,
            "chamado": chamado,
            "mensagens": mensagens,
            "total_de_mensagens": total,
            "truncado": total > len(mensagens),
        }


FERRAMENTA = ConsultarChamado()
