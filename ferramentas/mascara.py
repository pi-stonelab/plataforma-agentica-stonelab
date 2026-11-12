"""Máscara de dado restrito na saída das ferramentas (DOC-MOCK §8.3). Função pura, sem I/O.

Contrato (uma fonte só, `mock/regras.py`):
- `CLASSIFICACAO_CAMPOS` diz qual máscara vale para cada NOME DE CAMPO restrito;
- `CAMPOS_NAO_RESTRITOS` lista os campos liberados;
- numa ferramenta que lê dado de lojista, texto em campo fora das duas listas sai como "***"
  (negar por padrão);
- CPF e cartão escritos no meio de qualquer texto também são mascarados.
Na Sprint 2 ninguém vê o dado restrito completo (O2). Quem chama é `Ferramenta.executar`, uma vez.
"""

import re

from mock import regras

MASCARADO = "***"
LIMITE_PROFUNDIDADE = 8
CPF_NO_TEXTO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CARTAO_NO_TEXTO = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
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


def _texto_livre(valor):
    valor = CARTAO_NO_TEXTO.sub(lambda m: _cartao_com_4_ultimos(_digitos(m.group())), valor)
    return CPF_NO_TEXTO.sub(lambda m: _cpf(m.group()), valor)


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
