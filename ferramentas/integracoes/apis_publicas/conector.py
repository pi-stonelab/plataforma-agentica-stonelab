"""APIs públicas: ViaCEP (endereço de um CEP) e PTAX do Banco Central (cotação de moedas).

Modo pelo `APIS_PUBLICAS_MODO`: `real` (padrão, chama as APIs), `simulado` (sem rede: os 3 CEPs de
`dados_sinteticos.py` e cotações fixas, ilustrativas) ou `desligado`. As URLs base vêm do .env (`VIACEP_URL` e
`BCB_PTAX_URL`), com os endereços oficiais como padrão. O formato das respostas segue a documentação pública:
ViaCEP `/ws/{cep}/json/` e PTAX OData `Moedas` e `CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)`.

O "hoje" (`hoje`) é o único relógio de verdade das ferramentas: no modo real, a cotação de um dado público vale
pela data real (America/Sao_Paulo), decisão do Pedro de 22/11; no simulado, segue o `HOJE_DO_MOCK` como o resto.
Toda resposta leva `fonte`, que diz quando o valor é de demonstração. A QA derruba as duas APIs com
`MOCK_FALHAS=apis_publicas`.
"""

import os
import re
import threading
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from mock import falhas

from ferramentas import dados_sinteticos
from ferramentas.integracoes import cliente_http
from ferramentas.integracoes.cliente_http import RespostaInvalida
from ferramentas.integracoes.conector import Conector
from ferramentas.integracoes.registro import registrar

VIACEP_PADRAO = "https://viacep.com.br"
PTAX_PADRAO = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
PADRAO_CEP = re.compile(r"[0-9]{8}")
PADRAO_UF = re.compile(r"[A-Z]{2}")
PADRAO_MOEDA = re.compile(r"[A-Z]{3}")
TAMANHO_MAXIMO_CAMPO = 120
SEGUNDOS_DA_LISTA_DE_MOEDAS = 24 * 3600
CEP_DO_TESTE = "01001000"  # Praça da Sé, São Paulo: um CEP público, sem dado de ninguém
SABADO = 5  # date.weekday(): sábado e domingo não têm boletim
FUSO_DA_COTACAO = ZoneInfo("America/Sao_Paulo")
DATA_MINIMA_DA_COTACAO = date(1985, 1, 1)  # corte conservador: a série PTAX começa no fim de 1984
FONTE_VIACEP = "ViaCEP"
FONTE_PTAX = "Banco Central do Brasil (PTAX)"
FONTE_CEP_SIMULADO = "Endereço de exemplo (modo simulado)"
FONTE_COTACAO_SIMULADA = "Valores ilustrativos (modo simulado), não são cotações de verdade"
MENSAGEM_TESTE_SIMULADO = "Modo simulado: CEP e cotação respondem com dados fixos, sem rede."
# Modo simulado: valores ilustrativos, só para a demo e os testes sem rede. Não são cotações de verdade.
MOEDAS_SIMULADAS = {"EUR": "Euro", "GBP": "Libra Esterlina", "USD": "Dólar dos Estados Unidos"}
COTACOES_SIMULADAS = {
    "EUR": (Decimal("6.2000"), Decimal("6.2030")),
    "GBP": (Decimal("7.1000"), Decimal("7.1040")),
    "USD": (Decimal("5.3500"), Decimal("5.3506")),
}
BOLETIM_SIMULADO = "Fechamento PTAX (simulado)"


def _texto(item, campo):
    valor = item.get(campo)
    if not isinstance(valor, str) or len(valor) > TAMANHO_MAXIMO_CAMPO:
        raise RespostaInvalida("resposta fora do formato")
    return valor.strip()


