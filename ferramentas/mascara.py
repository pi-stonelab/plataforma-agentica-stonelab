"""Máscara de dado restrito na saída das ferramentas (DOC-MOCK §8.3). Função pura, sem I/O.

Contrato (uma fonte só, `mock/regras.py`):
- `CLASSIFICACAO_CAMPOS` diz qual máscara vale para cada NOME DE CAMPO restrito;
- `CAMPOS_NAO_RESTRITOS` lista os campos liberados;
- numa ferramenta que lê dado de lojista, texto em campo fora das duas listas sai como "***"
  (negar por padrão);
- CPF e cartão escritos no meio de qualquer texto também são mascarados (ver `_texto_livre`).
Na Sprint 2 ninguém vê o dado restrito completo (O2). Quem chama é `Ferramenta.executar`, uma vez.

Texto livre, o que vale (ALTO-1 da auditoria B):
- o texto é normalizado antes (NFKC, dígitos de outros alfabetos viram 0-9, caracteres invisíveis
  somem) e a saída sai normalizada;
- sequência de dígitos com até 4 separadores entre dois dígitos (espaço, quebra de linha, ponto,
  hífen, barra, traço longo, sublinhado) conta como um número só, sem depender de borda de palavra: letra colada
  em dígito ("cpf52998224700") também é pega;
- 11 dígitos viram CPF (`***.456.789-**`); 13 a 19, cartão (`**** **** **** 1111`); 12 dígitos ou
  mais de 19 viram `***` (na dúvida, mascara). Luhn não é usado: nunca se libera um número;
- falso positivo aceito: qualquer número de 11 dígitos (um celular, "0800 123 4567") vira CPF mascarado,
  e dois números de 8 dígitos seguidos (duas datas) viram cartão;
- o que NÃO é coberto de propósito: e-mail e telefone digitados em texto livre (DOC-MOCK §8.3 só diz
  CPF e cartão; decisão de produto pendente) e número escrito por extenso ou com letra no meio.
"""

import re
import unicodedata

from mock import regras

