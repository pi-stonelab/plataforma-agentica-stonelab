# E-mail (SMTP)

O envio de e-mail da plataforma, pela conta de envio dela (`EMAIL_REMETENTE`), com o primeiro nome de quem
confirmou no remetente e o e-mail dele no "responder para".

## Ferramentas que usam

- `comunicacao/enviar_email` (escrita em duas fases)

## Conector

`conector.py` (`ConectorEmail`) embrulha `ferramentas/email_smtp.py`, que faz o envio. Com `EMAIL_SMTP_HOST`, o modo
é `real`; sem, `desligado` (não há caixa simulada). A saúde é `indisponivel` quando o sistema `email` de
`mock.falhas` está ligado. `python -m ferramentas.integracoes testar email` (com `MODO_TERMINAL=1`) conecta, cifra e
faz o login, sem mandar nada; `python -m ferramentas.email_smtp --testar <endereço>` manda um e-mail de teste.

## Ligação

As variáveis `EMAIL_*` do `.env.example`. TLS obrigatório fora do localhost, com o certificado conferido.

## Hoje

Envio real por SMTP (Gmail com senha de app, por exemplo). Nos testes, um servidor SMTP local
(`backend/tests/apoio_smtp.py`). Ler e-mails (`buscar_emails`) e enviar pela conta de cada pessoa ficam para os
conectores do Google Workspace e do Microsoft 365.