def _endereco_do_viacep(resposta, cep):
    dados = resposta.dados
    if resposta.status == 404:
        return None
    if resposta.status != 200 or not isinstance(dados, dict):
        raise RespostaInvalida("resposta fora do formato")
    if dados.get("erro") in (True, "true"):  # o ViaCEP já usou o booleano e hoje usa o texto
        return None
    if _texto(dados, "cep").replace("-", "") != cep or not PADRAO_UF.fullmatch(_texto(dados, "uf")):
        raise RespostaInvalida("resposta fora do formato")
    return {
        "cep": cep,
        "logradouro": _texto(dados, "logradouro"),
        "bairro": _texto(dados, "bairro"),
        "cidade": _texto(dados, "localidade"),
        "uf": _texto(dados, "uf"),
        "fonte": FONTE_VIACEP,
    }


def _lista_do_odata(resposta):
    dados = resposta.dados
    if resposta.status != 200 or not isinstance(dados, dict) or not isinstance(dados.get("value"), list):
        raise RespostaInvalida("resposta fora do formato")
    if not all(isinstance(item, dict) for item in dados["value"]):
        raise RespostaInvalida("resposta fora do formato")
    return dados["value"]


def _moedas_do_ptax(resposta):
    moedas = {}
    for item in _lista_do_odata(resposta):
        simbolo = _texto(item, "simbolo")
        if not PADRAO_MOEDA.fullmatch(simbolo):
            raise RespostaInvalida("resposta fora do formato")
        moedas[simbolo] = _texto(item, "nomeFormatado")
    if not moedas:
        raise RespostaInvalida("lista de moedas vazia")
    return moedas


def _numero(item, campo):
    valor = item.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise RespostaInvalida("resposta fora do formato")
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise RespostaInvalida("resposta fora do formato") from None
    if not numero.is_finite() or numero <= 0:
        raise RespostaInvalida("resposta fora do formato")
    return numero


def _boletins_do_ptax(resposta):
    if resposta.status == 404:
        return []
    return [
        {
            "compra": _numero(item, "cotacaoCompra"),
            "venda": _numero(item, "cotacaoVenda"),
            "momento": _texto(item, "dataHoraCotacao"),
            "boletim": _texto(item, "tipoBoletim"),
        }
        for item in _lista_do_odata(resposta)
    ]


