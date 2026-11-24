"""Prepara um acordo de cobrança com as faturas vencidas do lojista; grava só quando quem pediu confirma.

Dentro da alçada de quem pede, o acordo nasce ativo. Acima, nasce pendente e vai para o coordenador (ou para a
dupla aprovação). Nunca aprova sozinho o que passa da alçada (DOC-MOCK §7.9).
"""

import re

from ferramentas import escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.dados_sinteticos import reais

PADRAO_FATURA = re.compile(r"I\d{6}")
DESTINO_DA_ALCADA = {
    "analista": "Fica ativo agora: está dentro do que a analista de cobrança aprova",
    "coordenador": "Espera a aprovação do coordenador financeiro",
    "dupla_aprovacao": "Espera duas aprovações (acordos acima de R$ 10.000,00 somados)",
}
DENTRO_DA_ALCADA_DE_QUEM_PEDE = "Fica ativo agora: está dentro do que o seu cargo aprova"
SEM_OUTRO_APROVADOR = (
    "Não há outra pessoa que possa aprovar este acordo (quem pede não aprova): ele ficaria parado. "
    "Se registrar, dá para retirá-lo depois."
)


class RegistrarAcordo(FerramentaComConfirmacao):
    nome = "registrar_acordo"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cadastral", "cobranca")
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "encargos", "valor_da_parcela", "valor_da_ultima_parcela", "aprovacao",
        "atencao",
    )
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "na lista de acordos do lojista"
    frase_de_nada_feito = "Nada foi gravado."
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
        "numero_de_parcelas": "Parcelas (além da entrada)",
        "valor_da_parcela": "Valor de cada parcela",
        "valor_da_ultima_parcela": "Última parcela (fecha o saldo)",
        "aprovacao": "Aprovação",
        "atencao": "Atenção",
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
        abertos = escritas_sinteticas.acordos_abertos_do_lojista(codigo)
        numeros = escritas_sinteticas.montar_acordo(
            faturas, argumentos["numero_parcelas"], argumentos.get("entrada_percentual"), perdoar, desconto, abertos
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
        na_alcada = alcada in alcadas
        aprovacao = DENTRO_DA_ALCADA_DE_QUEM_PEDE if na_alcada else DESTINO_DA_ALCADA[alcada]
        if em_reais["valor_da_ultima_parcela"] == em_reais["valor_da_parcela"]:
            del em_reais["valor_da_ultima_parcela"]  # só aparece quando a última absorve centavos
        previa = {"id_cliente": codigo, "faturas": list(codigos), **em_reais, "aprovacao": aprovacao}
        if avisos := _avisos(abertos, na_alcada, alcada, usuario):
            previa["atencao"] = " ".join(avisos)
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def referencia_do_resultado(self, dados):
        return dados["codigo"]  # id neutro do acordo registrado: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.registrar_acordo(
            conteudo["codigo"], conteudo["faturas"], conteudo["numero_parcelas"], conteudo["entrada_percentual"],
            conteudo["perdoar_encargos"], conteudo["desconto_principal_percentual"], usuario.id_usuario,
        )


def _avisos(abertos, na_alcada, alcada, usuario):
    avisos = []
    if abertos["quantidade"]:
        avisos.append(
            f"O lojista já tem {abertos['quantidade']} acordo(s) em aberto, somando "
            f"{reais(abertos['valor_renegociado_centavos'])} renegociados: o total conta para quem aprova."
        )
    if not na_alcada and escritas_sinteticas.aprovadores_possiveis(alcada, usuario.id_usuario) == 0:
        avisos.append(SEM_OUTRO_APROVADOR)
    return avisos


def _codigos_das_faturas(texto):
    """"I000123, I000124" vira ("I000123", "I000124"); sem texto, None (todas as vencidas fora de acordo)."""
    if not texto:
        return None
    codigos = tuple(parte.strip().upper() for parte in texto.split(",") if parte.strip())
    if not codigos or any(not PADRAO_FATURA.fullmatch(codigo) for codigo in codigos):
        raise ErroFerramenta("parametro_invalido", "Faturas separadas por vírgula, como I000123, I000124.")
    return codigos


FERRAMENTA = RegistrarAcordo()
