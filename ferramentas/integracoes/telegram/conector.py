"""Telegram (Bot API): aviso num chat da lista permitida, pelo bot da plataforma.

Configuração (.env): `TELEGRAM_TOKEN` (o token que o @BotFather entrega, como `123456789:AA...`) e
`TELEGRAM_CHATS` (`apelido:chat_id[:Nome]` separados por vírgula, como `plantao:-1001234567890:Plantão`). O
modelo e a pessoa só usam o apelido; o número do chat fica no .env, e o nome (opcional) aparece no cartão. Preencher o `TELEGRAM_TOKEN` liga a integração;
`TELEGRAM_MODO` força `real`, `simulado` ou `desligado`. `TELEGRAM_URL` só existe para os testes (padrão:
https://api.telegram.org).

O token vai no caminho da URL (`/bot<token>/sendMessage`), como a Bot API exige. Por isso ele é conferido por
formato antes de entrar na URL, os loggers do httpx ficam calados e com o `FiltroDeToken` (`cliente_http`), e
nenhum erro, log ou estado leva a URL. O texto vai sem formatação (sem `parse_mode`) e sem prévia de link. No
modo simulado, o aviso fica na caixa de saída simulada (`simuladas.py`) e a resposta diz isso em `fonte`.

Recusa 400: a `description` diz o motivo ("Bad Request: chat not found", "message is too long"); ela decide a
mensagem, mas nunca é repetida. 429: `parameters.retry_after` diz quanto esperar.

Pedidos (documentação oficial: https://core.telegram.org/bots/api#sendmessage e #getme):
- POST /bot<token>/sendMessage  {"chat_id": ..., "text": ..., "link_preview_options": {"is_disabled": true}}
                                 → {"ok": true, "result": {"message_id": 123, ...}}
- GET  /bot<token>/getMe        → {"ok": true, "result": {"is_bot": true, "username": ...}}   (só o `testar`)
- GET  /bot<token>/getChat?chat_id=...  → {"ok": true, "result": {"id": ..., "title": ...}}   (só o `testar`)
Erros: {"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}; 401 token inválido;
403 bot bloqueado ou fora do chat; 429 pedidos demais.
"""

import os
import re

from ferramentas.base import EfeitoIncerto, ErroFerramenta
from ferramentas.integracoes import cliente_http, simuladas
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida
from ferramentas.integracoes.conector import (
    Conector,
    ConfiguracaoInvalida,
    ler_destinos,
    ler_rotulos,
)
from ferramentas.integracoes.registro import registrar

TELEGRAM_PADRAO = "https://api.telegram.org"
PADRAO_TOKEN = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{30,60}")
PADRAO_CHAT = re.compile(r"-?[0-9]{1,20}")
TAMANHO_MAXIMO_DO_TEXTO = 4096  # limite da Bot API por mensagem
FONTE_REAL = "Telegram"
FONTE_SIMULADA = "Telegram simulado (modo de demonstração): nada foi enviado ao Telegram de verdade"
MENSAGEM_TESTE_SIMULADO = (
    "Modo simulado: os avisos ficam na caixa de saída simulada da plataforma, sem chamar o Telegram"
    " (python -m ferramentas.integracoes simuladas mostra o que teria saído)."
)
MENSAGEM_CHAT_RECUSOU = (
    "O Telegram não aceitou o aviso no chat {apelido}: o chat não existe ou o bot não está nele. Nada foi"
    " enviado; avise quem administra a plataforma."
)
MENSAGEM_TEXTO_LONGO = "O Telegram recusou o aviso porque ficou longo demais. Encurte o texto. Nada foi enviado."
MENSAGEM_RECUSA = "O Telegram recusou o aviso. Nada foi enviado."
CHATS_SIMULADOS = {"plantao": "-1000000000001"}  # modo simulado sem TELEGRAM_CHATS
ROTULOS_SIMULADOS = {"plantao": "Plantão (demonstração)"}