class ConectorApisPublicas(Conector):
    nome = "apis_publicas"
    rotulo = "APIs públicas (CEP e câmbio)"
    variavel_modo = "APIS_PUBLICAS_MODO"
    modo_padrao = "real"
    variaveis = ("APIS_PUBLICAS_MODO", "VIACEP_URL", "BCB_PTAX_URL")
    servicos = ("viacep", "ptax")
    mensagem_desligada = "As consultas de CEP e de câmbio não estão ligadas nesta plataforma."
    como_ligar = "use APIS_PUBLICAS_MODO=real (internet) ou simulado (dados fixos, sem rede)"
    dica_sem_rede = "Confira a internet ou use APIS_PUBLICAS_MODO=simulado."
    dicas = {
        "VIACEP_URL": "VIACEP_URL inválida: use https:// e só o endereço base, sem ? nem #. Vazia usa a oficial.",
        "BCB_PTAX_URL": "BCB_PTAX_URL inválida: use https:// e só o endereço base, sem ? nem #. Vazia usa a oficial.",
    }

    def __init__(self):
        super().__init__()
        self._trava = threading.Lock()
        self._moedas = {}  # URL base -> (momento, {simbolo: nome}): a lista muda raramente

    def _url_viacep(self, ambiente):
        return cliente_http.url_base(ambiente.get("VIACEP_URL") or VIACEP_PADRAO, "VIACEP_URL")

    def _url_ptax(self, ambiente):
        return cliente_http.url_base(ambiente.get("BCB_PTAX_URL") or PTAX_PADRAO, "BCB_PTAX_URL")

    def conferir_configuracao(self, ambiente=os.environ):
        self._url_viacep(ambiente)
        self._url_ptax(ambiente)

    def fora_do_ar(self):
        return falhas.fora_do_ar("apis_publicas")

    def agora_real(self):
        """O relógio de verdade (Brasília). A suíte de testes troca este método para o dia não mudar sozinho."""
        return datetime.now(FUSO_DA_COTACAO)

    def hoje(self, ambiente=os.environ):
        """O dia de "hoje" para a cotação: o real (Brasília) no modo real, o do mock no simulado."""
        if self.modo(ambiente) == "real":
            return self.agora_real().date()
        return dados_sinteticos.HOJE_DO_MOCK

    def _exigir_no_ar(self, ambiente):
        modo = self.exigir_ligado(ambiente)
        if self.fora_do_ar():
            raise ConnectionError("apis públicas fora do ar (falha simulada)")
        return modo

    def endereco(self, cep, ambiente=os.environ):
        """Endereço do `cep` (8 dígitos): {cep, logradouro, bairro, cidade, uf, fonte}, ou None se não existe."""
        if not PADRAO_CEP.fullmatch(cep):
            raise ValueError("cep fora do formato")
        if self._exigir_no_ar(ambiente) == "simulado":
            endereco = dados_sinteticos.buscar_endereco(cep)
            return None if endereco is None else {**endereco, "fonte": FONTE_CEP_SIMULADO}
        url = f"{self._url_viacep(ambiente)}/ws/{cep}/json/"
        return self.chamar(
            "consultar_cep", lambda: _endereco_do_viacep(cliente_http.pedir("GET", url), cep), servico="viacep"
        )

    def moedas(self, ambiente=os.environ):
        """{simbolo: nome} das moedas que o Banco Central publica (a lista fica guardada por um dia)."""
        if self._exigir_no_ar(ambiente) == "simulado":
            return dict(MOEDAS_SIMULADAS)
        base = self._url_ptax(ambiente)
        with self._trava:
            guardada = self._moedas.get(base)
        if guardada and self._relogio() - guardada[0] < SEGUNDOS_DA_LISTA_DE_MOEDAS:
            return dict(guardada[1])
        url = f"{base}/Moedas?$top=100&$format=json"
        moedas = self.chamar("listar_moedas", lambda: _moedas_do_ptax(cliente_http.pedir("GET", url)), servico="ptax")
        with self._trava:
            self._moedas[base] = (self._relogio(), moedas)
        return dict(moedas)

    def boletins(self, moeda, dia, ambiente=os.environ):
        """Boletins da `moeda` no `dia`: [{compra, venda, momento, boletim}]. Lista vazia: dia sem boletim."""
        if not PADRAO_MOEDA.fullmatch(moeda) or not isinstance(dia, date) or dia < DATA_MINIMA_DA_COTACAO:
            raise ValueError("moeda ou dia fora do formato")
        if self._exigir_no_ar(ambiente) == "simulado":
            if dia.weekday() >= SABADO or moeda not in COTACOES_SIMULADAS:
                return []
            compra, venda = COTACOES_SIMULADAS[moeda]
            momento = f"{dia.isoformat()} 13:10:00.000"
            return [{"compra": compra, "venda": venda, "momento": momento, "boletim": BOLETIM_SIMULADO}]
        url = (
            f"{self._url_ptax(ambiente)}/CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
            f"?@moeda='{moeda}'&@dataCotacao='{dia:%m-%d-%Y}'&$top=100&$format=json"
        )
        return self.chamar("consultar_cotacao", lambda: _boletins_do_ptax(cliente_http.pedir("GET", url)), servico="ptax")

    def testar(self, ambiente=os.environ):
        if self._exigir_no_ar(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        if self.endereco(CEP_DO_TESTE, ambiente) is None:
            raise RespostaInvalida("o CEP de teste não foi encontrado")
        quantas = len(self.moedas(ambiente))
        return f"ViaCEP e PTAX responderam ({quantas} moedas no Banco Central)."

    def reiniciar(self):
        super().reiniciar()
        with self._trava:
            self._moedas.clear()


CONECTOR = registrar(ConectorApisPublicas())
