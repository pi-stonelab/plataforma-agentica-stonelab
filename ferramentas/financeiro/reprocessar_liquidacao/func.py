"""Prepara uma nova tentativa da liquidação que falhou; agenda no core simulado só quando quem pediu confirma."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

LIMITE_DE_LIQUIDACOES = 50


class ReprocessarLiquidacao(FerramentaComConfirmacao):
    nome = "reprocessar_liquidacao"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("liquidacao",)
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "nova_tentativa_em")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Reprocessar liquidação"
    mensagem_feito = "Nova tentativa agendada."
    descricao_para_pessoa = (
        "Prepara uma nova tentativa da liquidação que falhou, para o próximo dia útil; nada é agendado antes da "
        "sua confirmação."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_liquidacao": "Liquidação",
        "data": "Data original",
        "valor": "Valor",
        "motivo_falha": "Motivo da falha",
        "nova_tentativa_em": "Nova tentativa em",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_liquidacao": {"tipo": "inteiro", "obrigatorio": True},
    }

    def montar(self, argumentos, usuario):
        codigo, id_liquidacao = argumentos["id_cliente"], argumentos["id_liquidacao"]
        lojista.exigir_acesso(usuario, codigo)
        liquidacoes, _ = dados_sinteticos.buscar_liquidacoes(codigo, None, None, LIMITE_DE_LIQUIDACOES)
        liquidacao = next((item for item in liquidacoes if item["id_liquidacao"] == id_liquidacao), None)
        if liquidacao is None:
            raise ErroFerramenta("nao_encontrado", "Liquidação não encontrada para este lojista.")
        if liquidacao["situacao"] not in escritas_sinteticas.SITUACOES_DE_LIQUIDACAO_QUE_REPROCESSAM:
            raise ErroFerramenta("parametro_invalido", "Só a liquidação que falhou é reprocessada.")
        conteudo = {"codigo": codigo, "id_liquidacao": id_liquidacao}
        previa = {
            "id_cliente": codigo,
            "id_liquidacao": id_liquidacao,
            "data": liquidacao["data"],
            "valor": liquidacao["valor"],
            "motivo_falha": liquidacao["motivo_falha"],
            "nova_tentativa_em": escritas_sinteticas.proximo_dia_util(),
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.reprocessar_liquidacao(conteudo["codigo"], conteudo["id_liquidacao"], usuario.id_usuario)


FERRAMENTA = ReprocessarLiquidacao()
