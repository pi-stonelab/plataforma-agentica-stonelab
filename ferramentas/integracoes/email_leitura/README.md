# E-mail, leitura (IMAP)

A caixa de e-mail da plataforma: onde chegam as respostas dos lojistas aos e-mails que a plataforma envia
(`email/`, SMTP). Integração separada do envio: outro servidor, outra credencial e outra chave de liga e desliga.

## Ferramentas que usam

- `comunicacao/buscar_emails` (leitura)

## Conector

`conector.py` (`ConectorEmailLeitura`) usa o `imaplib` da biblioteca padrão (IMAP4rev1, RFC 3501):

- Conexão cifrada fora do localhost (`ssl` na porta 993, ou `starttls` na 143), com o certificado conferido.
- `EXAMINE` (a pasta abre só para leitura), `SEARCH` com `FROM` dos contatos do lojista e o período, e
  `FETCH` com `BODY.PEEK` (nenhuma mensagem fica marcada como lida).
- Nada do modelo vai ao comando IMAP: os remetentes vêm do cadastro do lojista e o filtro de assunto é feito
  depois de ler os cabeçalhos.
- Volta só remetente, assunto, data e um trecho do texto (1500 caracteres), com teto de mensagens; mensagem acima
  de 256 KB volta só com o cabeçalho.
- Erro e log levam só a etapa e o tipo da falha: nada de host, usuário, senha, endereço ou texto.

Na demo com `EMAIL_DESTINO_TESTE`, o "lojista" responde do endereço de teste, então ele entra na busca.

## Ligação

1. Use uma caixa da plataforma (no Gmail: ative o IMAP nas configurações e crie uma senha de app).
2. No `.env`: `EMAIL_IMAP_HOST=imap.gmail.com`, `EMAIL_IMAP_USUARIO=<e-mail da caixa>` e
   `EMAIL_IMAP_SENHA=<senha de app>`. Porta e segurança vazias usam `ssl` e 993. `EMAIL_IMAP_PASTA` vazia usa INBOX.
3. `MODO_TERMINAL=1 python -m ferramentas.integracoes testar email_leitura` faz o login e conta as mensagens da
   pasta, sem ler nenhuma.

Sem `EMAIL_IMAP_HOST`, a leitura fica desligada e a ferramenta some do que o modelo vê. `EMAIL_LEITURA_MODO=simulado`
monta a caixa com as mensagens por e-mail do mundo simulado (o CRM do mock) e diz isso em `fonte`.

## Hoje

Conector real pronto. Nos testes, um servidor IMAP local mínimo em socket de verdade (`backend/tests/apoio_imap.py`).
O sistema `email_leitura` de `mock.falhas` derruba a leitura na demo. Ler a caixa pessoal de cada funcionário
fica para os conectores do Google Workspace e do Microsoft 365.
