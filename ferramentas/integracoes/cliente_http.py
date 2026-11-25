"""Cliente HTTP comum dos conectores (httpx), com as proteções de toda integração externa.

- HTTPS obrigatório fora do localhost (`http://` só em localhost, 127.0.0.1 e ::1, para os servidores de teste).
- URL sem usuário, senha, parâmetro ou fragmento no .env: a URL base é fixa, e o modelo nunca escolhe destino.
  O caminho de cada pedido é montado por `montar_url`, que codifica cada pedaço e não deixa sair da base.
- Redirecionamento só para o mesmo esquema, host e porta, no máximo `REDIRECIONAMENTOS` vezes. Exceção pedida
  por quem chama (`seguir_para`, uma lista de domínios): download de arquivo que a API entrega por um endereço
  temporário de outro domínio (Microsoft Graph). O destino precisa ser HTTPS e estar na lista, e o cabeçalho
  `Authorization` não vai junto (o endereço temporário já traz a permissão dentro dele).
- Prazo total do pedido (`tempo_limite`), não só por leitura: um servidor que goteja bytes não segura a chamada.
- Resposta acima de `LIMITE_DE_BYTES`, JSON inválido e 5xx viram `ConnectionError`; tempo esgotado vira
  `TimeoutError`; 401 e 403 viram `CredencialRecusada`; 429 vira `LimiteDePedidos` com os segundos de espera
  (`Retry-After`, ou `parameters.retry_after` do Telegram). Esses dois não contam no disjuntor (`conector.chamar`).
  A `CredencialRecusada` guarda o `status` e o JSON da recusa (`dados`) só para o conector separar "token vencido"
  (401), "falta permissão" e "limite de pedidos" (o Google responde 403 também para limite); nunca vão a mensagem.
  As mensagens são genéricas: nada de URL ou conteúdo.
- Pedido que muda algo (POST, PUT, PATCH, DELETE) e cai depois de enviado (sem resposta, conexão cortada,
  500, 502 ou 504) vira `base.EfeitoIncerto`: a ação pode ter acontecido, e quem chamou não repete sozinho. O
  mesmo vale quando o servidor respondeu, mas não dá para ler o resultado (2xx com corpo quebrado ou grande
  demais) ou mandou redirecionar: ele recebeu o pedido, e não sabemos o que fez.
- 2xx devolve o JSON lido (ou os bytes, com `bruto=True`, para baixar arquivo); 404 volta a quem chamou (costuma ser "não encontrado"); os outros 4xx são pedido
  errado: `PedidoRecusado` (um `ErroFerramenta("parametro_invalido")`), que não conta no disjuntor. O corpo da
  recusa fica em `PedidoRecusado.dados`, para o conector entender o motivo; nunca vai na mensagem.
- Os loggers do httpx e do httpcore ficam em WARNING: no nível INFO eles escrevem a URL inteira, com token
  ou parâmetro dentro. E, se alguém os puser em INFO de novo, `FiltroDeToken` apaga o token do Telegram
  (`/bot<token>/`) de cada linha antes de ela sair.
"""

import json
import logging
import re
import time
from typing import NamedTuple
from urllib.parse import quote, urlsplit

import httpx

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes.conector import (
    ConfiguracaoInvalida,
    CredencialRecusada,
    LimiteDePedidos,
)

HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")
LIMITE_DE_BYTES = 1_000_000
REDIRECIONAMENTOS = 3
TEMPO_LIMITE = 10  # segundos para o pedido inteiro
IDENTIFICACAO_DO_CLIENTE = "PlataformaAgenticaStonelab/1.0"  # o User-Agent dos pedidos
METODOS_QUE_SO_LEEM = ("GET", "HEAD")
STATUS_INCERTOS = (500, 502, 504)  # numa escrita, o servidor pode ter feito a ação antes de falhar
MENSAGEM = "integração indisponível"
MENSAGEM_PEDIDO_RECUSADO = "O serviço recusou o pedido. Confira os dados enviados."

