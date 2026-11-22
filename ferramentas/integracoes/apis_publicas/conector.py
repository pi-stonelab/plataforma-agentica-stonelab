"""APIs públicas: ViaCEP (endereço de um CEP) e PTAX do Banco Central (cotação de moedas).

Modo pelo `APIS_PUBLICAS_MODO`: `real` (padrão, chama as APIs), `simulado` (sem rede: os 3 CEPs de
`dados_sinteticos.py` e cotações fixas, ilustrativas) ou `desligado`. As URLs base vêm do .env (`VIACEP_URL` e
`BCB_PTAX_URL`), com os endereços oficiais como padrão. O formato das respostas segue a documentação pública:
ViaCEP `/ws/{cep}/json/` e PTAX OData `Moedas` e `CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)`.
"""

import os
import re
import threading
from datetime import date
from decimal import Decimal, InvalidOperation

from ferramentas import dados_sinteticos
from ferramentas.integracoes import http
from ferramentas.integracoes.conector import Conector
from ferramentas.integracoes.http import RespostaInvalida
from ferramentas.integracoes.registro import registrar

VIACEP_PADRAO = "https://viacep.com.br"
PTAX_PADRAO = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
CEP_RE = re.compile(r"[0-9]{8}")
UF_RE = re.compile(r"[A-Z]{2}")
MOEDA_RE = re.compile(r"[A-Z]{3}")
TAMANHO_MAXIMO_CAMPO = 120
SEGUNDOS_DA_LISTA_DE_MOEDAS = 24 * 3600
CEP_DO_TESTE = "01001000"  # Praça da Sé, São Paulo: um CEP público, sem dado de ninguém
SABADO = 5
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
    if resposta.status != 200 or not isinstance(dados, dict):
        raise RespostaInvalida("resposta fora do formato")
    if dados.get("erro") in (True, "true"):  # o ViaCEP já usou o booleano e hoje usa o texto
        return None
    if _texto(dados, "cep").replace("-", "") != cep or not UF_RE.fullmatch(_texto(dados, "uf")):
        raise RespostaInvalida("resposta fora do formato")
    return {
        "cep": cep,
        "logradouro": _texto(dados, "logradouro"),
        "bairro": _texto(dados, "bairro"),
        "cidade": _texto(dados, "localidade"),
        "uf": _texto(dados, "uf"),
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
        if not MOEDA_RE.fullmatch(simbolo):
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

    def __init__(self):
        super().__init__()
        self._trava = threading.Lock()
        self._moedas = {}  # URL base -> (momento, {simbolo: nome}): a lista muda raramente

    def _url_viacep(self, ambiente):
        return http.url_base(ambiente.get("VIACEP_URL") or VIACEP_PADRAO, "VIACEP_URL")

    def _url_ptax(self, ambiente):
        return http.url_base(ambiente.get("BCB_PTAX_URL") or PTAX_PADRAO, "BCB_PTAX_URL")

    def conferir_configuracao(self, ambiente=os.environ):
        self._url_viacep(ambiente)
        self._url_ptax(ambiente)

    def endereco(self, cep, ambiente=os.environ):
        """Endereço público do `cep` (8 dígitos): {cep, logradouro, bairro, cidade, uf}, ou None se não existe."""
        if not CEP_RE.fullmatch(cep):
            raise ValueError("cep fora do formato")
        if self.exigir_ligado(ambiente) == "simulado":
            return dados_sinteticos.buscar_endereco(cep)
        url = f"{self._url_viacep(ambiente)}/ws/{cep}/json/"
        return self.chamar(
            "consultar_cep", lambda: _endereco_do_viacep(http.pedir("GET", url), cep), servico="viacep"
        )

    def moedas(self, ambiente=os.environ):
        """{simbolo: nome} das moedas que o Banco Central publica (a lista fica guardada por um dia)."""
        if self.exigir_ligado(ambiente) == "simulado":
            return dict(MOEDAS_SIMULADAS)
        base = self._url_ptax(ambiente)
        with self._trava:
            guardada = self._moedas.get(base)
        if guardada and self._relogio() - guardada[0] < SEGUNDOS_DA_LISTA_DE_MOEDAS:
            return dict(guardada[1])
        url = f"{base}/Moedas?$top=100&$format=json"
        moedas = self.chamar("listar_moedas", lambda: _moedas_do_ptax(http.pedir("GET", url)), servico="ptax")
        with self._trava:
            self._moedas[base] = (self._relogio(), moedas)
        return dict(moedas)

    def boletins(self, moeda, dia, ambiente=os.environ):
        """Boletins da `moeda` no `dia`: [{compra, venda, momento, boletim}]. Lista vazia: dia sem boletim."""
        if not MOEDA_RE.fullmatch(moeda) or not isinstance(dia, date):
            raise ValueError("moeda ou dia fora do formato")
        if self.exigir_ligado(ambiente) == "simulado":
            if dia.weekday() >= SABADO or moeda not in COTACOES_SIMULADAS:
                return []
            compra, venda = COTACOES_SIMULADAS[moeda]
            momento = f"{dia.isoformat()} 13:10:00.000"
            return [{"compra": compra, "venda": venda, "momento": momento, "boletim": BOLETIM_SIMULADO}]
        url = (
            f"{self._url_ptax(ambiente)}/CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
            f"?@moeda='{moeda}'&@dataCotacao='{dia:%m-%d-%Y}'&$top=100&$format=json"
        )
        return self.chamar("consultar_cotacao", lambda: _boletins_do_ptax(http.pedir("GET", url)), servico="ptax")

    def testar(self, ambiente=os.environ):
        if self.endereco(CEP_DO_TESTE, ambiente) is None:
            raise RespostaInvalida("o CEP de teste não foi encontrado")
        quantas = len(self.moedas(ambiente))
        return f"ViaCEP e PTAX responderam ({quantas} moedas no Banco Central)."

    def reiniciar(self):
        super().reiniciar()
        with self._trava:
            self._moedas.clear()


CONECTOR = registrar(ConectorApisPublicas())
