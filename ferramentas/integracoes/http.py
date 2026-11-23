"""Cliente HTTP comum dos conectores (httpx), com as proteções de toda integração externa.

- HTTPS obrigatório fora do localhost (`http://` só em localhost, 127.0.0.1 e ::1, para os servidores de teste).
- URL sem usuário, senha, parâmetro ou fragmento no .env: a URL base é fixa, e o modelo nunca escolhe destino.
- Redirecionamento só para o mesmo esquema, host e porta, no máximo `REDIRECIONAMENTOS` vezes.
- Resposta acima de `LIMITE_DE_BYTES`, JSON inválido, 5xx e 429 viram `ConnectionError`; tempo esgotado vira
  `TimeoutError`. As mensagens são genéricas: nada de URL, parâmetro ou conteúdo.
- 2xx devolve o JSON lido; os outros 4xx voltam a quem chamou (404 costuma ser "não encontrado").
"""

import json
from typing import NamedTuple
from urllib.parse import urlsplit

import httpx

from ferramentas.integracoes.conector import ConfiguracaoInvalida

HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")
LIMITE_DE_BYTES = 1_000_000
REDIRECIONAMENTOS = 3
TEMPO_LIMITE = 10  # segundos por pedido
AGENTE = "PlataformaAgenticaStonelab/1.0"
MENSAGEM = "integração indisponível"


class LimiteDePedidos(ConnectionError):
    """O serviço respondeu 429: pedidos demais. Tente mais tarde."""


class RespostaInvalida(ConnectionError):
    """O serviço respondeu algo que não dá para usar: grande demais, JSON quebrado ou campo fora do formato."""


class RespostaHttp(NamedTuple):
    status: int
    dados: object  # JSON lido; None sem corpo ou num 4xx que não é JSON


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


def _ler_corpo(resposta, limite_de_bytes):
    tamanho = resposta.headers.get("content-length", "")
    if tamanho.isdigit() and int(tamanho) > limite_de_bytes:
        raise RespostaInvalida(MENSAGEM)
    corpo = bytearray()
    for pedaco in resposta.iter_bytes():
        corpo.extend(pedaco)
        if len(corpo) > limite_de_bytes:
            raise RespostaInvalida(MENSAGEM)
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


def _seguir(cliente, pedido, limite_de_bytes):
    """Manda o pedido e segue redirecionamentos da mesma origem. Devolve (status, corpo em bytes)."""
    for _ in range(REDIRECIONAMENTOS + 1):
        resposta = cliente.send(pedido, stream=True)
        try:
            if not resposta.is_redirect:
                return resposta.status_code, _ler_corpo(resposta, limite_de_bytes)
            destino = resposta.next_request
        finally:
            resposta.close()
        if destino is None or not _mesma_origem(pedido.url, destino.url):
            raise ConnectionError(MENSAGEM)
        pedido = destino
    raise ConnectionError(MENSAGEM)


def pedir(
    metodo,
    url,
    *,
    parametros=None,
    corpo=None,
    cabecalhos=None,
    tempo_limite=TEMPO_LIMITE,
    limite_de_bytes=LIMITE_DE_BYTES,
):
    """Faz o pedido e devolve `RespostaHttp`. Ver as regras no topo do arquivo."""
    if not _url_permitida(url):
        raise ConnectionError(MENSAGEM)
    todos_os_cabecalhos = {"Accept": "application/json", "User-Agent": AGENTE, **(cabecalhos or {})}
    local = _local(urlsplit(url).hostname)
    try:
        # trust_env só fora do localhost: proxy do sistema nunca intercepta o servidor de teste local.
        with httpx.Client(timeout=tempo_limite, follow_redirects=False, trust_env=not local) as cliente:
            pedido = cliente.build_request(
                metodo, url, params=parametros, json=corpo, headers=todos_os_cabecalhos
            )
            status, conteudo = _seguir(cliente, pedido, limite_de_bytes)
    except httpx.TimeoutException:
        raise TimeoutError(MENSAGEM) from None
    except httpx.HTTPError:
        raise ConnectionError(MENSAGEM) from None
    if status == 429:
        raise LimiteDePedidos(MENSAGEM)
    if status >= 500 or status < 200 or 300 <= status < 400:
        raise ConnectionError(MENSAGEM)
    return RespostaHttp(status, _json(conteudo, obrigatorio=status < 300))
