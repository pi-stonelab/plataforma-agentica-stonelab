"""Máscara de dado restrito na saída das ferramentas (DOC-MOCK §8.3). Função pura, sem I/O.

Contrato (uma fonte só, `mock/regras.py`):
- `CLASSIFICACAO_CAMPOS` diz qual máscara vale para cada NOME DE CAMPO restrito;
- `CAMPOS_NAO_RESTRITOS` lista os campos liberados para todas as ferramentas;
- `campos_liberados` da ficha libera campos só para aquela ferramenta (assunto e corpo do enviar_email);
- numa ferramenta que lê dado de lojista, texto em campo fora das duas listas sai como "***"
  (negar por padrão);
- CPF e cartão escritos no meio de qualquer texto também são mascarados (ver `_texto_livre`).
Na Sprint 2 ninguém vê o dado restrito completo (O2). Quem chama é `Ferramenta.executar`, uma vez.

Texto livre, o que vale (ALTO-1 da auditoria B, MED-1 da C):
- o texto é normalizado antes (NFKC, dígitos de outros alfabetos viram 0-9, caracteres invisíveis
  somem, inclusive seletor de variação, acento combinante, keycap e caracteres tag) e sai normalizado;
- sequência de dígitos com até 8 separadores entre dois dígitos conta como um número só, sem borda de
  palavra ("cpf52998224700" também é pega). Separador: espaço, quebra de linha, `. , : ; / \\ | _ * ~`,
  hífens e travessões, bullet, aspas, parênteses, colchetes, `<`, `>` ou tag HTML curta (cada tag vale 1);
- antes da regra por quantidade de dígitos, dois formatos inequívocos ganham a máscara do próprio tipo (revisão de
  usuário do bloco B, 22/11): telefone com DDD entre parênteses ou com +55 ("(21) 99999-8888", "+55 21 99999-8888")
  vira `(21) *****-8888`, como o campo `telefone`; CNPJ com pontos e barra ("12.345.678/0001-90") vira
  `**.***.***/**01-90`, que mostra os mesmos 4 dígitos que a máscara de cartão mostraria. Qualquer outra forma
  cai na regra abaixo;
- 11 dígitos viram CPF (`***.456.789-**`); 13 a 19, cartão (`**** **** **** 1111`); 12 dígitos ou
  mais de 19 viram `***` (na dúvida, mascara). Luhn não é usado: nunca se libera um número;
- exceção (revisão do bloco E1, 23/11): 11 dígitos SEM a pontuação de CPF que começam por um DDD que existe e
  têm 9 no terceiro dígito ("21998765432") têm cara de celular e ganham a máscara de telefone
  (`(21) *****-5432`), para o cartão de confirmação não mostrar um telefone com cara de CPF. Um CPF que
  calhe de ter esse formato também sai mascarado (os 4 últimos dígitos em vez dos 6 do meio);
- falsos positivos aceitos, do lado seguro: número de 11 dígitos sem cara de celular ("0800 123 4567")
  vira CPF, duas datas
  seguidas viram cartão, e `, : ;` juntam o que o autor separou ("14:30:00 15/10/2026"). Não são texto livre,
  então não mascaram: o campo `protocolo` (AAAAMMDD-NNNNNN) e os campos de valor em reais (`valor`,
  `valor_bruto`, `valor_liquido`, `valor_total`), desde que o valor inteiro tenha o formato esperado;
- NFKC troca caracteres de compatibilidade em todo texto livre: "1º" vira "1o", "m²" vira "m2", "½" vira
  "1⁄2", "™" vira "TM"; ZWJ/ZWNJ somem (emoji de família vira três emojis). Aceito: o sentido se mantém;
- e-mail em texto livre: só no tipo `texto_externo`, o texto que SAI da plataforma (Slack, Telegram, Jira) ou que
  CHEGA de fora (Jira, caixa de e-mail): `joao.silva@exemplo.example` vira `j***@exemplo.example`, como o campo `email`
  (decisão do orquestrador em 23/11, sem fonte, para o Brenno validar). O `texto_livre` de sempre não mexe em
  e-mail: o DOC-MOCK §8.3 só fala de CPF e cartão;
- NÃO coberto de propósito: telefone sem DDD, nome de pessoa e conta bancária no meio do texto (não há como
  reconhecer sem errar muito; as fichas que mandam texto para fora pedem para não escrevê-los) e número por
  extenso ou com letra no meio;
- risco residual aceito: o mesmo número escrito pelo lojista como CPF numa mensagem e como telefone em outra
  mostra partes diferentes em cada uma. Só o próprio autor controla o formato do que escreve;
- LIMITAÇÃO CONHECIDA: número dividido entre duas mensagens ou dois campos ("CPF 111.444" e "777-00")
  sai igual em cada pedaço, porque a máscara vê um texto por vez. Só um filtro de saída na resposta
  final (KAN-63) resolve; esta máscara não tenta.
"""

