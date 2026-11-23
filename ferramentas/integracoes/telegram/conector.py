"""Telegram (Bot API): aviso num chat da lista permitida, pelo bot da plataforma.

Configuração (.env): `TELEGRAM_TOKEN` (o token que o @BotFather entrega, como `123456789:AA...`) e
`TELEGRAM_CHATS` (`apelido:chat_id` separados por vírgula, como `plantao:-1001234567890`). O modelo e a pessoa
só usam o apelido; o número do chat fica no .env. Preencher o `TELEGRAM_TOKEN` liga a integração;
`TELEGRAM_MODO` força `real`, `simulado` ou `desligado`. `TELEGRAM_URL` só existe para os testes (padrão:
https://api.telegram.org).

O token vai no caminho da URL (`/bot<token>/sendMessage`), como a Bot API exige. Por isso ele é conferido por
formato antes de entrar na URL, os loggers do httpx ficam calados (`cliente_http`) e nenhum erro, log ou estado
leva a URL. O texto vai sem formatação (sem `parse_mode`) e sem prévia de link. No modo simulado, o aviso fica
em memória (`AvisosSimulados`) e a resposta diz isso em `fonte`.

Pedidos (documentação oficial: https://core.telegram.org/bots/api#sendmessage e #getme):
- POST /bot<token>/sendMessage  {"chat_id": ..., "text": ..., "link_preview_options": {"is_disabled": true}}
                                 → {"ok": true, "result": {"message_id": 123, ...}}
- GET  /bot<token>/getMe        → {"ok": true, "result": {"is_bot": true, "username": ...}}   (só o `testar`)
Erros: {"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}; 401 token inválido;
403 bot bloqueado ou fora do chat; 429 pedidos demais.
"""

import os
import re
import threading
from collections import deque

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http
from ferramentas.integracoes.cliente_http import RespostaInvalida
from ferramentas.integracoes.conector import Conector, ConfiguracaoInvalida, ler_destinos
from ferramentas.integracoes.registro import registrar
from mock import falhas

TELEGRAM_PADRAO = "https://api.telegram.org"
PADRAO_TOKEN = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{30,60}")
PADRAO_CHAT = re.compile(r"-?[0-9]{1,20}")
TAMANHO_MAXIMO_DO_TEXTO = 4096  # limite da Bot API por mensagem
FONTE_REAL = "Telegram"
FONTE_SIMULADA = "Telegram simulado (modo de demonstração): nada foi enviado ao Telegram de verdade"
MENSAGEM_TESTE_SIMULADO = "Modo simulado: os avisos ficam na memória da plataforma, sem chamar o Telegram."
MENSAGEM_CHAT_RECUSOU = (
    "O Telegram não aceitou o aviso no chat {apelido}: o chat não existe ou o bot não está nele. Nada foi"
    " enviado; avise quem administra a plataforma."
)
LIMITE_DE_SIMULADOS = 50
CHATS_SIMULADOS = {"plantao": "-1000000000001"}  # modo simulado sem TELEGRAM_CHATS


class AvisosSimulados:
    """Os avisos do modo simulado, em memória e só os últimos `LIMITE_DE_SIMULADOS` (testes e demo)."""

    def __init__(self):
        self._trava = threading.Lock()
        self._avisos = deque(maxlen=LIMITE_DE_SIMULADOS)
        self._contador = 0

    def enviar(self, apelido, texto):
        with self._trava:
            self._contador += 1
            self._avisos.append({"id_mensagem": self._contador, "chat": apelido, "texto": texto})
            return self._contador

    def listar(self):
        with self._trava:
            return [dict(aviso) for aviso in self._avisos]

    def limpar(self):
        with self._trava:
            self._avisos.clear()
            self._contador = 0


def _id_da_mensagem(dados):
    """O `message_id` do aviso enviado. Resposta 2xx sem ele: o Telegram recebeu e não sabemos o resultado."""
    resultado = dados.get("result") if isinstance(dados, dict) and dados.get("ok") is True else None
    id_mensagem = resultado.get("message_id") if isinstance(resultado, dict) else None
    if isinstance(id_mensagem, bool) or not isinstance(id_mensagem, int):
        raise EfeitoIncerto()
    return id_mensagem


