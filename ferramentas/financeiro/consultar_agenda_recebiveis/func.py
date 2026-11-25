"""Agenda de recebíveis de um lojista: o que vai cair (ou já caiu) por parcela, e o resumo do que está por vir."""

from datetime import timedelta

from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_MAXIMO = 30  # com 50 parcelas a resposta passa dos 6000 caracteres que o agente lê
DIAS_PADRAO_DO_PASSADO = 30  # só data_fim no passado: a agenda são os 30 dias que terminam nela


def _inicio_padrao(data_fim):
    """Sem data_inicio, a agenda começa hoje: quem pergunta pela agenda quer o que ainda vai cair."""
    hoje = dados_sinteticos.HOJE_DO_MOCK
    if data_fim is None or data_fim >= hoje:
        return hoje
    return data_fim - timedelta(days=DIAS_PADRAO_DO_PASSADO - 1)


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
        padrao = {"data_inicio": _inicio_padrao(argumentos.get("data_fim"))}
        pedido = lojista.preparar(usuario, padrao | argumentos, com_periodo=True, limite_maximo=LIMITE_MAXIMO)
        parcelas, total = dados_sinteticos.buscar_agenda(
            pedido.codigo, pedido.data_inicio, pedido.data_fim, situacao, pedido.limite
        )
        return {
            "id_cliente": pedido.codigo,
            "agenda_futura": dados_sinteticos.resumo_da_agenda(pedido.codigo),
            "parcelas": parcelas,
            "total_encontrado": total,
            "truncado": total > len(parcelas),
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConsultarAgendaRecebiveis()
