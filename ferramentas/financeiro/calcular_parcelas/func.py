"""Parcelamento de um acordo em centavos, com a alçada de quem pode aprovar (DOC-MOCK §7.9)."""

from decimal import ROUND_HALF_UP, Decimal

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.dados_sinteticos import reais

# Alçadas do DOC-MOCK §7.9 (limites ilustrativos, da equipe). Pendência: mover para mock/regras.py.
ENTRADA_MINIMA_ANALISTA = Decimal(20)  # em %
PARCELAS_MAXIMAS_ANALISTA = 6
PARCELAS_MAXIMAS_COORDENADOR = 12
DESCONTO_MAXIMO_COORDENADOR = Decimal(10)  # em % do valor principal
VALOR_MAXIMO = Decimal(1000000)
PARCELAS_MAXIMAS_PEDIDO = 60  # acima de 12 já é proibido; este teto só barra lista absurda


def em_centavos(valor):
    return int((valor * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percentual_de(centavos, percentual):
    return int((Decimal(centavos) * percentual / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def dividir(centavos, partes):
    """Partes iguais; a última absorve a diferença do arredondamento (DOC-MOCK §7.1)."""
    parcela = centavos // partes
    return [parcela] * (partes - 1) + [centavos - parcela * (partes - 1)]


def quem_aprova(numero_parcelas, entrada, desconto):
    """Devolve ("analista" | "coordenador" | "proibido", motivo)."""
    if desconto > DESCONTO_MAXIMO_COORDENADOR:
        return "proibido", "Desconto no principal acima de 10% não é permitido."
    if numero_parcelas > PARCELAS_MAXIMAS_COORDENADOR:
        return "proibido", "Acordo acima de 12 parcelas não é permitido."
    motivos = []
    if desconto > 0:
        motivos.append("desconto no principal só o coordenador aprova (até 10%)")
    if numero_parcelas > PARCELAS_MAXIMAS_ANALISTA:
        motivos.append("o analista aprova até 6 parcelas")
    if entrada < ENTRADA_MINIMA_ANALISTA:
        motivos.append("o analista exige entrada de pelo menos 20%")
    if motivos:
        return "coordenador", "Exige coordenador: " + "; ".join(motivos) + "."
    return "analista", "Dentro da alçada do analista (até 6 parcelas, entrada de pelo menos 20%)."


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
    }

    def rodar(self, argumentos, usuario):
        valor_total = argumentos["valor_total"]
        numero_parcelas = argumentos["numero_parcelas"]
        entrada = argumentos.get("entrada_percentual", ENTRADA_MINIMA_ANALISTA)
        desconto = argumentos.get("desconto_principal_percentual", Decimal(0))
        if not 0 < valor_total <= VALOR_MAXIMO:
            raise ErroFerramenta(
                "parametro_invalido", "O valor_total deve ficar entre 0 e 1.000.000."
            )
        if not 1 <= numero_parcelas <= PARCELAS_MAXIMAS_PEDIDO:
            raise ErroFerramenta("parametro_invalido", "O numero_parcelas deve ficar entre 1 e 60.")
        if not 0 <= entrada < 100 or not 0 <= desconto < 100:
            raise ErroFerramenta("parametro_invalido", "Os percentuais devem ficar entre 0 e 99.")
        aprovador, motivo = quem_aprova(numero_parcelas, entrada, desconto)
        dados = {
            "valor_informado": reais(em_centavos(valor_total)),
            "numero_parcelas": numero_parcelas,
            "entrada_percentual": float(entrada),
            "desconto_principal_percentual": float(desconto),
            "quem_aprova": aprovador,
            "motivo": motivo,
            "parcelas": [],  # proibido: nada é calculado
        }
        if aprovador == "proibido":
            return dados
        negociado = em_centavos(valor_total) - percentual_de(em_centavos(valor_total), desconto)
        valor_entrada = percentual_de(negociado, entrada)
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