class ConectorTelegram(Conector):
    nome = "telegram"
    rotulo = "Telegram"
    variavel_modo = "TELEGRAM_MODO"
    modo_padrao = "desligado"
    variavel_que_liga = "TELEGRAM_TOKEN"
    variaveis = ("TELEGRAM_MODO", "TELEGRAM_TOKEN", "TELEGRAM_CHATS", "TELEGRAM_URL")
    credencial = "plataforma"
    mensagem_desligada = "O envio de avisos pelo Telegram não está ligado nesta plataforma."
    como_ligar = "preencha TELEGRAM_TOKEN e TELEGRAM_CHATS (ou use TELEGRAM_MODO=simulado)"
    dica_sem_rede = "Confira a internet, ou use TELEGRAM_MODO=simulado."
    dicas = {
        "TELEGRAM_TOKEN": "TELEGRAM_TOKEN inválido: use o token que o @BotFather entregou, como 123456789:AA...",
        "TELEGRAM_CHATS": (
            "TELEGRAM_CHATS inválida: apelido:chat_id separados por vírgula, como plantao:-1001234567890. O apelido"
            " usa letras minúsculas, números, - e _."
        ),
        "TELEGRAM_URL": "TELEGRAM_URL inválida: deixe vazia (usa https://api.telegram.org).",
    }

    def __init__(self):
        super().__init__()
        self.simulados = AvisosSimulados()

    def _token(self, ambiente):
        token = ambiente.get("TELEGRAM_TOKEN", "").strip()
        if not PADRAO_TOKEN.fullmatch(token):
            raise ConfiguracaoInvalida("TELEGRAM_TOKEN")
        return token

    def _url_do_metodo(self, ambiente, metodo):
        """`<base>/bot<token>/<metodo>`. O token já passou pelo `PADRAO_TOKEN` (sem `/`, `?` ou `#`), então vai
        como está: o `montar_url` codificaria o `:` do token, que a Bot API espera literal."""
        base = cliente_http.url_base(ambiente.get("TELEGRAM_URL") or TELEGRAM_PADRAO, "TELEGRAM_URL")
        return f"{base}/bot{self._token(ambiente)}/{metodo}"

    def chats(self, ambiente=os.environ):
        """{apelido: chat_id} dos chats liberados no .env. No simulado sem lista: o de exemplo."""
        chats = ler_destinos(ambiente, "TELEGRAM_CHATS", PADRAO_CHAT)
        if not chats and self.modo(ambiente) == "simulado":
            return dict(CHATS_SIMULADOS)
        return chats

    def conferir_configuracao(self, ambiente=os.environ):
        self._url_do_metodo(ambiente, "getMe")
        if not self.chats(ambiente):
            raise ConfiguracaoInvalida("TELEGRAM_CHATS")

    def fora_do_ar(self):
        return falhas.fora_do_ar("telegram")

    def _ligado(self, ambiente):
        modo = self.exigir_ligado(ambiente)
        if self.fora_do_ar():
            raise ConnectionError("telegram fora do ar (falha simulada)")
        return modo

    def apelidos(self, ambiente=os.environ):
        return sorted(self.chats(ambiente))

    def enviar(self, apelido, texto, ambiente=os.environ):
        """Manda `texto` ao chat do `apelido` e devolve o id da mensagem."""
        modo = self._ligado(ambiente)
        chats = self.chats(ambiente)
        self.exigir_destino(apelido, chats)
        if modo == "simulado":
            return self.simulados.enviar(apelido, texto)
        url = self._url_do_metodo(ambiente, "sendMessage")
        corpo = {"chat_id": chats[apelido], "text": texto, "link_preview_options": {"is_disabled": True}}

        def enviar_aviso():
            try:
                resposta = cliente_http.pedir("POST", url, corpo=corpo)
            except ErroFerramenta:  # 400 do Telegram: quase sempre "chat not found"; nada foi enviado
                raise ErroFerramenta("integracao_indisponivel", MENSAGEM_CHAT_RECUSOU.format(apelido=apelido)) from None
            if resposta.status == 404:  # sem esse método: a URL base ou o token não são da Bot API
                raise ConnectionError(cliente_http.MENSAGEM)
            return _id_da_mensagem(resposta.dados)

        return self.chamar("enviar", enviar_aviso)

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        url = self._url_do_metodo(ambiente, "getMe")
        dados = self.chamar("testar", lambda: cliente_http.pedir("GET", url).dados)
        bot = dados.get("result") if isinstance(dados, dict) and dados.get("ok") is True else None
        if not isinstance(bot, dict) or bot.get("is_bot") is not True:
            raise RespostaInvalida("resposta fora do formato")
        nome = bot.get("username") if isinstance(bot.get("username"), str) else "sem nome"
        return f"O Telegram aceitou o token do bot @{nome}. Chats liberados: {', '.join(self.apelidos(ambiente))}."

    def reiniciar(self):
        super().reiniciar()
        self.simulados.limpar()


CONECTOR = registrar(ConectorTelegram())
