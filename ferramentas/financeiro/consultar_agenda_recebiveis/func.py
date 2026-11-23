"""Agenda de recebíveis de um lojista: o que vai cair (ou já caiu) por parcela, e o resumo do que está por vir."""

from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import ErroFerramenta, Ferramenta


class ConsultarAgendaRecebiveis(Ferramenta):
    nome = "consultar_agenda_recebiveis"
    descricao_para_pessoa = "Mostra o que o lojista tem a receber, parcela por parcela, e o que está retido ou bloqueado."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("agenda_recebiveis",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "situacao": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        situacao = argumentos.get("situacao")
        if situacao is not None and situacao not in dados_sinteticos.SITUACOES_RECEBIVEL:
            raise ErroFerramenta(
                "parametro_invalido", "A situacao deve ser previsto, pago, retido, bloqueado ou antecipado."
            )
        # Sem data_inicio, a agenda começa hoje: quem pergunta pela agenda quer o que ainda vai cair.
        pedido = lojista.preparar(
            usuario, {"data_inicio": dados_sinteticos.HOJE_DO_MOCK} | argumentos, com_periodo=True
        )
        parcelas, total = dados_sinteticos.buscar_agenda(
            pedido.codigo, pedido.data_inicio, pedido.data_fim, situacao, pedido.limite
        )
        return {
            "codigo": pedido.codigo,
            "agenda_futura": dados_sinteticos.resumo_da_agenda(pedido.codigo),
            "parcelas": parcelas,
            "total_encontrado": total,
            "truncado": total > len(parcelas),
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConsultarAgendaRecebiveis()
