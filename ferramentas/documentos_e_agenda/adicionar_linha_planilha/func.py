"""Prepara uma linha nova numa planilha da conta (Google ou Microsoft) de quem pede; grava só quando ele confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.escritorio import (
    PARAMETRO_SERVICO,
    EscritaDeEscritorio,
    celulas_de,
    conector_da_pessoa,
    exigir_id_de_arquivo,
    mascarar_celula,
)
from ferramentas.integracoes import conector


class AdicionarLinhaPlanilha(EscritaDeEscritorio):
    nome = "adicionar_linha_planilha"
    area = "documentos_e_agenda"
    categorias_dados = ("documento_de_trabalho",)
    campos_liberados = (*EscritaDeEscritorio.campos_liberados, "planilha", "valores", "linhas_adicionadas")
    status = "ativa"
    titulo = "Adicionar linha à planilha"
    descricao_para_pessoa = (
        "Prepara uma linha nova numa planilha (Google ou Microsoft); ela só é gravada depois que você confirma."
    )
    rotulos_da_previa = {"servico": "Conta", "planilha": "Planilha", "aba": "Aba", "valores": "Linha a adicionar"}
    parametros = {
        "id_arquivo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 128},
        "valores": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 2000},
        "aba": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 100},
        "servico": PARAMETRO_SERVICO,
    }

    def montar(self, argumentos, usuario):
        id_arquivo = exigir_id_de_arquivo(argumentos["id_arquivo"])
        valores = celulas_de(argumentos["valores"], "A linha")
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        planilha = conta.descrever_planilha(usuario.id_usuario, id_arquivo)  # confere que existe e acha a aba
        titulos = [aba["titulo"] for aba in planilha["abas"]]
        aba = argumentos.get("aba") or titulos[0]
        if aba not in titulos:
            raise ErroFerramenta("nao_encontrado", f"Aba não encontrada. Abas da planilha: {', '.join(titulos)}.")
        titulo = mascarar_celula(planilha["titulo"])
        conteudo = {"servico": conta.nome, "id_arquivo": id_arquivo, "aba": aba, "valores": valores}
        previa = {
            "servico": conta.rotulo, "planilha": titulo, "aba": mascarar_celula(aba), "valores": valores,
        }
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        conta = conector(conteudo["servico"])
        conta.adicionar_linha(usuario.id_usuario, conteudo["id_arquivo"], conteudo["aba"], conteudo["valores"])
        return {"aba": conteudo["aba"], "linhas_adicionadas": 1, "fonte": conta.fonte()}

    def mensagem_ao_confirmar(self, dados):
        frase = "Linha adicionada à planilha."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if "simulado" in dados["fonte"] else frase


FERRAMENTA = AdicionarLinhaPlanilha()
