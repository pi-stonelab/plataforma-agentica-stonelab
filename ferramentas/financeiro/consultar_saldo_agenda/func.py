"""Saldo da agenda de recebíveis de um lojista: quanto ainda vai cair, por situação, sem as parcelas (DOC-MOCK §8.2)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ConsultarSaldoAgenda(Ferramenta):
    nome = "consultar_saldo_agenda"
    descricao_para_pessoa = "Mostra quanto o lojista ainda tem a receber na agenda, por situação, sem listar as parcelas."
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("saldo_agenda",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        pedido = lojista.preparar(usuario, argumentos)
        return {
            "id_cliente": pedido.codigo,
            "data_base": dados_sinteticos.HOJE_DO_MOCK.isoformat(),
            "agenda_futura": dados_sinteticos.resumo_da_agenda(pedido.codigo),
        }


FERRAMENTA = ConsultarSaldoAgenda()
