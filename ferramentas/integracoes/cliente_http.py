"""Cliente HTTP comum dos conectores (httpx), com as proteções de toda integração externa.

- HTTPS obrigatório fora do localhost (`http://` só em localhost, 127.0.0.1 e ::1, para os servidores de teste).
- URL sem usuário, senha, parâmetro ou fragmento no .env: a URL base é fixa, e o modelo nunca escolhe destino.
  O caminho de cada pedido é montado por `montar_url`, que codifica cada pedaço e não deixa sair da base.
- Redirecionamento só para o mesmo esquema, host e porta, no máximo `REDIRECIONAMENTOS` vezes.
- Prazo total do pedido (`tempo_limite`), não só por leitura: um servidor que goteja bytes não segura a chamada.
- Resposta acima de `LIMITE_DE_BYTES`, JSON inválido, 5xx e 429 viram `ConnectionError`; tempo esgotado vira
  `TimeoutError`; 401 e 403 viram `CredencialRecusada`. As mensagens são genéricas: nada de URL ou conteúdo.
- Pedido que muda algo (POST, PUT, PATCH, DELETE) e cai depois de enviado (sem resposta, conexão cortada,
  500, 502 ou 504) vira `base.EfeitoIncerto`: a ação pode ter acontecido, e quem chamou não repete sozinho. O
  mesmo vale quando o servidor respondeu, mas não dá para ler o resultado (2xx com corpo quebrado ou grande
  demais) ou mandou redirecionar: ele recebeu o pedido, e não sabemos o que fez.
- 2xx devolve o JSON lido; 404 volta a quem chamou (costuma ser "não encontrado"); os outros 4xx são pedido
  errado: `ErroFerramenta("parametro_invalido")`, que não conta como falha da integração no disjuntor.
- Os loggers do httpx e do httpcore ficam em WARNING: no nível INFO eles escrevem a URL inteira, com token
  ou parâmetro dentro.
"""

import json
import logging
import time
from typing import NamedTuple
from urllib.parse import quote, urlsplit

import httpx

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes.conector import ConfiguracaoInvalida

HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")
LIMITE_DE_BYTES = 1_000_000
REDIRECIONAMENTOS = 3
TEMPO_LIMITE = 10  # segundos para o pedido inteiro
IDENTIFICACAO_DO_CLIENTE = "PlataformaAgenticaStonelab/1.0"  # o User-Agent dos pedidos
METODOS_QUE_SO_LEEM = ("GET", "HEAD")
STATUS_INCERTOS = (500, 502, 504)  # numa escrita, o servidor pode ter feito a ação antes de falhar
MENSAGEM = "integração indisponível"
MENSAGEM_PEDIDO_RECUSADO = "O serviço recusou o pedido. Confira os dados enviados."

for _nome in ("httpx", "httpcore"):
    logging.getLogger(_nome).setLevel(logging.WARNING)


class LimiteDePedidos(ConnectionError):
    """O serviço respondeu 429: pedidos demais. Tente mais tarde."""


class RespostaInvalida(ConnectionError):
    """O serviço respondeu algo que não dá para usar: grande demais, JSON quebrado ou campo fora do formato."""


class CredencialRecusada(ConnectionError):
    """O serviço respondeu 401 ou 403: a credencial do .env está errada, vencida ou sem permissão."""


class RespostaHttp(NamedTuple):
    status: int
    dados: object  # JSON lido; None sem corpo ou num 404 que não é JSON


class _PrazoTotal(Exception):
    """O pedido passou do `tempo_limite` total enquanto lia a resposta."""


def _local(host):
    return (host or "").lower() in HOSTS_LOCAIS


def _url_permitida(url):
    partes = urlsplit(url)
    if partes.scheme == "https" and partes.hostname:
        return True
    return partes.scheme == "http" and _local(partes.hostname)


def url_base(valor, variavel):
    """Valida a URL base vinda do .env e devolve sem a barra final. Errada: `ConfiguracaoInvalida(variavel)`."""
    texto = (valor or "").strip()
    try:
        partes = urlsplit(texto)
        porta = partes.port  # porta fora do intervalo levanta ValueError
    except ValueError:
        raise ConfiguracaoInvalida(variavel) from None
    sobra = partes.username or partes.password or partes.query or partes.fragment
    if porta == 0 or sobra or not _url_permitida(texto):
        raise ConfiguracaoInvalida(variavel)
    return texto.rstrip("/")


def _mesma_origem(a, b):
    pa, pb = urlsplit(str(a)), urlsplit(str(b))
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)


def montar_url(base, *segmentos):
    """`base` + cada segmento codificado (`/`, `?`, `#` e `..` não escapam). Sai da base: `ValueError`."""
    pedacos = [quote(str(segmento), safe="") for segmento in segmentos]
    if any(pedaco in ("", ".", "..") for pedaco in pedacos):
        raise ValueError("segmento de caminho inválido")
    url = "/".join([base.rstrip("/"), *pedacos])
    if not _mesma_origem(base, url) or not urlsplit(url).path.startswith(urlsplit(base).path):
        raise ValueError("o caminho saiu da URL base")
    return url