def _motivo_da_recusa(dados):
    """`chat`, `texto` ou None, pela `description` do Telegram (que nunca é repetida para ninguém)."""
    descricao = dados.get("description", "") if isinstance(dados, dict) else ""
    descricao = descricao.casefold() if isinstance(descricao, str) else ""
    if "chat not found" in descricao or "not a member" in descricao or "kicked" in descricao:
        return "chat"
    if "too long" in descricao or "text must be non-empty" in descricao:
        return "texto"
    return None


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
        self.simuladas = simuladas.caixa(self.nome)

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

    def rotulos(self, ambiente=os.environ):
        """{apelido: nome legível} dos chats com nome no .env (no simulado, o de exemplo)."""
        if not ler_destinos(ambiente, "TELEGRAM_CHATS", PADRAO_CHAT) and self.modo(ambiente) == "simulado":
            return dict(ROTULOS_SIMULADOS)
        return ler_rotulos(ambiente, "TELEGRAM_CHATS")

    def conferir_configuracao(self, ambiente=os.environ):
        self._url_do_metodo(ambiente, "getMe")
        if not self.chats(ambiente):
            raise ConfiguracaoInvalida("TELEGRAM_CHATS")

    def apelidos(self, ambiente=os.environ):
        return sorted(self.chats(ambiente))

    def enviar(self, apelido, texto, ambiente=os.environ):
        """Manda `texto` ao chat do `apelido` e devolve o id da mensagem."""
        modo = self._ligado(ambiente)
        chats = self.chats(ambiente)
        self.exigir_destino(apelido, chats)
        if modo == "simulado":
            return self.simuladas.guardar(apelido, texto)
        url = self._url_do_metodo(ambiente, "sendMessage")
        corpo = {"chat_id": chats[apelido], "text": texto, "link_preview_options": {"is_disabled": True}}

        def enviar_aviso():
            try:
                resposta = cliente_http.pedir("POST", url, corpo=corpo)
            except PedidoRecusado as recusa:  # 400: nada foi enviado; a `description` diz o motivo
                motivo = _motivo_da_recusa(recusa.dados)
                if motivo == "chat":
                    mensagem = MENSAGEM_CHAT_RECUSOU.format(apelido=apelido)
                    raise ErroFerramenta("integracao_indisponivel", mensagem) from None
                if motivo == "texto":
                    raise ErroFerramenta("parametro_invalido", MENSAGEM_TEXTO_LONGO) from None
                raise ErroFerramenta("parametro_invalido", MENSAGEM_RECUSA) from None
            if resposta.status == 404:  # sem esse método: a URL base ou o token não são da Bot API
                raise ConnectionError(cliente_http.MENSAGEM)
            return _id_da_mensagem(resposta.dados)

        return self.chamar("enviar", enviar_aviso)

    def _conferir_chat(self, ambiente, apelido, chat_id):
        """Uma frase sobre o chat: o bot vê o chat, ou o que falta (sem mandar nada)."""
        url = self._url_do_metodo(ambiente, "getChat")
        try:
            dados = self.chamar("testar", lambda: cliente_http.pedir("GET", url, parametros={"chat_id": chat_id}).dados)
        except PedidoRecusado:
            return f"{apelido}: chat não encontrado, ou o bot não está nele (adicione o bot ao grupo)."
        chat = dados.get("result") if isinstance(dados, dict) and dados.get("ok") is True else None
        if not isinstance(chat, dict):
            return f"{apelido}: o Telegram respondeu fora do formato."
        return f"{apelido}: ok."

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return MENSAGEM_TESTE_SIMULADO
        url = self._url_do_metodo(ambiente, "getMe")
        dados = self.chamar("testar", lambda: cliente_http.pedir("GET", url).dados)
        bot = dados.get("result") if isinstance(dados, dict) and dados.get("ok") is True else None
        if not isinstance(bot, dict) or bot.get("is_bot") is not True:
            raise RespostaInvalida("resposta fora do formato")
        nome = bot.get("username") if isinstance(bot.get("username"), str) else "sem nome"
        linhas = [f"O Telegram aceitou o token do bot @{nome}."]
        linhas += [self._conferir_chat(ambiente, a, c) for a, c in sorted(self.chats(ambiente).items())]
        return " ".join(linhas)

    def descobrir(self, ambiente=os.environ):
        """Os chats em que o bot recebeu mensagem recentemente (getUpdates): [(título, chat_id)], sem o texto.

        Para quem configura achar o `chat_id` sem abrir a URL com o token no navegador."""
        if self._ligado(ambiente) == "simulado":
            return [(rotulo, CHATS_SIMULADOS[apelido]) for apelido, rotulo in ROTULOS_SIMULADOS.items()]
        url = self._url_do_metodo(ambiente, "getUpdates")
        dados = self.chamar("testar", lambda: cliente_http.pedir("GET", url).dados)
        atualizacoes = dados.get("result") if isinstance(dados, dict) and dados.get("ok") is True else None
        if not isinstance(atualizacoes, list):
            raise RespostaInvalida("resposta fora do formato")
        chats = {}
        for atualizacao in atualizacoes:
            for chave in ("message", "channel_post", "my_chat_member"):
                chat = atualizacao.get(chave, {}).get("chat") if isinstance(atualizacao, dict) else None
                if isinstance(chat, dict) and isinstance(chat.get("id"), int):
                    titulo = chat.get("title") or chat.get("first_name") or "conversa sem título"
                    chats[chat["id"]] = str(titulo)[:60]
        return [(titulo, str(chat_id)) for chat_id, titulo in chats.items()]

    def reiniciar(self):
        super().reiniciar()
        self.simuladas.limpar()


CONECTOR = registrar(ConectorTelegram())
