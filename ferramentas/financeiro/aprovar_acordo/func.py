"""Prepara a aprovação ou a recusa de um acordo pendente; grava só quando quem decide confirma.

Quem pediu o acordo nunca decide, e quem decide precisa ter a alçada dele (DOC-MOCK §7.9 e §8.1).
"""

import re

from ferramentas import dados_sinteticos, escritas_sinteticas
from ferramentas.apresentacao import ROTULOS_DA_ALCADA, cargo_de
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

PADRAO_ACORDO = re.compile(r"AC\d{4}")
DECISOES = {"aprovar": True, "recusar": False}
ROTULOS_DA_DECISAO = {"aprovar": "Aprovar", "recusar": "Recusar"}
LIMITE_DE_PENDENTES = 50


class AprovarAcordo(FerramentaComConfirmacao):
    nome = "aprovar_acordo"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N2"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cadastral", "cobranca")
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "id_acordo", "decisao")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "na lista de acordos"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Decidir acordo"
    mensagem_feito = "Decisão gravada."
    descricao_para_pessoa = "Prepara a aprovação ou a recusa de um acordo pendente; nada muda antes da sua confirmação."
    rotulos_da_previa = {
        "id_acordo": "Acordo",
        "decisao": "Decisão",
        "id_cliente": "Lojista",
        "faturas": "Faturas",
        "valor_original": "Valor original",
        "valor_renegociado": "Valor renegociado",
        "entrada": "Entrada",
        "numero_de_parcelas": "Parcelas",
        "perdao_encargos": "Perdão de encargos",
        "desconto_principal": "Desconto no principal",
        "alcada": "Quem aprova",
        "id_solicitante": "Pedido por",
    }
    parametros = {
        "id_acordo": {"tipo": "texto", "obrigatorio": True},
        "decisao": {"tipo": "texto", "obrigatorio": True},
    }

    def montar(self, argumentos, usuario):
        id_acordo, decisao = argumentos["id_acordo"].upper(), argumentos["decisao"].lower()
        if not PADRAO_ACORDO.fullmatch(id_acordo):
            raise ErroFerramenta("parametro_invalido", "O id_acordo deve ser como AC0001.")
        if decisao not in DECISOES:
            raise ErroFerramenta("parametro_invalido", "A decisão é aprovar ou recusar.")
        pendentes, _ = dados_sinteticos.buscar_acordos(None, "pendente_aprovacao", LIMITE_DE_PENDENTES)
        acordo = next((item for item in pendentes if item["codigo"] == id_acordo), None)
        if acordo is None:
            raise ErroFerramenta("nao_encontrado", "Acordo pendente de aprovação não encontrado.")
        if acordo["id_solicitante"] == usuario.id_usuario:  # a gravação confere de novo, com a alçada
            raise ErroFerramenta("permissao_negada", "Quem pediu o acordo não pode aprová-lo nem recusá-lo.")
        conteudo = {"id_acordo": id_acordo, "aprovar": DECISOES[decisao]}
        previa = {
            "id_acordo": id_acordo,
            "decisao": ROTULOS_DA_DECISAO[decisao],
            "id_cliente": acordo["id_cliente"],
            "faturas": acordo["faturas"],
            "valor_original": acordo["valor_original"],
            "valor_renegociado": acordo["valor_renegociado"],
            "entrada": acordo["entrada"],
            "numero_de_parcelas": acordo["numero_de_parcelas"],
            "perdao_encargos": acordo["perdao_encargos"],
            "desconto_principal": acordo["desconto_principal"],
            "alcada": ROTULOS_DA_ALCADA.get(acordo["alcada"], acordo["alcada"]),
            "id_solicitante": cargo_de(acordo["id_solicitante"], dados_sinteticos.buscar_funcionario),
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def mensagem_ao_confirmar(self, dados):
        return f"Acordo {dados['codigo']} {'aprovado' if dados['situacao'] == 'ativo' else 'recusado'}."

    def referencia_do_resultado(self, dados):
        return dados["codigo"]  # id neutro do acordo decidido: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        return escritas_sinteticas.decidir_acordo(conteudo["id_acordo"], conteudo["aprovar"], usuario.id_usuario)


FERRAMENTA = AprovarAcordo()
