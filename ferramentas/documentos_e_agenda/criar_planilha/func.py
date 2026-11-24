"""Prepara uma planilha nova na conta (Google ou Microsoft) de quem pede; cria só quando ele confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.escritorio import (
    PARAMETRO_SERVICO,
    EscritaDeEscritorio,
    celulas_de,
    conector_da_pessoa,
    exigir_uma_linha,
    linhas_de,
)
from ferramentas.integracoes import conector

TAMANHO_DO_TITULO = 100
LINHAS_NO_MAXIMO = 50
LINHAS_NA_PREVIA = 10


class CriarPlanilha(EscritaDeEscritorio):
    nome = "criar_planilha"
    area = "documentos_e_agenda"
    categorias_dados = ("documento_de_trabalho",)
    campos_liberados = (*EscritaDeEscritorio.campos_liberados, "titulo", "tamanho", "linhas")
    status = "ativa"
    titulo = "Criar planilha"
    descricao_para_pessoa = "Prepara uma planilha nova (Google ou Microsoft); ela só é criada depois que você confirma."
    rotulos_da_previa = {"servico": "Conta", "titulo": "Planilha", "colunas": "Colunas", "tamanho": "Tamanho", "linhas": "Linhas"}
    parametros = {
        "titulo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_TITULO},
        "colunas": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 400},
        "linhas": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 8000},
        "servico": PARAMETRO_SERVICO,
    }

    def montar(self, argumentos, usuario):
        titulo = exigir_uma_linha(argumentos["titulo"], "O título")
        colunas = celulas_de(argumentos["colunas"], "As colunas")
        linhas = linhas_de(argumentos.get("linhas", ""), "As linhas", LINHAS_NO_MAXIMO)
        if any(len(linha) > len(colunas) for linha in linhas):
            raise ErroFerramenta("parametro_invalido", "Uma linha tem mais células do que a planilha tem colunas.")
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        conteudo = {"servico": conta.nome, "titulo": titulo, "linhas": [colunas, *linhas]}
        previa = {
            "servico": conta.rotulo,
            "titulo": titulo,
            "colunas": colunas,
            "tamanho": f"{len(linhas)} linhas de dados, {len(colunas)} colunas",
            "linhas": linhas[:LINHAS_NA_PREVIA],  # cada célula já mascarada; o cartão mostra as primeiras
        }
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        conta = conector(conteudo["servico"])
        planilha = conta.criar_planilha(usuario.id_usuario, conteudo["titulo"], conteudo["linhas"])
        return {**planilha, "fonte": conta.fonte()}

    def mensagem_ao_confirmar(self, dados):
        frase = "Planilha criada."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if "simulado" in dados["fonte"] else frase

    def referencia_do_resultado(self, dados):
        return dados["id_arquivo"]  # id neutro: liga a planilha criada a quem confirmou, no registro


FERRAMENTA = CriarPlanilha()
