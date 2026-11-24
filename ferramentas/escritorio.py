"""O que as ferramentas de agenda, planilha e documento (`documentos_e_agenda/`) têm em comum.

- A conta: Google Workspace ou Microsoft 365. A ficha lista as duas como alternativas; a ferramenta usa a que está
  ligada e a que a pessoa conectou. Se a pessoa tem as duas, o agente pergunta e repete com o parâmetro `servico`.
- Validação do que o modelo manda (id de arquivo, intervalo, células) e máscara do texto que sai ou chega.
- `EscritaDeEscritorio`: a base das três ferramentas de escrita (prévia, confirmação e só então a ação), com o aviso
  de demonstração olhando só a conta que vai agir.
"""

import re

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import (
    AVISO_DE_CONTA_DA_PESSOA,
    AVISO_DE_DEMONSTRACAO,
    FerramentaComConfirmacao,
)
from ferramentas.integracoes import conector
from ferramentas.integracoes.conector import sem_acento
from ferramentas.integracoes.escritorio import PADRAO_ID_ARQUIVO, PADRAO_INTERVALO
from ferramentas.mascara import mascarar_valor
from ferramentas.mensagens_internas import TEXTO_QUE_SAI

INTEGRACOES = ("google_workspace", "microsoft_365")
APELIDOS_DAS_CONTAS = {
    "google": "google_workspace",
    "google_workspace": "google_workspace",
    "microsoft": "microsoft_365",
    "microsoft_365": "microsoft_365",
}
TAMANHO_DO_ID_OU_LINK = 300  # o id tem até 128; o link do Google que a pessoa cola é mais longo
PARAMETRO_SERVICO = {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 30}
SEPARADOR_DE_CELULAS = "|"
CELULAS_NO_MAXIMO = 20
TAMANHO_DA_CELULA = 200
MENSAGEM_SEM_CONTA_LIGADA = (
    "Esta pessoa ainda não ligou a conta Google nem a Microsoft. Avise o usuário para conectar uma delas na tela de "
    "integrações e não tente de novo."
)
MENSAGEM_DUAS_CONTAS = (
    "Esta pessoa ligou as duas contas (Google e Microsoft). Pergunte qual usar e repita com servico=google ou "
    "servico=microsoft."
)
MENSAGEM_NENHUMA_LIGADA = "Nenhuma conta de escritório (Google ou Microsoft) está ligada nesta plataforma."


def conector_da_conta(apelido):
    """O conector que o `servico` do modelo nomeia ("google", "microsoft"). Desconhecido: `parametro_invalido`."""
    nome = APELIDOS_DAS_CONTAS.get(sem_acento(apelido or "").replace(" ", "_"))
    if nome is None:
        raise ErroFerramenta("parametro_invalido", "O parâmetro servico deve ser google ou microsoft.")
    return conector(nome)


def conector_da_pessoa(usuario, servico=None):
    """O conector (Google ou Microsoft) que `usuario` usa agora.

    Com `servico`, esse mesmo. Sem ele: o único ligado na plataforma; havendo os dois, o que a pessoa conectou;
    nenhum ou os dois conectados, `ErroFerramenta` com o que o agente deve fazer."""
    if servico:
        escolhido = conector_da_conta(servico)
        if not escolhido.configurado():
            raise ErroFerramenta("integracao_indisponivel", escolhido.aviso_desligada())
        return escolhido
    ligados = [c for c in (conector(n) for n in INTEGRACOES) if c.configurado()]
    if not ligados:
        raise ErroFerramenta("integracao_indisponivel", MENSAGEM_NENHUMA_LIGADA)
    if len(ligados) == 1:
        return ligados[0]
    com_conta = [c for c in ligados if c.conta_ligada(usuario.id_usuario)]
    if len(com_conta) == 1:
        return com_conta[0]
    raise ErroFerramenta(
        "integracao_indisponivel" if not com_conta else "parametro_invalido",
        MENSAGEM_SEM_CONTA_LIGADA if not com_conta else MENSAGEM_DUAS_CONTAS,
    )


def situacao_das_contas():
    """A linha da ficha: quais contas a plataforma tem ligadas e se alguma é demonstração."""
    ligados = [c for c in (conector(n) for n in INTEGRACOES) if c.configurado()]
    texto = f"Contas liberadas agora: {', '.join(c.rotulo for c in ligados) or 'nenhuma'}."
    if any(c.demonstracao() for c in ligados):
        texto += " Modo de demonstração: dados de exemplo, nada sai de verdade; diga isso ao usuário."
    return texto


LINK_DO_GOOGLE = re.compile(
    r"https://(?:docs|drive)\.google\.com/(?:(?:document|spreadsheets|presentation|file)/(?:u/\d/)?d/|open\?id=)"
    r"(?P<id>[A-Za-z0-9_-]{10,128})(?:[/?#&]\S*)?"
)


