"""Procura arquivos pelo nome no Drive (Google) ou no OneDrive (Microsoft) de quem pede."""

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.escritorio import (
    INTEGRACOES,
    PARAMETRO_SERVICO,
    conector_da_pessoa,
    exigir_limite,
    mascarar_celula,
    situacao_das_contas,
)
from ferramentas.integracoes.escritorio import TIPOS_DE_ARQUIVO

LIMITE_PADRAO = 10
LIMITE_MAXIMO = 20
TAMANHO_DA_CONSULTA = 80


class BuscarArquivos(Ferramenta):
    nome = "buscar_arquivos"
    area = "documentos_e_agenda"
    acesso = "leitura"
    integracoes = INTEGRACOES
    integracoes_alternativas = True
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento_de_trabalho",)
    # Da conta ou do arquivo da própria pessoa (E2/F5): saem pela máscara de CPF e cartão e só nesta ficha deixam de virar "***".
    campos_liberados = ("titulo", "modificado_em")
    sensibilidade = "interna"
    conteudo_terceiros = True  # arquivo compartilhado de fora aparece na busca: o nome é texto de terceiro
    status = "ativa"
    descricao_para_pessoa = "Procura planilhas e documentos pelo nome, na sua conta Google ou Microsoft."
    parametros = {
        "consulta": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DA_CONSULTA},
        "tipo": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
        "servico": PARAMETRO_SERVICO,
    }

    def situacao_para_o_agente(self):
        return situacao_das_contas()

    def rodar(self, argumentos, usuario):
        consulta = argumentos["consulta"]
        if not consulta or any(ord(c) < 32 for c in consulta):
            raise ErroFerramenta("parametro_invalido", "A consulta deve ser um texto de uma linha só.")
        tipo = (argumentos.get("tipo") or "qualquer").lower()
        if tipo not in TIPOS_DE_ARQUIVO:
            raise ErroFerramenta("parametro_invalido", f"O tipo deve ser um destes: {', '.join(TIPOS_DE_ARQUIVO)}.")
        limite = exigir_limite(argumentos.get("limite"), LIMITE_PADRAO, LIMITE_MAXIMO)
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        achados = conta.arquivos(usuario.id_usuario, consulta, tipo, limite + 1)  # um a mais mostra que há mais
        arquivos = achados[:limite]
        return {
            "arquivos": [{**arquivo, "titulo": mascarar_celula(arquivo["titulo"])} for arquivo in arquivos],
            "total": len(arquivos),  # quantos vieram nesta resposta, não quantos existem
            "truncado": len(achados) > limite,
            "fonte": conta.fonte(),
        }


FERRAMENTA = BuscarArquivos()
