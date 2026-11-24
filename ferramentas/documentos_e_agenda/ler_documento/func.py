"""Lê o texto de um documento da conta (Google Docs ou Word no OneDrive) de quem pede."""

from ferramentas.base import Ferramenta
from ferramentas.escritorio import (
    INTEGRACOES,
    PARAMETRO_SERVICO,
    conector_da_pessoa,
    exigir_id_de_arquivo,
    mascarar_celula,
    situacao_das_contas,
)
from ferramentas.mascara import mascarar_valor
from ferramentas.mensagens_internas import TEXTO_QUE_SAI

CARACTERES_NO_MAXIMO = 6000


class LerDocumento(Ferramenta):
    nome = "ler_documento"
    area = "documentos_e_agenda"
    acesso = "leitura"
    integracoes = INTEGRACOES
    integracoes_alternativas = True
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento_de_trabalho",)
    # Da conta ou do arquivo da própria pessoa (E2/F5): saem pela máscara de CPF e cartão e só nesta ficha deixam de virar "***".
    campos_liberados = ("titulo",)
    sensibilidade = "interna"
    conteudo_terceiros = True
    status = "ativa"
    descricao_para_pessoa = "Mostra o texto de um documento da sua conta Google ou Microsoft."
    parametros = {
        "id_arquivo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 128},
        "servico": PARAMETRO_SERVICO,
    }

    def situacao_para_o_agente(self):
        return situacao_das_contas()

    def rodar(self, argumentos, usuario):
        id_arquivo = exigir_id_de_arquivo(argumentos["id_arquivo"])
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        documento = conta.documento(usuario.id_usuario, id_arquivo, CARACTERES_NO_MAXIMO)
        return {
            "titulo": mascarar_celula(documento["titulo"]),
            "texto": mascarar_valor(TEXTO_QUE_SAI, documento["texto"]),
            "truncado": documento["truncado"],
            "fonte": conta.fonte(),
        }


FERRAMENTA = LerDocumento()
