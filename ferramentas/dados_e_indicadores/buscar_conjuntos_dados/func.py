"""Procura conjuntos de dados (tabelas) do dicionário pelo nome, pela descrição ou pelo sistema dono."""

from ferramentas import dicionario, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 10
LIMITE_MAXIMO = 20  # com 50 a resposta passa dos 6000 caracteres que o agente lê


class BuscarConjuntosDados(Ferramenta):
    nome = "buscar_conjuntos_dados"
    descricao_para_pessoa = "Procura as tabelas de dados da Stone pelo assunto e diz de que sistema cada uma é."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("datahub",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("metadado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("nome_do_sistema",)  # texto escrito pela plataforma, não pelo lojista
    parametros = {
        "termo": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 60},
        "sistema": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        termo = (argumentos.get("termo") or "").casefold()
        sistema = argumentos.get("sistema")
        todos = dicionario.conjuntos()
        if sistema is not None and sistema not in {tabela["sistema"] for tabela in todos}:
            opcoes = ", ".join(sorted({tabela["sistema"] for tabela in todos}))
            raise ErroFerramenta("parametro_invalido", f"O sistema deve ser um destes: {opcoes}.")
        limite = lojista.limite_pedido(argumentos, LIMITE_PADRAO, LIMITE_MAXIMO)
        achados = [
            tabela
            for tabela in todos
            if (sistema is None or tabela["sistema"] == sistema)
            and termo in f"{tabela['tabela']} {tabela['descricao_da_tabela']} {tabela['nome_do_sistema']}".casefold()
        ]
        return {
            "conjuntos": [
                {
                    "tabela": tabela["tabela"],
                    "sistema": tabela["sistema"],
                    "nome_do_sistema": tabela["nome_do_sistema"],
                    "descricao_da_tabela": tabela["descricao_da_tabela"],
                    "quantidade_de_colunas": len(tabela["colunas"]),
                    "tem_coluna_restrita": any(coluna["restrita"] for coluna in tabela["colunas"]),
                }
                for tabela in achados[:limite]
            ],
            "total_encontrado": len(achados),
            "truncado": len(achados) > limite,
        }


FERRAMENTA = BuscarConjuntosDados()
