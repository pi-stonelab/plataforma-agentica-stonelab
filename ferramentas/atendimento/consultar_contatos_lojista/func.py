"""Contatos de um lojista. Nome, CPF, telefone e e-mail saem mascarados (DOC-MOCK §8.3)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import Ferramenta


class ConsultarContatosLojista(Ferramenta):
    nome = "consultar_contatos_lojista"
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("contato",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {"id_cliente": {"tipo": "texto", "obrigatorio": True}}

    def rodar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        lojista.exigir_acesso(usuario, codigo)
        contatos, total = dados_sinteticos.buscar_contatos(codigo)
        # O dado sai em claro daqui: a máscara por campo é aplicada uma vez, em Ferramenta.executar.
        return {"codigo": codigo, "contatos": contatos, "total_encontrado": total}


FERRAMENTA = ConsultarContatosLojista()
