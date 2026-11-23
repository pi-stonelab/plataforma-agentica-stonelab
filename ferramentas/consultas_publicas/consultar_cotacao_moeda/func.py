from datetime import timedelta

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes.apis_publicas.conector import (
    CONECTOR as APIS_PUBLICAS,
)
from ferramentas.integracoes.apis_publicas.conector import (
    DATA_MINIMA_DA_COTACAO,
    FONTE_COTACAO_SIMULADA,
    FONTE_PTAX,
    MOEDAS_SIMULADAS,
    PADRAO_MOEDA,
    SABADO,
)

DIAS_PARA_TRAS = 7  # fim de semana e feriado não têm boletim: volta até achar, no máximo uma semana
FECHAMENTO = "Fechamento"


def _reais(valor):
    return "R$ " + f"{valor:.4f}".replace(".", ",")


def _brasileira(dia):
    return f"{dia:%d/%m/%Y}"


def _boletim_do_dia(boletins):
    """O de fechamento, se já saiu; senão o mais recente do dia."""
    fechamento = [b for b in boletins if b["boletim"].startswith(FECHAMENTO)]
    return fechamento[-1] if fechamento else max(boletins, key=lambda b: b["momento"])


def _dia_pedido(argumentos, simulado):
    hoje = APIS_PUBLICAS.hoje()
    dia = argumentos.get("data", hoje)
    if dia > hoje:
        if simulado:
            mensagem = f"Nesta plataforma de demonstração, hoje é {_brasileira(hoje)}. Escolha uma data até esse dia."
        else:
            mensagem = f"A data não pode ser depois de hoje ({_brasileira(hoje)})."
        raise ErroFerramenta("parametro_invalido", mensagem)
    if dia < DATA_MINIMA_DA_COTACAO:
        raise ErroFerramenta(
            "parametro_invalido", f"O Banco Central tem cotação a partir de {_brasileira(DATA_MINIMA_DA_COTACAO)}."
        )
    return dia


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
    descricao_para_pessoa = "Mostra a cotação oficial de uma moeda estrangeira em reais (PTAX do Banco Central)."
    parametros = {
        "moeda": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 3},
        "data": {"tipo": "data", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        moeda = argumentos["moeda"].upper()
        if not PADRAO_MOEDA.fullmatch(moeda):
            raise ErroFerramenta("parametro_invalido", "Use o código de 3 letras da moeda, como USD.")
        simulado = APIS_PUBLICAS.modo() == "simulado"
        dia = _dia_pedido(argumentos, simulado)
        moedas = APIS_PUBLICAS.moedas()
        if moeda not in moedas:
            if simulado:
                disponiveis = ", ".join(sorted(MOEDAS_SIMULADAS))
                raise ErroFerramenta("parametro_invalido", f"No modo de demonstração só há {disponiveis}.")
            raise ErroFerramenta("parametro_invalido", "O Banco Central não publica cotação dessa moeda.")
        for dias_antes in range(DIAS_PARA_TRAS):
            tentativa = dia - timedelta(days=dias_antes)
            if tentativa.weekday() >= SABADO or tentativa < DATA_MINIMA_DA_COTACAO:
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
                    "fonte": FONTE_COTACAO_SIMULADA if simulado else FONTE_PTAX,
                }
        raise ErroFerramenta("nao_encontrado", "Sem boletim do Banco Central nos 7 dias até essa data.")


FERRAMENTA = ConsultarCotacaoMoeda()
