"""Simulação de antecipação de toda a agenda que dá para antecipar hoje (DOC-MOCK §7.4). Não pede nada."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta

SEM_PARCELAS = "não há parcelas futuras para antecipar"
AVISO = (
    "Só simulação: nada foi pedido nem antecipado. Quem executa a antecipação é o especialista N2, com o pedido "
    "do lojista registrado num chamado."
)


class SimularAntecipacao(Ferramenta):
    nome = "simular_antecipacao"
    descricao_para_pessoa = "Simula quanto o lojista recebe se antecipar a agenda hoje, ou diz por que não pode."
    area = "financeiro"
    acesso = "calculo"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("agenda_recebiveis",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("aviso", "data_credito", "desconto", "valor_antecipado")  # texto escrito pela plataforma, não pelo lojista
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        lojista.exigir_acesso(usuario, codigo)
        motivos = dados_sinteticos.motivos_de_recusa_da_antecipacao(codigo)
        simulacao = None if motivos else dados_sinteticos.simulacao_de_antecipacao(codigo)
        if simulacao is not None and simulacao["quantidade_de_parcelas"] == 0:
            motivos, simulacao = [SEM_PARCELAS], None
        return {
            "id_cliente": codigo,
            "pode_antecipar": simulacao is not None,
            "motivos_de_recusa": motivos,
            "simulacao": simulacao,
            "aviso": AVISO,
        }


FERRAMENTA = SimularAntecipacao()