import re
import unicodedata

from mock import regras

MASCARADO = "***"
LIMITE_PROFUNDIDADE = 8
LIMITE_DE_SEPARADORES = 8
TAG_HTML_CURTA = r"</?[A-Za-z][A-Za-z0-9]{0,9}/?>"
CARACTERES_SEPARADORES = (
    r"\s.,:;/\\|_*~'\"()\[\]<>"
    r"\-\u2010-\u2015\u2212\u00b7\u2022\u2023\u2043\u2219\u22c5"
    r"\u2018-\u201f\u00ab\u00bb"
)
# Um dígito, depois (até 8 separadores + um dígito) quantas vezes houver. Separador e dígito não se
# misturam (e a tag começa por "<", que só pode ser tag se a letra seguinte casar), então a busca anda
# numa passada só (sem ReDoS), mesmo com 1 MB de dígitos e separadores.
SEQUENCIA_DE_DIGITOS = re.compile(
    rf"\d(?:(?:{TAG_HTML_CURTA}|[{CARACTERES_SEPARADORES}]){{0,{LIMITE_DE_SEPARADORES}}}\d)*"
)
CARACTERES_INVISIVEIS = re.compile(
    "[\x00-\x08\x0e-\x1f\x7f\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e"
    "\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff"
    "\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe00-\ufe0f\ufe20-\ufe2f"
    "\U000e0000-\U000e007f]"
)
# Campos de valor em reais não são texto livre: "R$ 12.345.678.900,00" tem 13 dígitos e não é cartão.
FORMATO_DE_CAMPOS_DE_VALOR = re.compile(r"R\$ \d{1,3}(?:\.\d{3})*,\d{2}")
CAMPOS_DE_VALOR = frozenset({"valor", "valor_bruto", "valor_liquido", "valor_total"})
DIGITO_NAO_ASCII = re.compile(r"(?![0-9])\d")
# Formatos inequívocos, procurados antes da regra por quantidade de dígitos (ver o topo do arquivo).
TELEFONE_NO_TEXTO = re.compile(
    r"(?<![\d+])(?P<pais>\+55[ ]?)?\((?P<ddd>\d{2})\)[ ]?(?P<meio>9?\d{4})[- ]?(?P<fim>\d{4})(?!\d)"
    r"|(?<![\d+])(?P<pais2>\+55[ ]?)(?P<ddd2>\d{2})[ ]?(?P<meio2>9?\d{4})[- ]?(?P<fim2>\d{4})(?!\d)"
)
CNPJ_NO_TEXTO = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")
# Limites em cada pedaço: a busca anda numa passada só, sem ReDoS, mesmo num texto grande.
EMAIL_NO_TEXTO = re.compile(r"(?<![\w.+-])[\w.%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}")
DDDS = frozenset(
    {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46,
     47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85,
     86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99}
)
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


def _cara_de_celular(trecho, digitos):
    """11 dígitos sem a pontuação de CPF, com DDD que existe e 9 no terceiro dígito (ver o topo do arquivo)."""
    return "." not in trecho and int(digitos[:2]) in DDDS and digitos[2] == "9"


