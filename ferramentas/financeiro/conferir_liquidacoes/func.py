"""Confere, dia a dia, se cada liquidação pagou o que a agenda mandava (KAN-14, caso de uso 5)."""

from datetime import timedelta

from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import Ferramenta

DIAS_PADRAO = 30
LIMITE_PADRAO = 20
EXPLICACAO = {  # só o que a conferência enxerga (agenda x depósito do dia); a causa é de quem investiga
    "falhou": "A liquidação do dia falhou. O motivo está em motivo_falha; veja o chamado de Recebimento ligado antes de explicar ao lojista.",
    "devolvida": "A liquidação do dia aparece como devolvida. Veja o chamado de Recebimento ligado antes de explicar a causa ao lojista.",
    "sem_liquidacao": "A agenda mandava pagar neste dia, mas não houve liquidação.",
    "abaixo": "O depósito veio abaixo da agenda. Esta conferência não olha descontos do dia: abra um chamado de Recebimento para o financeiro conferir.",
    "acima": "O depósito veio acima da agenda. Abra um chamado de Recebimento para o financeiro conferir.",
}


def _divergencia(dia):
    """O item da divergência do dia, ou None se o dia bateu."""
    if dia["falhou"]:
        situacao = "falhou"
    elif dia["devolvida"]:
        situacao = "devolvida"
    elif dia["pago_centavos"] == dia["agenda_centavos"]:
        return None
    elif dia["pago_centavos"] == 0:
        situacao = "sem_liquidacao"
    else:
        situacao = "paga"
    chave = situacao if situacao != "paga" else ("abaixo" if dia["pago_centavos"] < dia["agenda_centavos"] else "acima")
    return {
        "data": dia["dia"],
        "agenda": dados_sinteticos.reais(dia["agenda_centavos"]),
        "pago": dados_sinteticos.reais(dia["pago_centavos"]),
        "diferenca": dados_sinteticos.reais(dia["pago_centavos"] - dia["agenda_centavos"]),
        "situacao": situacao,
        "motivo_falha": dia["motivo_falha"],
        "explicacao": EXPLICACAO[chave],
    }


class ConferirLiquidacoes(Ferramenta):
    nome = "conferir_liquidacoes"
    descricao_para_pessoa = "Confere se cada depósito do lojista pagou o que a agenda mandava e aponta as diferenças."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("agenda_recebiveis", "liquidacao")
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("agenda", "diferenca", "explicacao", "pago")  # texto escrito pela plataforma, não pelo lojista
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        fim = argumentos.get("data_fim", dados_sinteticos.HOJE_DO_MOCK - timedelta(days=1))
        padrao = {"data_inicio": fim - timedelta(days=DIAS_PADRAO - 1), "data_fim": fim}  # o padrão parte da data_fim
        pedido = lojista.preparar(usuario, padrao | argumentos, com_periodo=True, limite_padrao=LIMITE_PADRAO)
        dias = dados_sinteticos.agenda_e_liquidacoes_por_dia(pedido.codigo, pedido.data_inicio, pedido.data_fim)
        divergencias = [item for item in map(_divergencia, dias) if item is not None]
        return {
            "id_cliente": pedido.codigo,
            "dias_conferidos": len(dias),
            "divergencias": divergencias[: pedido.limite],
            "total_encontrado": len(divergencias),
            "truncado": len(divergencias) > pedido.limite,
            "janela_dias": governanca.janela_dias(usuario),
        }


FERRAMENTA = ConferirLiquidacoes()
