# enviar_aviso_telegram

Prepara um aviso num chat interno do Telegram e deixa a prévia esperando a confirmação do funcionário; nesta etapa nada é enviado.

## Quando usar

Use quando o funcionário pedir para avisar um grupo interno da Stone pelo Telegram (por exemplo, o plantão fora
do horário). Escreva o texto só com o que o funcionário disse e o que veio das ferramentas. Depois de usar,
responda com FINAL dizendo que a prévia está esperando a confirmação na tela. Nunca diga que o aviso foi enviado.

## Quando não usar

Não use para falar com o lojista nem com pessoas fora da Stone. Não coloque CPF, cartão, conta ou telefone de
lojista no texto. Se o chat pedido não estiver na lista, a ferramenta recusa e diz quais existem: repasse isso.

## Parâmetros

- `chat` (texto, obrigatório): o apelido do chat, como `plantao`. Só os chats liberados nesta plataforma.
- `texto` (texto, obrigatório, até 4000 caracteres): o aviso. Para quebrar linha, use `\n` dentro do JSON.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`chat` e `texto` como será enviado (dado pessoal sai mascarado, com a assinatura do funcionário).

Erros possíveis: `parametro_invalido` (chat fora da lista, texto vazio ou longo demais) e
`integracao_indisponivel` (Telegram desligado, fora do ar ou prévias demais esperando confirmação).

## Para quem mantém

- Área: `comunicacao`. Acesso: escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria
  `comunicacao_interna` (todo cargo com área).
- Fase 2: `efetivar` envia pelo bot da plataforma (`sendMessage`, sem formatação e sem prévia de link). Chat
  conferido de novo na hora de enviar. O token vai no caminho da URL e nunca aparece em log, erro ou estado.
- LGPD: o texto passa pela máscara de texto livre antes da prévia, e é esse texto que sai.
- Integração: `telegram` (`integracoes/telegram/README.md`). Situação: ativa; modo simulado em memória.
