# comunicacao

Mensagens: e-mail com o lojista e avisos para colegas no Slack e no Telegram.

## Como escolher

- Escrever ao lojista: a ferramenta de e-mail, que vai para um contato cadastrado dele.
- Ver o que o lojista respondeu por e-mail: a de buscar e-mails.
- Avisar colegas da Stone: a de Slack (canal interno) ou a de Telegram (grupo interno).
- As de envio só montam a prévia: quem envia é o funcionário, ao confirmar na tela.
- Use só as que aparecem na lista abaixo: as outras não estão liberadas para você.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integrações da área: `email` (SMTP), `email_leitura` (IMAP), `slack`, `telegram`.
- Ferramentas ativas (4):
  - `buscar_emails` (leitura)
  - `enviar_email` (escrita em duas fases)
  - `enviar_mensagem_slack` (escrita em duas fases)
  - `enviar_aviso_telegram` (escrita em duas fases)
- Integração desligada no `.env` tira a ferramenta do índice do modelo.
