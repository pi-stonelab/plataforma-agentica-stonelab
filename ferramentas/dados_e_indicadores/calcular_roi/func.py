"""Retorno de um agente: quanto ele economiza em horas contra o que custa (o "Gerir: custos e ROI" da proposta)."""

from decimal import ROUND_HALF_UP, Decimal

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.dados_sinteticos import reais

MESES_PADRAO = 12
MESES_MAXIMOS = 60
VALOR_MAXIMO = Decimal(10000000)
HORAS_MAXIMAS_POR_MES = Decimal(10000)


def _centavos(valor):
    return int((valor * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


class CalcularRoi(Ferramenta):
    nome = "calcular_roi"
    descricao_para_pessoa = "Calcula se um agente se paga: economia em horas contra o custo, com o retorno e o prazo de volta."
    area = "dados_e_indicadores"
    acesso = "calculo"
    integracoes = ()
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ()
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "horas_economizadas_por_mes": {"tipo": "decimal", "obrigatorio": True},
        "custo_hora": {"tipo": "decimal", "obrigatorio": True},
        "custo_mensal_agente": {"tipo": "decimal", "obrigatorio": True},
        "custo_implantacao": {"tipo": "decimal", "obrigatorio": False},
        "meses": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        horas = argumentos["horas_economizadas_por_mes"]
        custo_hora = argumentos["custo_hora"]
        custo_mensal = argumentos["custo_mensal_agente"]
        implantacao = argumentos.get("custo_implantacao", Decimal(0))
        meses = argumentos.get("meses", MESES_PADRAO)
        if not 0 <= horas <= HORAS_MAXIMAS_POR_MES:
            raise ErroFerramenta("parametro_invalido", "As horas_economizadas_por_mes devem ficar entre 0 e 10.000.")
        if not all(0 <= valor <= VALOR_MAXIMO for valor in (custo_hora, custo_mensal, implantacao)):
            raise ErroFerramenta("parametro_invalido", "Os valores em reais devem ficar entre 0 e 10.000.000.")
        if not 1 <= meses <= MESES_MAXIMOS:
            raise ErroFerramenta("parametro_invalido", f"Os meses devem ficar entre 1 e {MESES_MAXIMOS}.")
        economia_mensal = _centavos(horas * custo_hora)
        custo_mensal_centavos = _centavos(custo_mensal)
        implantacao_centavos = _centavos(implantacao)
        ganho_total = economia_mensal * meses
        custo_total = custo_mensal_centavos * meses + implantacao_centavos
        ganho_liquido_mensal = economia_mensal - custo_mensal_centavos
        if custo_total == 0:
            roi = None
        else:
            roi = (Decimal(ganho_total - custo_total) * 100 / custo_total).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if implantacao_centavos == 0:
            payback = 0 if ganho_liquido_mensal >= 0 else None
        elif ganho_liquido_mensal > 0:
            payback = -(-implantacao_centavos // ganho_liquido_mensal)  # meses inteiros, arredondando para cima
        else:
            payback = None
        return {
            "meses": meses,
            "economia_mensal": reais(economia_mensal),
            "custo_mensal": reais(custo_mensal_centavos),
            "ganho_liquido_mensal": reais(ganho_liquido_mensal),
            "ganho_total": reais(ganho_total),
            "custo_total": reais(custo_total),
            "roi_percentual": float(roi) if roi is not None else None,
            "payback_meses": payback,
            "se_paga": payback is not None and payback <= meses,
        }


FERRAMENTA = CalcularRoi()
