"""Confere se o telefone ou o e-mail de quem fala é um contato cadastrado do lojista (DOC-MOCK §6.6).

Só responde "confere" ou "não confere" e o que fazer. Nunca devolve o contato cadastrado: quem tenta um
golpe não pode descobrir o telefone certo perguntando ao agente.
"""

import re

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

PADRAO_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
DIGITOS_DO_TELEFONE = (10, 11, 12, 13)  # com DDD; 12 e 13 com o 55 do país
ORIENTACAO_QUANDO_CONFERE = (
    "O contato está no cadastro. Antes de mostrar dado confidencial ou mudar algo, confirme o CNPJ com a "
    "pessoa e mande o código de confirmação para esse contato. Troca de conta de recebimento é só com o N2."
)
ORIENTACAO_QUANDO_NAO_CONFERE = (
    "O contato não está no cadastro. Não mostre nenhum dado do lojista e não mude nada. Peça que a pessoa "
    "fale de um telefone ou e-mail cadastrado. Se ela pedir troca da conta de recebimento ou tiver pressa, "
    "encaminhe o chamado ao N2 como suspeita de fraude."
)


class VerificarIdentidadeContato(Ferramenta):
    nome = "verificar_identidade_contato"
    descricao_para_pessoa = "Confere se quem fala usa um telefone ou e-mail do cadastro do lojista, sem mostrar o contato."
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("contato",)
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "telefone": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 30},
        "email": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 120},
    }

    def rodar(self, argumentos, usuario):
        telefone, email = argumentos.get("telefone"), argumentos.get("email")
        if not telefone and not email:
            raise ErroFerramenta("parametro_invalido", "Informe o telefone ou o e-mail de quem está falando.")
        if telefone and len(re.sub(r"\D", "", telefone)) not in DIGITOS_DO_TELEFONE:
            raise ErroFerramenta("parametro_invalido", "O telefone deve ter DDD, como (21) 90000-0606.")
        if email and not PADRAO_EMAIL.fullmatch(email):
            raise ErroFerramenta("parametro_invalido", "O e-mail deve ser como nome@empresa.com.br.")
        codigo = argumentos["id_cliente"]
        lojista.exigir_acesso(usuario, codigo)
        resultado = dados_sinteticos.contato_confere(codigo, telefone, email)
        confere = bool(resultado and resultado["confere"])
        return {
            "codigo": codigo,
            "confere": confere,
            "papel": resultado["papel"] if confere else None,
            "orientacao": ORIENTACAO_QUANDO_CONFERE if confere else ORIENTACAO_QUANDO_NAO_CONFERE,
        }


FERRAMENTA = VerificarIdentidadeContato()
