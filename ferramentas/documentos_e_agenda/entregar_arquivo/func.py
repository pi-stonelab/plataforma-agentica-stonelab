"""Gera um arquivo (csv, xlsx ou txt) na pasta de saída da plataforma e devolve o id para a pessoa baixar no chat."""

from ferramentas import escritorio
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes import conector, formatos
from ferramentas.integracoes.anexos.conector import TIPOS_DE_SAIDA
from ferramentas.mensagens_internas import texto_mascarado

TAMANHO_DO_NOME = 80
TAMANHO_DO_CONTEUDO = 20_000
LINHAS_NO_MAXIMO = 500


class EntregarArquivo(Ferramenta):
    nome = "entregar_arquivo"
    area = "documentos_e_agenda"
    acesso = "escrita"  # grava só na pasta de saída da própria plataforma: sem prévia (governanca.ESCRITA_SEM_CONFIRMACAO)
    integracoes = ("anexos",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento_de_trabalho",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    descricao_para_pessoa = "Gera um arquivo (csv, xlsx ou txt) para você baixar na conversa."
    parametros = {
        "nome": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_NOME},
        "formato": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 10},
        "conteudo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_CONTEUDO},
    }

    def rodar(self, argumentos, usuario):
        formato = argumentos["formato"].strip().lower().lstrip(".")
        if formato not in TIPOS_DE_SAIDA:
            raise ErroFerramenta("parametro_invalido", f"O formato deve ser um destes: {', '.join(TIPOS_DE_SAIDA)}.")
        nome = escritorio.exigir_uma_linha(argumentos["nome"], "O nome")
        if formato == "txt":
            conteudo = formatos.escrever_txt(texto_mascarado(argumentos["conteudo"], "O conteúdo"))
        else:
            linhas = escritorio.linhas_de(argumentos["conteudo"], "O conteúdo", LINHAS_NO_MAXIMO)
            if not linhas:
                raise ErroFerramenta("parametro_invalido", "O conteúdo não pode ficar vazio.")
            conteudo = formatos.escrever_csv(linhas) if formato == "csv" else formatos.escrever_xlsx(linhas, nome)
        anexos = conector("anexos")
        entregue = anexos.guardar_saida(usuario.id_usuario, nome, formato, conteudo)
        return {
            "arquivo_id": entregue["arquivo_id"],
            "arquivo": entregue["nome"],
            "formato": formato,
            "tamanho": entregue["tamanho"],
            "fonte": anexos.fonte(),
        }


FERRAMENTA = EntregarArquivo()