def exigir_id_de_arquivo(texto):
    """O id do arquivo como o Google ou a Microsoft o escrevem (letras, números, `-`, `_` e `!`). Aceita também o link
    do Google que a pessoa colou (o id sai da URL); link da Microsoft não traz o id, então a pessoa usa a busca."""
    texto = texto.strip()
    if (achado := LINK_DO_GOOGLE.fullmatch(texto)) is not None:
        texto = achado.group("id")
    if not PADRAO_ID_ARQUIVO.fullmatch(texto):
        raise ErroFerramenta("parametro_invalido", "O id_arquivo deve ser o id que buscar_arquivos devolveu ou o link do arquivo no Google.")
    return texto


def exigir_intervalo(texto):
    """"a1:f20" -> "A1:F20". Fora do formato: `parametro_invalido`."""
    if texto is None:
        return None
    if not PADRAO_INTERVALO.fullmatch(texto):
        raise ErroFerramenta("parametro_invalido", "O intervalo deve ter o formato A1:F20.")
    return texto.upper()


def plural(quantidade, palavra):
    """"1 linha", "2 linhas"."""
    return f"{quantidade} {palavra}" if quantidade == 1 else f"{quantidade} {palavra}s"


def exigir_limite(valor, padrao, maximo):
    limite = padrao if valor is None else valor
    if not 1 <= limite <= maximo:
        raise ErroFerramenta("parametro_invalido", f"O limite deve ficar entre 1 e {maximo}.")
    return limite


def exigir_uma_linha(texto, rotulo):
    """Texto de uma linha só e não vazio, já mascarado (CPF, cartão, telefone e e-mail no meio do texto)."""
    mascarado = mascarar_valor(TEXTO_QUE_SAI, texto)
    if not mascarado.strip() or "\n" in mascarado or "\r" in mascarado:
        raise ErroFerramenta("parametro_invalido", f"{rotulo} deve ter uma linha só e não pode ficar em branco.")
    return mascarado.strip()


def mascarar_celula(texto):
    """O texto de uma célula que sai ou chega: mascarado e cortado no tamanho de uma célula."""
    return mascarar_valor(TEXTO_QUE_SAI, texto)[:TAMANHO_DA_CELULA]


def celulas_de(texto, rotulo):
    """"a | b | c" -> ["a", "b", "c"], cada célula mascarada. Vazio, célula demais ou longa demais: `parametro_invalido`."""
    if any(ord(caractere) < 32 for caractere in texto):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} deve ser um texto de uma linha só.")
    celulas = [celula.strip() for celula in texto.split(SEPARADOR_DE_CELULAS)]
    if not any(celulas):
        raise ErroFerramenta("parametro_invalido", f"{rotulo} não pode ficar em branco.")
    if len(celulas) > CELULAS_NO_MAXIMO or any(len(celula) > TAMANHO_DA_CELULA for celula in celulas):
        raise ErroFerramenta(
            "parametro_invalido",
            f"{rotulo} aceita até {CELULAS_NO_MAXIMO} células de até {TAMANHO_DA_CELULA} caracteres, separadas por {SEPARADOR_DE_CELULAS}.",
        )
    return [mascarar_celula(celula) for celula in celulas]


def linhas_de(texto, rotulo, maximo):
    """Uma linha de células por quebra de linha. Mais que `maximo` linhas: `parametro_invalido`."""
    brutas = [linha for linha in re.split(r"\r?\n", texto) if linha.strip()]
    if len(brutas) > maximo:
        raise ErroFerramenta("parametro_invalido", f"{rotulo} aceita até {maximo} linhas.")
    return [celulas_de(linha, rotulo) for linha in brutas]


class EscritaDeEscritorio(FerramentaComConfirmacao):
    """Base das ferramentas que escrevem na agenda ou nas planilhas da conta da pessoa."""

    integracoes = INTEGRACOES
    integracoes_alternativas = True
    areas_permitidas = ("todas",)
    nivel_minimo = "N1"
    sensibilidade = "interna"
    sai_da_plataforma = True
    aviso_de_saida = AVISO_DE_CONTA_DA_PESSOA
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "servico")  # "conta" é campo de banco: mascarado

    def situacao_para_o_agente(self):
        return situacao_das_contas()

    def texto_do_campo(self, campo, valor):
        """Linha de planilha no cartão: células separadas por " | " e uma linha por linha (cada célula já mascarada)."""
        if isinstance(valor, (list, tuple)) and valor and all(isinstance(item, (list, tuple)) for item in valor):
            return "\n".join(f" {SEPARADOR_DE_CELULAS} ".join(linha) for linha in valor)
        if isinstance(valor, (list, tuple)) and campo in ("valores", "colunas"):
            return f" {SEPARADOR_DE_CELULAS} ".join(str(item) for item in valor)
        return super().texto_do_campo(campo, valor)

    def aviso_da_previa(self, conteudo=None):
        """Demonstração só se a conta que vai agir é simulada (a outra pode ser de verdade)."""
        if not conteudo:
            return super().aviso_da_previa()
        avisos = [AVISO_DE_DEMONSTRACAO] if conector(conteudo["servico"]).demonstracao() else []
        if self.sai_da_plataforma:
            avisos.append(self.aviso_de_saida)
        return " ".join(avisos) or None
