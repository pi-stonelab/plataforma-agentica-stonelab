"""Servidor HTTP de teste, em socket de verdade, para os conectores de `ferramentas/integracoes/`.

`ServidorHttp(responder)` sobe um `ThreadingHTTPServer` em 127.0.0.1, numa porta livre, e chama
`responder(metodo, caminho_com_query)` para cada pedido; a função devolve `(status, cabecalhos, corpo)`.
Os pedidos ficam em `servidor.pedidos` (método e caminho, nunca corpo).

`responder_das_apis_publicas` fala como o ViaCEP (`/ws/{cep}/json/`) e como a PTAX do Banco Central (OData
`Moedas` e `CotacaoMoedaDia`), com os campos e formatos da documentação pública. Os valores são inventados.
A suíte inteira usa um servidor destes (`ambiente_da_suite`): nenhum teste vai à internet.
"""

import json
import re
import socket
import threading
import time
from contextlib import contextmanager
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ferramentas import dados_sinteticos

CAMINHO_PTAX = "/olinda/servico/PTAX/versao/v1/odata"
JSON = {"Content-Type": "application/json; charset=utf-8"}

# Formato do ViaCEP: os campos que a API devolve hoje. Os 3 CEPs de dados_sinteticos e o da Praça da Sé.
_EXTRAS_DO_VIACEP = dict.fromkeys(("complemento", "unidade", "estado", "regiao", "ibge", "gia", "ddd", "siafi"), "")
CEPS = {
    **{cep: dados_sinteticos.buscar_endereco(cep) for cep in dados_sinteticos.ENDERECOS},
    "01001000": {"cep": "01001000", "logradouro": "Praça da Sé", "bairro": "Sé", "cidade": "São Paulo", "uf": "SP"},
}

MOEDAS = (
    ("AUD", "Dólar australiano", "B"),
    ("CAD", "Dólar canadense", "A"),
    ("CHF", "Franco suíço", "A"),
    ("EUR", "Euro", "B"),
    ("GBP", "Libra Esterlina", "B"),
    ("JPY", "Iene", "A"),
    ("USD", "Dólar dos Estados Unidos", "A"),
)
FERIADO = date(2026, 10, 12)  # Nossa Senhora Aparecida, segunda-feira: o Banco Central não publica
PRIMEIRO_DIA = date(2026, 9, 21)
ULTIMO_DIA = date(2026, 10, 15)  # o HOJE_DO_MOCK
BASE_POR_MOEDA = {"USD": 5.3, "EUR": 6.2, "GBP": 7.1, "AUD": 3.5, "CAD": 3.9, "CHF": 6.6, "JPY": 0.036}


def _boletins(moeda, dia):
    """Quatro boletins por dia útil (abertura, dois intermediários e o fechamento), valores inventados."""
    if dia.weekday() >= 5 or dia == FERIADO or not PRIMEIRO_DIA <= dia <= ULTIMO_DIA:
        return []
    base = BASE_POR_MOEDA[moeda] + (dia - PRIMEIRO_DIA).days / 1000
    tipos = (
        ("Abertura", "10:04"),
        ("Intermediário", "11:04"),
        ("Intermediário", "12:04"),
        ("Fechamento PTAX", "13:04"),
    )
    return [
        {
            "paridadeCompra": 1.0,
            "paridadeVenda": 1.0,
            "cotacaoCompra": round(base + indice / 10000, 4),
            "cotacaoVenda": round(base + indice / 10000 + 0.0006, 4),
            "dataHoraCotacao": f"{dia.isoformat()} {hora}:23.355",
            "tipoBoletim": tipo,
        }
        for indice, (tipo, hora) in enumerate(tipos)
    ]


def boletim_de_fechamento(moeda, dia):
    return _boletins(moeda, dia)[-1]


def _resposta_json(dados, status=200):
    return status, JSON, json.dumps(dados, ensure_ascii=False).encode()


def _odata(itens):
    return _resposta_json({"@odata.context": "https://olinda.bcb.gov.br/$metadata", "value": itens})