PADRAO_TOKEN_NA_URL = re.compile(r"/bot[^/\s]+/")  # Telegram: /bot<token>/<método>
SEGUNDOS_DE_ESPERA_NO_MAXIMO = 3600
LOGGERS_DO_HTTP = ("httpx", "httpcore", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy")


class FiltroDeToken(logging.Filter):
    """Apaga `/bot<token>/` de toda linha de log dos loggers do httpx, mesmo se alguém os puser em INFO."""

    def filter(self, registro):
        mensagem = registro.getMessage()
        limpa = PADRAO_TOKEN_NA_URL.sub("/bot***/", mensagem)
        if limpa != mensagem:
            registro.msg, registro.args = limpa, ()
        return True


for _nome in LOGGERS_DO_HTTP:
    _logger = logging.getLogger(_nome)
    _logger.setLevel(logging.WARNING)
    if not any(isinstance(f, FiltroDeToken) for f in _logger.filters):
        _logger.addFilter(FiltroDeToken())


class RespostaInvalida(ConnectionError):
    """O serviço respondeu algo que não dá para usar: grande demais, JSON quebrado ou campo fora do formato."""


class RespostaGrandeDemais(RespostaInvalida):
    """A resposta passou do limite de bytes. Não é queda do serviço (ele respondeu o que a pessoa pediu): não conta no
    disjuntor, e quem chamou diz à pessoa para pedir menos."""

    culpa_do_pedido = True


class PedidoRecusado(ErroFerramenta):
    """4xx (fora 401, 403, 404 e 429): o serviço recusou o pedido. `dados`: o JSON da recusa, só para o conector."""

    def __init__(self, status, dados):
        super().__init__("parametro_invalido", MENSAGEM_PEDIDO_RECUSADO)
        self.status = status
        self.dados = dados


def segundos_de_espera(cabecalho, dados=None):
    """Quanto o serviço pediu para esperar: `Retry-After` em segundos ou `parameters.retry_after` (Telegram)."""
    candidatos = [cabecalho]
    if isinstance(dados, dict) and isinstance(dados.get("parameters"), dict):
        candidatos.append(dados["parameters"].get("retry_after"))
    for valor in candidatos:
        texto = str(valor).strip() if valor is not None else ""
        if texto.isdigit():
            return min(int(texto), SEGUNDOS_DE_ESPERA_NO_MAXIMO)
    return None


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


def montar_url(base, *segmentos, seguros=""):
    """`base` + cada segmento codificado (`/`, `?`, `#` e `..` não escapam). Sai da base: `ValueError`.

    `seguros`: caracteres que ficam sem codificar, para a sintaxe de caminho de algumas APIs (os dois-pontos de
    `root:/arquivo.xlsx:/content` do Graph). Nunca passe `/`, `?` ou `#` aqui."""
    if any(caractere in seguros for caractere in "/?#"):
        raise ValueError("caractere seguro inválido")
    pedacos = [quote(str(segmento), safe=seguros) for segmento in segmentos]
    if any(pedaco in ("", ".", "..") for pedaco in pedacos):
        raise ValueError("segmento de caminho inválido")
    url = "/".join([base.rstrip("/"), *pedacos])
    if not _mesma_origem(base, url) or not urlsplit(url).path.startswith(urlsplit(base).path):
        raise ValueError("o caminho saiu da URL base")
    return url


def _ler_corpo(resposta, limite_de_bytes, prazo):
    tamanho = resposta.headers.get("content-length", "")
    if tamanho.isdigit() and int(tamanho) > limite_de_bytes:
        raise RespostaGrandeDemais(MENSAGEM)
    corpo = bytearray()
    for pedaco in resposta.iter_bytes():
        corpo.extend(pedaco)
        if len(corpo) > limite_de_bytes:
            raise RespostaGrandeDemais(MENSAGEM)
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


def _destino_de_redirecionamento_permitido(origem, destino, seguir_para):
    """Mesma origem, ou HTTPS num domínio de `seguir_para` (igual ou subdomínio). Nunca outro caso."""
    if _mesma_origem(origem, destino):
        return True
    if not _url_permitida(str(destino)):
        return False
    host = (destino.host or "").lower()
    return any(host == dominio or host.endswith("." + dominio) for dominio in seguir_para)


def _seguir(cliente, pedido, limite_de_bytes, prazo, seguir_para=()):
    """Manda o pedido e segue redirecionamentos permitidos. Devolve (status, corpo em bytes, Retry-After).

    Escrita não segue redirecionamento: o servidor já recebeu o pedido, e repetir poderia duplicar a ação.
    """
    so_le = pedido.method in METODOS_QUE_SO_LEEM
    for _ in range(REDIRECIONAMENTOS + 1):
        resposta = cliente.send(pedido, stream=True)
        try:
            if not resposta.is_redirect:
                espera = resposta.headers.get("retry-after")
                return resposta.status_code, _ler_corpo(resposta, limite_de_bytes, prazo), espera
            if not so_le:
                raise EfeitoIncerto()
            destino = resposta.next_request
        finally:
            resposta.close()
        if destino is None or not _destino_de_redirecionamento_permitido(pedido.url, destino.url, seguir_para):
            raise ConnectionError(MENSAGEM)
        if not _mesma_origem(pedido.url, destino.url):
            destino.headers.pop("authorization", None)  # o httpx já tira; aqui fica garantido
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
    formulario=None,
    conteudo=None,
    cabecalhos=None,
    tempo_limite=None,
    limite_de_bytes=LIMITE_DE_BYTES,
    bruto=False,
    seguir_para=(),
    repetivel=False,
):
    """Faz o pedido e devolve `RespostaHttp`. Ver as regras no topo do arquivo. Sem `tempo_limite`: `TEMPO_LIMITE`.

    O envio é um só: `corpo` (JSON), `formulario` (application/x-www-form-urlencoded, o formato do endereço de
    token do OAuth) ou `conteudo` (bytes, com o `Content-Type` em `cabecalhos`). `bruto=True` devolve os bytes.
    `repetivel=True` marca o POST que pode ser refeito sem efeito duplicado (renovar e revogar token): vale como leitura."""
    if sum(item is not None for item in (corpo, formulario, conteudo)) > 1:
        raise ValueError("um tipo de corpo por pedido")
    tempo_limite = TEMPO_LIMITE if tempo_limite is None else tempo_limite
    if not _url_permitida(url):
        raise ConnectionError(MENSAGEM)
    so_le = repetivel or metodo.upper() in METODOS_QUE_SO_LEEM
    todos_os_cabecalhos = {
        "Accept": "*/*" if bruto else "application/json",
        "User-Agent": IDENTIFICACAO_DO_CLIENTE,
        **(cabecalhos or {}),
    }
    local = _local(urlsplit(url).hostname)
    prazo = time.monotonic() + tempo_limite
    try:
        # trust_env só fora do localhost: proxy do sistema nunca intercepta o servidor de teste local.
        with httpx.Client(timeout=tempo_limite, follow_redirects=False, trust_env=not local) as cliente:
            pedido = cliente.build_request(
                metodo, url, params=parametros, json=corpo, data=formulario, content=conteudo,
                headers=todos_os_cabecalhos,
            )
            status, resposta_em_bytes, espera = _seguir(cliente, pedido, limite_de_bytes, prazo, tuple(seguir_para))
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
    return _interpretar(status, resposta_em_bytes, so_le, espera, bruto)


def _interpretar(status, conteudo, so_le, espera=None, bruto=False):
    if status == 429:
        raise LimiteDePedidos(MENSAGEM, segundos_de_espera(espera, _json(conteudo, obrigatorio=False)))
    if status in (401, 403):
        recusa = CredencialRecusada(MENSAGEM)
        recusa.status, recusa.dados = status, _json(conteudo, obrigatorio=False)
        raise recusa
    if not so_le and status in STATUS_INCERTOS:
        raise EfeitoIncerto()
    if status >= 500 or status < 200 or 300 <= status < 400:
        raise ConnectionError(MENSAGEM)
    if 400 <= status < 500 and status != 404:
        raise PedidoRecusado(status, _json(conteudo, obrigatorio=False))
    if bruto and status < 300:
        return RespostaHttp(status, conteudo)
    try:
        dados = _json(conteudo, obrigatorio=status < 300)
    except RespostaInvalida:
        if not so_le:  # 2xx numa escrita: a ação aconteceu, só não dá para ler o resultado
            raise EfeitoIncerto() from None
        raise
    return RespostaHttp(status, dados)
