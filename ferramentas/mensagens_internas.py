"""O que as ferramentas de escrita para colegas (Slack, Telegram e Jira) têm em comum: texto e destino.

- O texto passa pela máscara de texto livre antes da prévia, e é esse texto que sai (CPF, cartão e telefone
  escritos na conversa não vão para o canal).
- Mensagem no Slack e no Telegram sai assinada com o primeiro nome de quem confirmou: o bot é da plataforma, e
  quem lê o canal precisa saber quem pediu. A assinatura já aparece na prévia.
- O destino é sempre um apelido (ou projeto) da lista do .env; fora dela, a mensagem diz quais existem.
"""

from ferramentas import dados_sinteticos, email_smtp
from ferramentas.base import ErroFerramenta
from ferramentas.mascara import mascarar_valor

LIVRE = "texto_livre"
ASSINATURA = "\n\n— {nome}, pela Plataforma Agêntica"
NOME_SEM_CADASTRO = "um funcionário"


def texto_mascarado(valor, rotulo, uma_linha=False):
    """O texto do modelo já mascarado e conferido: não vazio, sem caractere que o destino recusaria."""
    texto = mascarar_valor(LIVRE, valor)
    if not texto or not texto.strip():
        raise ErroFerramenta("parametro_invalido", f"{rotulo} não pode ficar vazio.")
    if uma_linha and not email_smtp.assunto_valido(texto):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} deve ter uma linha só.")
    if not email_smtp.corpo_valido(texto):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} tem um caractere inválido.")
    return texto


def assinado(texto, usuario):
    """`texto` com a assinatura de quem pediu (o primeiro nome do diretório)."""
    contato = dados_sinteticos.contato_do_funcionario(usuario.id_usuario) or {}
    nome = (contato.get("nome") or "").split()
    return texto + ASSINATURA.format(nome=nome[0] if nome else NOME_SEM_CADASTRO)


def destino_liberado(valor, liberados, rotulo):
    """O apelido (em minúsculas) se está na lista do .env; senão `parametro_invalido` com os liberados."""
    apelido = valor.strip().lower()
    if apelido not in liberados:
        lista = ", ".join(liberados) or "nenhum"
        raise ErroFerramenta("parametro_invalido", f"{rotulo} fora da lista desta plataforma. Liberados: {lista}.")
    return apelido


def exigir_integracao(conector):
    """Integração desligada ou mal configurada: nem a prévia é montada (ela nunca poderia sair)."""
    if not conector.configurado():
        raise ErroFerramenta("integracao_indisponivel", conector.aviso_desligada())