COTACAO_RE = re.compile(r".*/CotacaoMoedaDia\(moeda=@moeda,dataCotacao=@dataCotacao\)$")
CEP_RE = re.compile(r"/ws/([^/]*)/json/$")


def responder_das_apis_publicas(metodo, caminho):
    partes = urlsplit(caminho)
    consulta = parse_qs(partes.query)
    if (achado := CEP_RE.fullmatch(partes.path)) is not None:
        cep = achado.group(1)
        if not re.fullmatch(r"[0-9]{8}", cep):
            return 400, {"Content-Type": "text/html"}, b"<h1>Bad Request</h1>"
        if cep not in CEPS:
            return _resposta_json({"erro": "true"})
        endereco = CEPS[cep]
        return _resposta_json(
            {
                "cep": f"{cep[:5]}-{cep[5:]}",
                "logradouro": endereco["logradouro"],
                "bairro": endereco["bairro"],
                "localidade": endereco["cidade"],
                "uf": endereco["uf"],
                **_EXTRAS_DO_VIACEP,
            }
        )
    if partes.path.endswith("/Moedas"):
        return _odata([{"simbolo": s, "nomeFormatado": n, "tipoMoeda": t} for s, n, t in MOEDAS])
    if COTACAO_RE.fullmatch(partes.path):
        moeda = consulta.get("@moeda", [""])[0].strip("'")
        texto_dia = consulta.get("@dataCotacao", [""])[0].strip("'")
        mes, dia, ano = (int(parte) for parte in texto_dia.split("-"))
        if moeda not in BASE_POR_MOEDA:
            return _odata([])
        return _odata(_boletins(moeda, date(ano, mes, dia)))
    return 404, JSON, b'{"erro": "nao encontrado"}'


class _Atendimento(BaseHTTPRequestHandler):
    def _atender(self):
        servidor = self.server
        servidor.pedidos.append((self.command, self.path))
        self.rfile.read(int(self.headers.get("Content-Length") or 0))  # sem ler o corpo, o Windows reinicia a conexão
        if servidor.atraso:
            time.sleep(servidor.atraso)
        status, cabecalhos, corpo = servidor.responder(self.command, self.path)
        self.send_response(status)
        for nome, valor in cabecalhos.items():
            self.send_header(nome, valor)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    do_GET = do_POST = _atender

    def log_message(self, *args):  # o servidor de teste não escreve no terminal
        return


class ServidorHttp(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, responder=responder_das_apis_publicas, atraso=0.0):
        super().__init__(("127.0.0.1", 0), _Atendimento)
        self.responder = responder
        self.atraso = atraso
        self.pedidos = []
        self._linha = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    @property
    def porta(self):
        return self.server_address[1]

    @property
    def url(self):
        return f"http://127.0.0.1:{self.porta}"

    def __enter__(self):
        self._linha.start()
        return self

    def __exit__(self, *erro):
        self.shutdown()
        self.server_close()


def ambiente_das_apis_publicas(servidor):
    return {"APIS_PUBLICAS_MODO": "real", "VIACEP_URL": servidor.url, "BCB_PTAX_URL": servidor.url + CAMINHO_PTAX}


_DA_SUITE = []


def ambiente_da_suite():
    """Sobe (uma vez) o servidor das APIs públicas da suíte e devolve as variáveis que apontam para ele."""
    if not _DA_SUITE:
        _DA_SUITE.append(ServidorHttp().__enter__())
    return ambiente_das_apis_publicas(_DA_SUITE[0])


def dia_util_anterior(dia):
    dia -= timedelta(days=1)
    while dia.weekday() >= 5 or dia == FERIADO:
        dia -= timedelta(days=1)
    return dia


@contextmanager
def porta_que_recusa():
    """URL de uma porta local que recusa conexão na hora: o socket fica ligado sem `listen` durante o uso,
    então nenhum outro servidor do teste pega a mesma porta por acaso."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupada:
        ocupada.bind(("127.0.0.1", 0))
        yield f"http://127.0.0.1:{ocupada.getsockname()[1]}"