def _ler_corpo(resposta, limite_de_bytes, prazo):
    tamanho = resposta.headers.get("content-length", "")
    if tamanho.isdigit() and int(tamanho) > limite_de_bytes:
        raise RespostaInvalida(MENSAGEM)
    corpo = bytearray()
    for pedaco in resposta.iter_bytes():
        corpo.extend(pedaco)
        if len(corpo) > limite_de_bytes:
            raise RespostaInvalida(MENSAGEM)
        if time.monotonic() > prazo:
            raise _PrazoTotal()
    return bytes(corpo)


def _json(corpo, obrigatorio):
    if not corpo.strip():
        return None
    try:
        return json.loads(corpo)
    except (ValueError, UnicodeDecodeError):
        if obrigatorio:
            raise RespostaInvalida(MENSAGEM) from None
        return None


def _seguir(cliente, pedido, limite_de_bytes, prazo):
    """Manda o pedido e segue redirecionamentos da mesma origem. Devolve (status, corpo em bytes).

    Escrita não segue redirecionamento: o servidor já recebeu o pedido, e repetir poderia duplicar a ação.
    """
    so_le = pedido.method in METODOS_QUE_SO_LEEM
    for _ in range(REDIRECIONAMENTOS + 1):
        resposta = cliente.send(pedido, stream=True)
        try:
            if not resposta.is_redirect:
                return resposta.status_code, _ler_corpo(resposta, limite_de_bytes, prazo)
            if not so_le:
                raise EfeitoIncerto()
            destino = resposta.next_request
        finally:
            resposta.close()
        if destino is None or not _mesma_origem(pedido.url, destino.url):
            raise ConnectionError(MENSAGEM)
        pedido = destino
    raise ConnectionError(MENSAGEM)


def _antes_de_enviar(erro):
    """True se o pedido certamente não chegou ao servidor (não conectou ou nem foi montado)."""
    return isinstance(erro, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.UnsupportedProtocol))


def pedir(
    metodo,
    url,
    *,
    parametros=None,
    corpo=None,
    cabecalhos=None,
    tempo_limite=None,
    limite_de_bytes=LIMITE_DE_BYTES,
):
    """Faz o pedido e devolve `RespostaHttp`. Ver as regras no topo do arquivo. Sem `tempo_limite`: `TEMPO_LIMITE`."""
    tempo_limite = TEMPO_LIMITE if tempo_limite is None else tempo_limite
    if not _url_permitida(url):
        raise ConnectionError(MENSAGEM)
    so_le = metodo.upper() in METODOS_QUE_SO_LEEM
    todos_os_cabecalhos = {
        "Accept": "application/json",
        "User-Agent": IDENTIFICACAO_DO_CLIENTE,
        **(cabecalhos or {}),
    }
    local = _local(urlsplit(url).hostname)
    prazo = time.monotonic() + tempo_limite
    try:
        # trust_env só fora do localhost: proxy do sistema nunca intercepta o servidor de teste local.
        with httpx.Client(timeout=tempo_limite, follow_redirects=False, trust_env=not local) as cliente:
            pedido = cliente.build_request(
                metodo, url, params=parametros, json=corpo, headers=todos_os_cabecalhos
            )
            status, conteudo = _seguir(cliente, pedido, limite_de_bytes, prazo)
    except httpx.HTTPError as erro:
        if not so_le and not _antes_de_enviar(erro):
            raise EfeitoIncerto() from None
        if isinstance(erro, httpx.TimeoutException):
            raise TimeoutError(MENSAGEM) from None
        raise ConnectionError(MENSAGEM) from None
    except _PrazoTotal:
        if not so_le:
            raise EfeitoIncerto() from None
        raise TimeoutError(MENSAGEM) from None
    except RespostaInvalida:  # corpo grande demais: numa escrita, o servidor já recebeu o pedido
        if not so_le:
            raise EfeitoIncerto() from None
        raise
    return _interpretar(status, conteudo, so_le)


def _interpretar(status, conteudo, so_le):
    if status == 429:
        raise LimiteDePedidos(MENSAGEM)
    if status in (401, 403):
        raise CredencialRecusada(MENSAGEM)
    if not so_le and status in STATUS_INCERTOS:
        raise EfeitoIncerto()
    if status >= 500 or status < 200 or 300 <= status < 400:
        raise ConnectionError(MENSAGEM)
    if 400 <= status < 500 and status != 404:
        raise ErroFerramenta("parametro_invalido", MENSAGEM_PEDIDO_RECUSADO)
    try:
        dados = _json(conteudo, obrigatorio=status < 300)
    except RespostaInvalida:
        if not so_le:  # 2xx numa escrita: a ação aconteceu, só não dá para ler o resultado
            raise EfeitoIncerto() from None
        raise
    return RespostaHttp(status, dados)
