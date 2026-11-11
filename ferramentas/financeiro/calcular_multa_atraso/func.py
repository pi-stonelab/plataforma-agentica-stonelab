from decimal import ROUND_HALF_UP, Decimal

from ferramentas.base import ErroFerramenta, Ferramenta

# [preencher: confirmar taxas com o financeiro]
TAXA_MULTA = Decimal("0.02")
TAXA_JUROS_MENSAL = Decimal("0.01")
DIAS_DO_MES = 30
VALOR_MAXIMO = Decimal(1000000)
DIAS_MAXIMO = 3650
CENTAVO = Decimal("0.01")
REGRA = "Multa de 2% a partir do 1º dia de atraso e juros de 1% ao mês, proporcionais aos dias."


def arredondar(valor):
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


class CalcularMultaAtraso(Ferramenta):
    nome = "calcular_multa_atraso"
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
        "valor_fatura": {"tipo": "decimal", "obrigatorio": True},
        "dias_atraso": {"tipo": "inteiro", "obrigatorio": True},
    }

    def rodar(self, argumentos, usuario):
        valor = argumentos["valor_fatura"]
        dias = argumentos["dias_atraso"]
        if not 0 < valor <= VALOR_MAXIMO:
            raise ErroFerramenta(
                "parametro_invalido", "O valor_fatura deve ficar entre 0 e 1.000.000."
            )
        if not 0 <= dias <= DIAS_MAXIMO:
            raise ErroFerramenta("parametro_invalido", "Os dias_atraso devem ficar entre 0 e 3650.")
        multa = arredondar(valor * TAXA_MULTA) if dias >= 1 else Decimal(0)
        juros = arredondar(valor * TAXA_JUROS_MENSAL * dias / DIAS_DO_MES)
        valor = arredondar(valor)
        return {
            "valor_fatura": float(valor),
            "dias_atraso": dias,
            "multa": float(multa),
            "juros": float(juros),
            "valor_total": float(valor + multa + juros),
            "regra": REGRA,
        }


FERRAMENTA = CalcularMultaAtraso()
