"""Prepara um aviso num chat interno do Telegram (lista do .env); envia só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.telegram.conector import CONECTOR as TELEGRAM
from ferramentas.integracoes.telegram.conector import (
    FONTE_REAL,
    FONTE_SIMULADA,
    TAMANHO_MAXIMO_DO_TEXTO,
)
from ferramentas.mensagens_internas import (
    assinado,
    destino_liberado,
    exigir_integracao,
    texto_mascarado,
)

TAMANHO_DO_TEXTO = TAMANHO_MAXIMO_DO_TEXTO - 96  # sobra espaço para a assinatura


class EnviarAvisoTelegram(FerramentaComConfirmacao):
    nome = "enviar_aviso_telegram"
    area = "comunicacao"
    integracoes = ("telegram",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("comunicacao_interna",)
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "chat")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Enviar aviso no Telegram"
    descricao_para_pessoa = "Prepara um aviso num chat interno do Telegram; ele só sai depois que você confirma."
    rotulos_da_previa = {"chat": "Chat", "texto": "Aviso"}
    parametros = {
        "chat": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 40},
        "texto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_TEXTO},
    }

    def montar(self, argumentos, usuario):
        exigir_integracao(TELEGRAM)
        chat = destino_liberado(argumentos["chat"], TELEGRAM.apelidos(), "Chat")
        texto = assinado(texto_mascarado(argumentos["texto"], "O texto"), usuario)
        conteudo = {"chat": chat, "texto": texto}
        return conteudo, dict(conteudo)

    def efetivar(self, conteudo, usuario):
        simulado = TELEGRAM.modo() == "simulado"
        try:
            TELEGRAM.enviar(conteudo["chat"], conteudo["texto"])
        except DestinoNaoPermitido:  # o chat saiu da lista do .env depois da prévia
            raise ErroFerramenta("parametro_invalido", "Esse chat não está mais liberado. Nada foi enviado.") from None
        return {"chat": conteudo["chat"], "fonte": FONTE_SIMULADA if simulado else FONTE_REAL}


FERRAMENTA = EnviarAvisoTelegram()
