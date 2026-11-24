"""Prepara uma mensagem num canal interno do Slack (lista do .env); publica só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.slack.conector import CONECTOR as SLACK
from ferramentas.integracoes.slack.conector import (
    FONTE_REAL,
    FONTE_SIMULADA,
    TAMANHO_MAXIMO_DO_TEXTO,
)
from ferramentas.mensagens_internas import (
    assinado,
    com_rotulo,
    escolher_da_lista,
    exigir_integracao,
    liberados_para_o_agente,
    texto_mascarado,
)

TAMANHO_DO_TEXTO = TAMANHO_MAXIMO_DO_TEXTO - 100  # sobra espaço para a assinatura


class EnviarMensagemSlack(FerramentaComConfirmacao):
    nome = "enviar_mensagem_slack"
    area = "comunicacao"
    integracoes = ("slack",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("comunicacao_interna",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    sai_da_plataforma = True
    titulo = "Enviar mensagem no Slack"
    descricao_para_pessoa = "Prepara uma mensagem num canal interno do Slack; ela só sai depois que você confirma."
    rotulos_da_previa = {"canal": "Canal (Slack)", "texto": "Mensagem"}
    parametros = {
        "canal": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 40},
        "texto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_TEXTO},
    }

    def situacao_para_o_agente(self):
        return liberados_para_o_agente(SLACK, "Canais", SLACK.apelidos())

    def montar(self, argumentos, usuario):
        exigir_integracao(SLACK)
        canal = escolher_da_lista(argumentos["canal"], SLACK.apelidos(), "Canal")
        texto = assinado(texto_mascarado(argumentos["texto"], "O texto"), usuario)
        conteudo = {"canal": canal, "texto": texto}
        previa = {"canal": com_rotulo(canal, SLACK.rotulos(), "#"), "texto": texto}
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        fonte = _fonte()
        try:
            # O `ts` do Slack não volta: não serve a quem confirmou, e a máscara o leria como número de cartão.
            SLACK.publicar(conteudo["canal"], conteudo["texto"])
        except DestinoNaoPermitido:  # o canal saiu da lista do .env depois da prévia
            raise ErroFerramenta("parametro_invalido", "Esse canal não está mais liberado. Nada foi enviado.") from None
        return {"canal": conteudo["canal"], "fonte": fonte}

    def mensagem_ao_confirmar(self, dados):
        frase = f"Mensagem publicada em #{dados['canal']} (Slack)."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if dados["fonte"] == FONTE_SIMULADA else frase


def _fonte():
    return FONTE_SIMULADA if SLACK.demonstracao() else FONTE_REAL


FERRAMENTA = EnviarMensagemSlack()
