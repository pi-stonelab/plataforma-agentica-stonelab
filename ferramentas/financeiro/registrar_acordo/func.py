"""Prepara um acordo de cobrança com as faturas vencidas do lojista; grava só quando quem pediu confirma.

Dentro da alçada de quem pede, o acordo nasce ativo. Acima, nasce pendente e vai para o coordenador (ou para a
dupla aprovação). Nunca aprova sozinho o que passa da alçada (DOC-MOCK §7.9).
"""

import re

from ferramentas import escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

PADRAO_FATURA = re.compile(r"I\d{6}")
DESTINO_DA_ALCADA = {
    "analista": "fica ativo agora (dentro da alçada da analista)",
    "coordenador": "vai para a aprovação do coordenador financeiro",
    "dupla_aprovacao": "vai para a dupla aprovação (acima de R$ 10.000,00)",
}


class RegistrarAcordo(FerramentaComConfirmacao):
    nome = "registrar_acordo"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cadastral", "cobranca")
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "encargos", "valor_da_parcela", "aprovacao")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Registrar acordo"
    mensagem_feito = "Acordo registrado."
    descricao_para_pessoa = (
        "Prepara um acordo com as faturas vencidas do lojista, com entrada, parcelas e quem precisa aprovar; ele só é "
        "gravado depois que você confirma."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "faturas": "Faturas",
        "valor_original": "Valor original",
        "encargos": "Encargos",
        "perdao_encargos": "Perdão de encargos",
        "desconto_principal": "Desconto no principal",
        "valor_renegociado": "Valor renegociado",
        "entrada": "Entrada",
        "numero_de_parcelas": "Parcelas",
        "valor_da_parcela": "Valor da parcela",
        "aprovacao": "Aprovação",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "numero_parcelas": {"tipo": "inteiro", "obrigatorio": True},
        "entrada_percentual": {"tipo": "decimal", "obrigatorio": False},
        "perdoar_encargos": {"tipo": "texto", "obrigatorio": False},
        "desconto_principal_percentual": {"tipo": "decimal", "obrigatorio": False},
        "faturas": {"tipo": "texto", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        alcadas = escritas_sinteticas.alcadas_do_cargo(usuario.cargo)
        if not alcadas:
            raise ErroFerramenta("permissao_negada", "Seu cargo não negocia acordos.")
        pedidas = _codigos_das_faturas(argumentos.get("faturas"))
        perdoar = escritas_sinteticas.sim_ou_nao(argumentos.get("perdoar_encargos"), "perdoar_encargos")
        desconto = argumentos.get("desconto_principal_percentual") or 0
        lojista.exigir_acesso(usuario, codigo)
        faturas = escritas_sinteticas.faturas_do_acordo(codigo, pedidas)
        numeros = escritas_sinteticas.montar_acordo(
            faturas, argumentos["numero_parcelas"], argumentos.get("entrada_percentual"), perdoar, desconto
        )
        codigos = tuple(fatura["codigo"] for fatura in faturas)  # a gravação usa exatamente estas
        conteudo = {
            "codigo": codigo,
            "faturas": codigos,
            "numero_parcelas": argumentos["numero_parcelas"],
            "entrada_percentual": argumentos.get("entrada_percentual"),
            "perdoar_encargos": perdoar,
            "desconto_principal_percentual": desconto,
        }
        em_reais = escritas_sinteticas.numeros_em_reais(numeros)
        alcada = em_reais.pop("alcada")
        aprovacao = "fica ativo agora (dentro da sua alçada)" if alcada in alcadas else DESTINO_DA_ALCADA[alcada]
        previa = {"id_cliente": codigo, "faturas": list(codigos), **em_reais, "aprovacao": aprovacao}
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.registrar_acordo(
            conteudo["codigo"], conteudo["faturas"], conteudo["numero_parcelas"], conteudo["entrada_percentual"],
            conteudo["perdoar_encargos"], conteudo["desconto_principal_percentual"], usuario.id_usuario,
        )


def _codigos_das_faturas(texto):
    """"I000123, I000124" vira ("I000123", "I000124"); sem texto, None (todas as vencidas fora de acordo)."""
    if not texto:
        return None
    codigos = tuple(parte.strip().upper() for parte in texto.split(",") if parte.strip())
    if not codigos or any(not PADRAO_FATURA.fullmatch(codigo) for codigo in codigos):
        raise ErroFerramenta("parametro_invalido", "Faturas separadas por vírgula, como I000123, I000124.")
    return codigos


FERRAMENTA = RegistrarAcordo()
