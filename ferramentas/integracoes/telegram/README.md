# Telegram

Avisos da plataforma em chats internos do Telegram (grupo de plantão, por exemplo), pelo bot da plataforma.

## Ferramentas que usam

- `comunicacao/enviar_aviso_telegram` (escrita em duas fases)

## Conector

`conector.py` (`ConectorTelegram`) usa a Bot API pelo cliente HTTP comum (`integracoes/cliente_http.py`):

- `POST https://api.telegram.org/bot<token>/sendMessage` com `chat_id`, `text` e
  `link_preview_options: {"is_disabled": true}` → `{"ok": true, "result": {"message_id": ...}}`
- `GET https://api.telegram.org/bot<token>/getMe` só no `testar`

Fonte: https://core.telegram.org/bots/api#sendmessage e https://core.telegram.org/bots/api#getme.

O token vai no caminho da URL, como a Bot API exige. Por isso: ele é conferido por formato antes de entrar na
URL, os loggers do httpx ficam calados, e nenhum erro, log, estado ou exceção leva a URL (há teste para cada
tipo de falha). O texto vai sem formatação (`parse_mode` ausente) e sem prévia de link. 400 ("chat not found")
e 403 (bot fora do chat ou bloqueado) viram "nada foi enviado, avise quem administra"; 401 é token recusado;
429 e 5xx contam no disjuntor; escrita sem resposta vira "pode ter saído".

Regras: o modelo e a pessoa só usam o apelido do chat (`TELEGRAM_CHATS`); o número fica no `.env`. O texto passa
pela máscara de texto livre antes da prévia e sai assinado com o primeiro nome de quem confirmou.

## Ligação

1. No Telegram, fale com o @BotFather, crie um bot (`/newbot`) e copie o token (`123456789:AA...`).
2. Adicione o bot ao grupo liberado e descubra o `chat_id` do grupo (para grupos, um número negativo, como
   `-1001234567890`).
3. No `.env`: `TELEGRAM_TOKEN=<token>` e `TELEGRAM_CHATS=plantao:-1001234567890`.
4. `MODO_TERMINAL=1 python -m ferramentas.integracoes testar telegram` confere o token e mostra o nome do bot,
   sem enviar nada.

Sem token, a integração fica desligada e a ferramenta some do que o modelo vê. `TELEGRAM_MODO=simulado` guarda os
avisos em memória (chat de exemplo `plantao` quando não há lista) e diz isso em `fonte`.

## Hoje

Conector real pronto. Nos testes, um servidor HTTP local no formato da Bot API
(`backend/tests/apoio_integracoes_externas.py`). O sistema `telegram` de `mock.falhas` derruba a integração.
