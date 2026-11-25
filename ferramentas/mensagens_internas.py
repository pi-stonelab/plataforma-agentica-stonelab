"""O que as ferramentas de escrita para colegas (Slack, Telegram e Jira) têm em comum: texto, assinatura e destino.

- O texto passa pela máscara de texto que sai da plataforma (`texto_externo`) antes da prévia, e é esse texto que
  sai: CPF, cartão, telefone e e-mail escritos na conversa não vão para o canal. Nome de pessoa e conta bancária
  não são reconhecidos; as fichas pedem para não escrevê-los, e o cartão avisa que a mensagem sai da plataforma.
- A mensagem sai assinada com o primeiro nome de quem confirmou: o bot e a conta do Jira são da plataforma, e quem
  lê precisa saber quem pediu. A assinatura já aparece na prévia.
- O destino é sempre um apelido (ou projeto) da lista do .env, sem diferença de maiúscula nem de acento
  ("Plantão" é `plantao`); fora dela, a mensagem diz quais existem. O conector confere de novo ao enviar.
"""

from ferramentas import dados_sinteticos, email_smtp
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes.conector import sem_acento
from ferramentas.mascara import mascarar_valor

TEXTO_QUE_SAI = "texto_externo"
ASSINATURA = "\n\n— {nome}, pela Plataforma Agêntica"
ASSINATURA_DO_CHAMADO = "\n\n— Pedido por {nome}, pela Plataforma Agêntica"
NOME_SEM_CADASTRO = "um funcionário"


def texto_mascarado(valor, rotulo, uma_linha=False):
    """O texto do modelo já mascarado e conferido: não vazio, sem caractere que o destino recusaria."""
    texto = mascarar_valor(TEXTO_QUE_SAI, valor)
    if not texto or not texto.strip():
        raise ErroFerramenta("parametro_invalido", f"{rotulo} não pode ficar em branco.")
    if uma_linha and not email_smtp.assunto_valido(texto):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} deve ter uma linha só.")
    if not email_smtp.corpo_valido(texto):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} tem um caractere inválido.")
    return texto


def primeiro_nome(usuario):
    """O primeiro nome de quem pediu, do diretório; sem cadastro, "um funcionário"."""
    contato = dados_sinteticos.contato_do_funcionario(usuario.id_usuario) or {}
    nome = (contato.get("nome") or "").split()
    return nome[0] if nome else NOME_SEM_CADASTRO


def assinado(texto, usuario, assinatura=ASSINATURA):
    """`texto` com a assinatura de quem pediu."""
    return texto + assinatura.format(nome=primeiro_nome(usuario))


def escolher_da_lista(valor, liberados, rotulo):
    """O item da lista do .env que casa com `valor` sem diferença de maiúscula nem de acento, na grafia da lista.

    Fora da lista: `parametro_invalido` dizendo quais existem (o modelo corrige sem adivinhar)."""
    por_chave = {sem_acento(item): item for item in liberados}
    escolhido = por_chave.get(sem_acento(valor or ""))
    if escolhido is None:
        lista = ", ".join(liberados) or "nenhum"
        raise ErroFerramenta("parametro_invalido", f"{rotulo} fora da lista desta plataforma. Liberados: {lista}.")
    return escolhido


def com_rotulo(apelido, rotulos, prefixo=""):
    """Como o cartão mostra o destino: "#plantao (Plantão de atendimento)", ou só "#plantao" sem rótulo no .env."""
    rotulo = rotulos.get(apelido)
    return f"{prefixo}{apelido} ({rotulo})" if rotulo else f"{prefixo}{apelido}"


def liberados_para_o_agente(conector, rotulo_da_lista, liberados):
    """A linha que a ficha mostra ao modelo: o que está liberado agora e se é demonstração."""
    texto = f"{rotulo_da_lista} liberados agora: {', '.join(liberados) or 'nenhum'}."
    if conector.demonstracao():
        texto += " Modo de demonstração: nada sai de verdade; diga isso ao usuário."
    return texto


def exigir_integracao(conector):
    """Integração desligada ou mal configurada: nem a prévia é montada (ela nunca poderia sair)."""
    if not conector.configurado():
        raise ErroFerramenta("integracao_indisponivel", conector.aviso_desligada())