def _numero_no_texto(trecho):
    """Máscara de uma sequência de dígitos achada no texto, pela quantidade de dígitos."""
    digitos = _digitos(trecho)
    if len(digitos) == 11 and _cara_de_celular(trecho, digitos):
        return _telefone(digitos)
    if len(digitos) == 11:
        return _cpf(digitos)
    if 13 <= len(digitos) <= 19:
        return _cartao_com_4_ultimos(digitos)
    if len(digitos) == 12 or len(digitos) > 19:
        return MASCARADO
    return trecho


def _telefone_no_texto(achado):
    pais = achado.group("pais") or achado.group("pais2") or ""
    ddd = achado.group("ddd") or achado.group("ddd2")
    meio = achado.group("meio") or achado.group("meio2")
    fim = achado.group("fim") or achado.group("fim2")
    return f"{pais}({ddd}) {'*' * len(meio)}-{fim}"


def _cnpj_no_texto(achado):
    digitos = _digitos(achado.group())
    return f"**.***.***/**{digitos[10:12]}-{digitos[12:]}"


def _texto_livre(valor):
    texto = _normalizar(valor)
    texto = TELEFONE_NO_TEXTO.sub(_telefone_no_texto, texto)
    texto = CNPJ_NO_TEXTO.sub(_cnpj_no_texto, texto)
    return SEQUENCIA_DE_DIGITOS.sub(lambda m: _numero_no_texto(m.group()), texto)


def _texto_externo(valor):
    """Texto livre que sai da plataforma ou chega de fora: o `texto_livre` e, antes, o e-mail no meio do texto."""
    texto = EMAIL_NO_TEXTO.sub(lambda m: _email(m.group()), _normalizar(valor))
    return _texto_livre(texto)


MASCARAS = {
    "cpf": _cpf,
    "telefone": _telefone,
    "email": _email,
    "conta": _conta,
    "cartao": _cartao,
    "nome": _nome,
    "texto_livre": _texto_livre,
    "texto_externo": _texto_externo,
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


def _e_valor_em_reais(campo, valor):
    """Valor em reais no padrão "R$ 1.842,30", em campo de valor: o valor inteiro tem de casar o formato."""
    return campo in CAMPOS_DE_VALOR and FORMATO_DE_CAMPOS_DE_VALOR.fullmatch(valor) is not None


def _valor(campo, valor, estrito, nivel, liberados):
    """Máscara de um valor que está no campo `campo` (listas herdam o campo do dono)."""
    if nivel > LIMITE_PROFUNDIDADE:
        raise ValueError("dados fundos demais")
    tipo = regras.CLASSIFICACAO_CAMPOS.get(campo)
    if isinstance(valor, dict):
        return {
            chave: _valor(str(chave), item, estrito, nivel + 1, liberados) for chave, item in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_valor(campo, item, estrito, nivel + 1, liberados) for item in valor]
    if tipo is not None:
        return mascarar_valor(tipo, valor)
    if isinstance(valor, str):
        if _e_identificador_de_formato_fixo(campo, valor) or _e_valor_em_reais(campo, valor):
            return valor
        liberado = campo in regras.CAMPOS_NAO_RESTRITOS or campo in liberados
        return _texto_livre(valor) if liberado or not estrito else MASCARADO
    return valor


def mascarar(dados, categorias_dados, campos_liberados=()):
    """Devolve `dados` com todo campo restrito mascarado.

    `categorias_dados` é a da ficha: só quando a ferramenta lê dado de lojista vale a regra de
    negar texto em campo não classificado. `campos_liberados` também é da ficha: campos de texto
    que só aquela ferramenta devolve e que passam pela máscara de texto livre em vez de virar "***".
    """
    estrito = not set(categorias_dados) <= regras.CATEGORIAS_COMUNS
    return _valor("", dados, estrito, 0, frozenset(campos_liberados))
