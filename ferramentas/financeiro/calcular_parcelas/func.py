"""Parcelamento de um acordo em centavos, com a alçada de quem pode aprovar (DOC-MOCK §7.9, `regras.alcada_do_acordo`)."""

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.dados_sinteticos import reais

ENTRADA_PADRAO = Decimal(dados_sinteticos.ENTRADA_MINIMA_ANALISTA_PERCENTUAL)  # em %
VALOR_MAXIMO = Decimal(1000000)
PARCELAS_MAXIMAS_PEDIDO = 60  # acima de 12 já é proibido; este teto só barra lista absurda


def em_centavos(valor):
    return int((valor * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percentual_de(centavos, percentual, arredondamento):
    return int((Decimal(centavos) * percentual / 100).quantize(Decimal(1), rounding=arredondamento))


def dividir(centavos, partes):
    """Partes iguais; a última absorve a diferença do arredondamento (DOC-MOCK §7.1)."""
    parcela = centavos // partes
    return [parcela] * (partes - 1) + [centavos - parcela * (partes - 1)]


def motivo_da_alcada(alcada, *, principal, negociado, numero_parcelas, entrada, perdao, desconto):
    """Explica, em texto para a pessoa, a decisão de `regras.alcada_do_acordo` (DOC-MOCK §7.9). Centavos."""
    d = dados_sinteticos
    if alcada == "proibido":
        if numero_parcelas > d.PARCELAS_MAXIMAS_COORDENADOR:
            return f"Acordo acima de {d.PARCELAS_MAXIMAS_COORDENADOR} parcelas não é permitido."
        return f"Desconto no principal acima de {d.DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL}% não é permitido."
    if alcada == "dupla_aprovacao":
        limite = reais(d.LIMITE_DA_DUPLA_APROVACAO_CENTAVOS)
        return f"Acima de {limite} renegociados: duas aprovações, e quem pede nunca aprova."
    motivos = []
    if desconto > 0:
        motivos.append(f"desconto no principal só o coordenador aprova (até {d.DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL}%)")
    if perdao > 0 and principal > d.PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS:
        limite = reais(d.PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS)
        motivos.append(f"o analista só perdoa multa e juros em dívida de até {limite}")
    if numero_parcelas > d.PARCELAS_MAXIMAS_ANALISTA:
        motivos.append(f"o analista aprova até {d.PARCELAS_MAXIMAS_ANALISTA} parcelas")
    if entrada * 100 < negociado * d.ENTRADA_MINIMA_ANALISTA_PERCENTUAL:
        motivos.append(f"o analista exige entrada de pelo menos {d.ENTRADA_MINIMA_ANALISTA_PERCENTUAL}%")
    if alcada == "coordenador":
        return "Exige coordenador: " + "; ".join(motivos) + "."
    return (
        f"Dentro da alçada do analista (até {d.PARCELAS_MAXIMAS_ANALISTA} parcelas, entrada de pelo menos "
        f"{d.ENTRADA_MINIMA_ANALISTA_PERCENTUAL}%)."
    )


class CalcularParcelas(Ferramenta):
    nome = "calcular_parcelas"
    area = "financeiro"
    acesso = "calculo"
    integracoes = ()
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ()
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "valor_total": {"tipo": "decimal", "obrigatorio": True},
        "numero_parcelas": {"tipo": "inteiro", "obrigatorio": True},
        "entrada_percentual": {"tipo": "decimal", "obrigatorio": False},
        "desconto_principal_percentual": {"tipo": "decimal", "obrigatorio": False},
        "valor_principal": {"tipo": "decimal", "obrigatorio": False},
        "perdao_encargos": {"tipo": "decimal", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        valor_total = argumentos["valor_total"]
        numero_parcelas = argumentos["numero_parcelas"]
        entrada_percentual = argumentos.get("entrada_percentual", ENTRADA_PADRAO)
        desconto_percentual = argumentos.get("desconto_principal_percentual", Decimal(0))
        if not 0 < valor_total <= VALOR_MAXIMO:
            raise ErroFerramenta("parametro_invalido", "O valor_total deve ficar entre 0 e 1.000.000.")
        if not 1 <= numero_parcelas <= PARCELAS_MAXIMAS_PEDIDO:
            raise ErroFerramenta("parametro_invalido", "O numero_parcelas deve ficar entre 1 e 60.")
        if not 0 <= entrada_percentual < 100 or not 0 <= desconto_percentual < 100:
            raise ErroFerramenta("parametro_invalido", "Os percentuais devem ficar entre 0 e 99.")
        total = em_centavos(valor_total)
        principal = em_centavos(argumentos.get("valor_principal", valor_total))
        perdao = em_centavos(argumentos.get("perdao_encargos", Decimal(0)))
        if not 0 < principal <= total:
            raise ErroFerramenta("parametro_invalido", "O valor_principal deve ser maior que 0 e até o valor_total.")
        if not 0 <= perdao <= total - principal:
            raise ErroFerramenta(
                "parametro_invalido", "O perdao_encargos não pode passar da multa e dos juros (valor_total menos valor_principal)."
            )
        # A alçada é conferida em centavos: o desconto arredonda para baixo e a entrada para cima, para nenhum dos
        # dois sair do percentual pedido (20% de R$ 330,67 é R$ 66,14, não R$ 66,13, que ficaria abaixo de 20%).
        desconto = percentual_de(principal, desconto_percentual, ROUND_FLOOR)
        negociado = total - desconto - perdao
        valor_entrada = percentual_de(negociado, entrada_percentual, ROUND_CEILING)
        alcada = dados_sinteticos.alcada_do_acordo(principal, negociado, numero_parcelas, valor_entrada, perdao, desconto)
        dados = {
            "valor_informado": reais(total),
            "numero_parcelas": numero_parcelas,
            "entrada_percentual": float(entrada_percentual),
            "desconto_principal_percentual": float(desconto_percentual),
            "quem_aprova": alcada,
            "motivo": motivo_da_alcada(
                alcada, principal=principal, negociado=negociado, numero_parcelas=numero_parcelas,
                entrada=valor_entrada, perdao=perdao, desconto=desconto,
            ),
            "parcelas": [],  # proibido: nada é calculado
        }
        if alcada == "proibido":
            return dados
        valores = dividir(negociado - valor_entrada, numero_parcelas)
        if min(valores) < 1:
            raise ErroFerramenta("parametro_invalido", "Valor pequeno demais para tantas parcelas.")
        dados |= {
            "valor_negociado": reais(negociado),
            "entrada": reais(valor_entrada),
            "parcelas": [{"numero": n, "valor": reais(v)} for n, v in enumerate(valores, start=1)],
        }
        return dados


FERRAMENTA = CalcularParcelas()
