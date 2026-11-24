# Slack

O Slack da Stone: avisos da plataforma em canais internos (plantão, financeiro), pelo bot da plataforma.

## Ferramentas que usam

- `comunicacao/enviar_mensagem_slack` (escrita em duas fases)

## Conector

`conector.py` (`ConectorSlack`) usa a Web API pelo cliente HTTP comum (`integracoes/cliente_http.py`), com o
token de bot no cabeçalho `Authorization: Bearer`. Pedidos:

- `POST https://slack.com/api/chat.postMessage` com `channel`, `text`, `unfurl_links: false` e
  `unfurl_media: false` → `{"ok": true, "channel", "ts"}`
- `GET https://slack.com/api/auth.test` só no `testar` (não publica nada)

O Slack responde 200 também quando recusa (`{"ok": false, "error": "..."}`): canal inexistente, bot fora do
canal ou canal arquivado viram "nada foi enviado, avise quem administra"; token inválido ou sem escopo conta
como credencial recusada; `ratelimited` conta no disjuntor. Escrita sem resposta vira "pode ter saído".
Fonte: https://docs.slack.dev/reference/methods/chat.postMessage e
https://docs.slack.dev/reference/methods/auth.test.

Regras: o modelo e a pessoa só usam o apelido do canal (`SLACK_CANAIS`); o ID fica no `.env`. O texto passa pela
máscara de texto livre antes da prévia e sai assinado com o primeiro nome de quem confirmou.

## Ligação

1. Em api.slack.com/apps, crie um app no workspace da empresa, dê o escopo de bot `chat:write` e instale; copie
   o "Bot User OAuth Token" (começa com `xoxb-`).
2. Convide o bot em cada canal liberado (`/invite @nome-do-bot`) e copie o ID do canal (detalhes do canal, no
   fim da janela; começa com `C` ou `G`).
3. No `.env`: `SLACK_TOKEN=xoxb-...` e `SLACK_CANAIS=plantao:C0123ABCD,financeiro:C0456EFGH`.
4. `MODO_TERMINAL=1 python -m ferramentas.integracoes testar slack` confere o token, sem publicar nada.

Sem token, a integração fica desligada e a ferramenta some do que o modelo vê. `SLACK_MODO=simulado` guarda as
mensagens em memória (canais de exemplo `plantao` e `financeiro` quando não há lista) e diz isso em `fonte`.

## Hoje

Conector real pronto. Nos testes, um servidor HTTP local no formato da Web API
(`backend/tests/apoio_integracoes_externas.py`). O sistema `slack` de `mock.falhas` derruba a integração na demo.
