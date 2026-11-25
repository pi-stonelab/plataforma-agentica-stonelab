"""Lê as linhas de uma planilha da conta (Google Sheets ou Excel no OneDrive) de quem pede."""

from ferramentas.base import Ferramenta
from ferramentas.escritorio import (
    CELULAS_NO_MAXIMO,
    INTEGRACOES,
    PARAMETRO_SERVICO,
    TAMANHO_DO_ID_OU_LINK,
    conector_da_pessoa,
    exigir_id_de_arquivo,
    exigir_intervalo,
    exigir_limite,
    mascarar_celula,
    situacao_das_contas,
)

LIMITE_PADRAO = 30
LIMITE_MAXIMO = 100


class LerPlanilha(Ferramenta):
    nome = "ler_planilha"
    area = "documentos_e_agenda"
    acesso = "leitura"
    integracoes = INTEGRACOES
    integracoes_alternativas = True
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento_de_trabalho",)
    # Da conta ou do arquivo da própria pessoa (E2/F5): saem pela máscara de CPF e cartão e só nesta ficha deixam de virar "***".
    campos_liberados = ("titulo", "aba", "abas", "intervalo", "linhas")
    sensibilidade = "interna"
    conteudo_terceiros = True
    status = "ativa"
    descricao_para_pessoa = "Mostra as linhas de uma planilha da sua conta Google ou Microsoft."
    parametros = {
        "id_arquivo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_ID_OU_LINK},
        "aba": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 100},
        "intervalo": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
        "servico": PARAMETRO_SERVICO,
    }

    def situacao_para_o_agente(self):
        return situacao_das_contas()

    def rodar(self, argumentos, usuario):
        id_arquivo = exigir_id_de_arquivo(argumentos["id_arquivo"])
        intervalo = exigir_intervalo(argumentos.get("intervalo"))
        limite = exigir_limite(argumentos.get("limite"), LIMITE_PADRAO, LIMITE_MAXIMO)
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        planilha = conta.ler_planilha(usuario.id_usuario, id_arquivo, argumentos.get("aba"), intervalo, limite)
        recortadas = any(len(linha) > CELULAS_NO_MAXIMO for linha in planilha["linhas"])
        return {
            "titulo": mascarar_celula(planilha["titulo"]),
            "aba": mascarar_celula(planilha["aba"]),
            "intervalo": planilha["intervalo"],
            "linhas": [[mascarar_celula(celula) for celula in linha[:CELULAS_NO_MAXIMO]] for linha in planilha["linhas"]],
            "truncado": planilha["truncado"] or recortadas,
            "fonte": conta.fonte(),
        }


FERRAMENTA = LerPlanilha()