MASCARADO = "***"
LIMITE_PROFUNDIDADE = 8
# Um dígito, depois (até 4 separadores + um dígito) quantas vezes houver. Separador e dígito não se
# misturam, então a busca anda numa passada só (sem ReDoS), mesmo com 1 MB de dígitos e espaços.
SEQUENCIA_DE_DIGITOS = re.compile(r"\d(?:[\s./\\_\-\u2010-\u2015\u2212\u00b7]{0,4}\d)*")
CARACTERES_INVISIVEIS = re.compile(
    "[\x00-\x08\x0e-\x1f\x7f\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e"
    "\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
DIGITO_NAO_ASCII = re.compile(r"(?![0-9])\d")
# Forma de cada valor depois de mascarado: mascarar de novo devolve o mesmo valor.
JA_MASCARADO = {
    "cpf": re.compile(r"\*\*\*\.\d{3}\.\d{3}-\*\*"),
    "telefone": re.compile(r"\(\d{2}\) \*{4,5}-\d{4}"),
    "email": re.compile(r"[^@\s]\*\*\*@[^@\s]+"),
    "conta": re.compile(r"\*\*\*\d{2}"),
    "cartao": re.compile(r"\*{4} \*{4} \*{4} \d{4}"),
    "nome": re.compile(r"\S\*\*\*( \S\*\*\*)*"),
}


def _digitos(valor):
    return re.sub(r"\D", "", valor)


def _cartao_com_4_ultimos(digitos):
    return f"**** **** **** {digitos[-4:]}"


def _cpf(valor):
    digitos = _digitos(valor)
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**" if len(digitos) == 11 else MASCARADO


def _telefone(valor):
    digitos = _digitos(valor)
    if len(digitos) not in (10, 11):
        return MASCARADO
    return f"({digitos[:2]}) {'*' * (len(digitos) - 6)}-{digitos[-4:]}"


def _email(valor):
    local, arroba, dominio = valor.partition("@")
    return f"{local[0]}***@{dominio}" if local and arroba and dominio else MASCARADO


def _conta(valor):
    digitos = _digitos(valor)
    return f"***{digitos[-2:]}" if len(digitos) >= 2 else MASCARADO


def _cartao(valor):
    digitos = _digitos(valor)
    return _cartao_com_4_ultimos(digitos) if len(digitos) >= 4 else MASCARADO


def _nome(valor):
    partes = valor.split()
    return " ".join(f"{parte[0]}***" for parte in partes) if partes else MASCARADO


def _normalizar(texto):
    """NFKC, dígitos de outros alfabetos em 0-9 e sem caracteres invisíveis (zero-width e afins)."""
    if not texto.isascii():
        texto = unicodedata.normalize("NFKC", texto)
        texto = DIGITO_NAO_ASCII.sub(lambda m: str(unicodedata.decimal(m.group())), texto)
    return CARACTERES_INVISIVEIS.sub("", texto)


def _numero_no_texto(trecho):
    """Máscara de uma sequência de dígitos achada no texto, pela quantidade de dígitos."""
    digitos = _digitos(trecho)
    if len(digitos) == 11:
        return _cpf(digitos)
    if 13 <= len(digitos) <= 19:
        return _cartao_com_4_ultimos(digitos)
    if len(digitos) == 12 or len(digitos) > 19:
        return MASCARADO
    return trecho


def _texto_livre(valor):
    return SEQUENCIA_DE_DIGITOS.sub(lambda m: _numero_no_texto(m.group()), _normalizar(valor))


MASCARAS = {
    "cpf": _cpf,
    "telefone": _telefone,
    "email": _email,
    "conta": _conta,
    "cartao": _cartao,
    "nome": _nome,
    "texto_livre": _texto_livre,
}


def mascarar_valor(tipo, valor):
    """Aplica a máscara `tipo` a um valor. Tipo desconhecido ou valor estranho: tudo mascarado."""
    if valor is None:
        return None
    if tipo not in MASCARAS or not isinstance(valor, str):
        return MASCARADO
    if tipo in JA_MASCARADO and JA_MASCARADO[tipo].fullmatch(valor):
        return valor
    return MASCARAS[tipo](valor)


def _e_identificador_de_formato_fixo(campo, valor):
    """Protocolo AAAAMMDD-NNNNNN tem 14 dígitos e não é cartão: o valor inteiro tem de casar o formato."""
    formato = regras.FORMATO_DE_IDENTIFICADORES.get(campo)
    return formato is not None and re.fullmatch(formato, valor) is not None


def _valor(campo, valor, estrito, nivel):
    """Máscara de um valor que está no campo `campo` (listas herdam o campo do dono)."""
    if nivel > LIMITE_PROFUNDIDADE:
        raise ValueError("dados fundos demais")
    tipo = regras.CLASSIFICACAO_CAMPOS.get(campo)
    if isinstance(valor, dict):
        return {
            chave: _valor(str(chave), item, estrito, nivel + 1) for chave, item in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_valor(campo, item, estrito, nivel + 1) for item in valor]
    if tipo is not None:
        return mascarar_valor(tipo, valor)
    if isinstance(valor, str):
        if _e_identificador_de_formato_fixo(campo, valor):
            return valor
        liberado = campo in regras.CAMPOS_NAO_RESTRITOS
        return _texto_livre(valor) if liberado or not estrito else MASCARADO
    return valor


def mascarar(dados, categorias_dados):
    """Devolve `dados` com todo campo restrito mascarado.

    `categorias_dados` é a da ficha: só quando a ferramenta lê dado de lojista vale a regra de
    negar texto em campo não classificado.
    """
    estrito = not set(categorias_dados) <= regras.CATEGORIAS_COMUNS
    return _valor("", dados, estrito, 0)
