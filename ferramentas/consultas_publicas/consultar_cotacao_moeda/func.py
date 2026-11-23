import re
from datetime import timedelta

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.dados_sinteticos import HOJE_DO_MOCK
from ferramentas.integracoes.apis_publicas.conector import CONECTOR as APIS_PUBLICAS

MOEDA_RE = re.compile(r"[A-Za-z]{3}")
DIAS_PARA_TRAS = 7  # fim de semana e feriado não têm boletim: volta até achar, no máximo uma semana
SABADO = 5
FECHAMENTO = "Fechamento"
FONTE_REAL = "Banco Central do Brasil (PTAX)"
FONTE_SIMULADA = "Valores ilustrativos (modo simulado), não são cotações de verdade"


def _reais(valor):
    return "R$ " + f"{valor:.4f}".replace(".", ",")


def _boletim_do_dia(boletins):
    """O de fechamento, se já saiu; senão o mais recente do dia."""
    fechamento = [b for b in boletins if b["boletim"].startswith(FECHAMENTO)]
    return fechamento[-1] if fechamento else max(boletins, key=lambda b: b["momento"])


class ConsultarCotacaoMoeda(Ferramenta):
    nome = "consultar_cotacao_moeda"
    area = "consultas_publicas"
    acesso = "leitura"
    integracoes = ("apis_publicas",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("cambio",)
    sensibilidade = "publica"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "moeda": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 3},
        "data": {"tipo": "data", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        moeda = argumentos["moeda"].upper()
        if not MOEDA_RE.fullmatch(moeda):
            raise ErroFerramenta("parametro_invalido", "A moeda deve ser o código de 3 letras, como USD.")
        dia = argumentos.get("data", HOJE_DO_MOCK)
        if dia > HOJE_DO_MOCK:
            raise ErroFerramenta("parametro_invalido", "A data não pode ser depois de hoje.")
        moedas = APIS_PUBLICAS.moedas()
        if moeda not in moedas:
            raise ErroFerramenta("parametro_invalido", "O Banco Central não publica cotação dessa moeda.")
        for dias_antes in range(DIAS_PARA_TRAS):
            tentativa = dia - timedelta(days=dias_antes)
            if tentativa.weekday() >= SABADO:
                continue
            boletins = APIS_PUBLICAS.boletins(moeda, tentativa)
            if boletins:
                escolhido = _boletim_do_dia(boletins)
                return {
                    "moeda": moeda,
                    "nome_da_moeda": moedas[moeda],
                    "data": tentativa.isoformat(),
                    "boletim": escolhido["boletim"],
                    "cotacao_compra": _reais(escolhido["compra"]),
                    "cotacao_venda": _reais(escolhido["venda"]),
                    "fonte": FONTE_SIMULADA if APIS_PUBLICAS.modo() == "simulado" else FONTE_REAL,
                }
        raise ErroFerramenta("nao_encontrado", "Sem boletim do Banco Central nos 7 dias até essa data.")


FERRAMENTA = ConsultarCotacaoMoeda()
