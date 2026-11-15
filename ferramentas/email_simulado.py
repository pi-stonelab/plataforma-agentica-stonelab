"""Caixa de saída simulada: o "provedor de e-mail" da demo. Nenhuma mensagem sai da plataforma.

Só `confirmacoes.confirmar` chega aqui, depois de a pessoa aprovar a prévia. O sistema simulado
"email" pode ser posto fora do ar como os outros (`mock.falhas.ligar("email")`).

[A FAZER (Pedro, ferramentas, Sprint 3): conectores reais do Google Workspace e do Microsoft 365 com a
mesma função `enviar`, escolhendo o provedor pela conta de cada pessoa]
"""

import threading

from mock import falhas

LIMITE_MENSAGENS = 100
ENVIADAS = []  # como a caixa de saída de um provedor de verdade: guarda a mensagem enviada
CONTADOR = {"proxima": 1}
TRAVA_DAS_MENSAGENS = threading.Lock()


def enviar(id_remetente, para, assunto, corpo):
    """Guarda a mensagem na caixa de saída simulada e devolve o id dela (como `MSG-0001`)."""
    falhas.verificar("email")
    with TRAVA_DAS_MENSAGENS:
        id_mensagem = f"MSG-{CONTADOR['proxima']:04d}"
        CONTADOR["proxima"] += 1
        ENVIADAS.append(
            {
                "id_mensagem": id_mensagem,
                "de": id_remetente,
                "para": para,
                "assunto": assunto,
                "corpo": corpo,
            }
        )
        del ENVIADAS[:-LIMITE_MENSAGENS]
    return id_mensagem


def limpar():
    """Esvazia a caixa de saída e volta a numeração ao início (testes e reinício da demo)."""
    with TRAVA_DAS_MENSAGENS:
        ENVIADAS.clear()
        CONTADOR["proxima"] = 1
