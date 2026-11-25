"""Prepara a retirada de um acordo pendente por quem o pediu; cancela só quando essa pessoa confirma.

O acordo que espera aprovação prende as faturas do lojista. Quem pediu pode desistir dele (por exemplo, quando não há
outra pessoa que possa aprová-lo): o acordo vira "cancelado" e as faturas ficam livres para um acordo novo.
"""

import re

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.apresentacao import ROTULOS_DA_ALCADA
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

PADRAO_ACORDO = re.compile(r"AC\d{4}")
LIMITE_DE_PENDENTES = 50


class RetirarAcordo(FerramentaComConfirmacao):
    nome = "retirar_acordo"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cadastral", "cobranca")
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "id_acordo", "efeito")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "na lista de acordos"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Retirar acordo"
    mensagem_feito = "Acordo retirado."
    descricao_para_pessoa = (
        "Prepara a retirada de um acordo que você pediu e que ainda espera aprovação; as faturas ficam livres para um "
        "acordo novo. Nada muda antes da sua confirmação."
    )
    rotulos_da_previa = {
        "id_acordo": "Acordo",
        "id_cliente": "Lojista",
        "faturas": "Faturas",
        "valor_renegociado": "Valor renegociado",
        "alcada": "Quem aprovaria",
        "efeito": "O que acontece",
    }
    parametros = {"id_acordo": {"tipo": "texto", "obrigatorio": True}}

    def montar(self, argumentos, usuario):
        id_acordo = argumentos["id_acordo"].upper()
        if not PADRAO_ACORDO.fullmatch(id_acordo):
            raise ErroFerramenta("parametro_invalido", "O id_acordo deve ser como AC0001.")
        pendentes, _ = dados_sinteticos.buscar_acordos(None, "pendente_aprovacao", LIMITE_DE_PENDENTES)
        acordo = next((a for a in pendentes if a["codigo"] == id_acordo and a["id_solicitante"] == usuario.id_usuario), None)
        if acordo is None:  # o de outra pessoa responde igual ao que não existe
            raise ErroFerramenta("nao_encontrado", "Acordo pendente de aprovação seu não encontrado.")
        lojista.exigir_acesso(usuario, acordo["id_cliente"])
        conteudo = {"id_acordo": id_acordo}
        previa = {
            "id_acordo": id_acordo,
            "id_cliente": acordo["id_cliente"],
            "faturas": acordo["faturas"],
            "valor_renegociado": acordo["valor_renegociado"],
            "alcada": ROTULOS_DA_ALCADA.get(acordo["alcada"], acordo["alcada"]),
            "efeito": "O acordo é cancelado e as faturas ficam livres para um acordo novo",
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def mensagem_ao_confirmar(self, dados):
        return f"Acordo {dados['codigo']} retirado: as faturas ficaram livres para um acordo novo."

    def referencia_do_resultado(self, dados):
        return dados["codigo"]  # id neutro do acordo retirado: liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        return escritas_sinteticas.retirar_acordo(conteudo["id_acordo"], usuario.id_usuario)


FERRAMENTA = RetirarAcordo()
