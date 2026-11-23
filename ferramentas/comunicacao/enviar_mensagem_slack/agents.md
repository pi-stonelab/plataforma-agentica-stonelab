# enviar_mensagem_slack

Prepara uma mensagem num canal interno do Slack e deixa a prévia esperando a confirmação do funcionário; nesta etapa nada é enviado.

## Quando usar

Use quando o funcionário pedir para avisar um time da Stone num canal interno do Slack (por exemplo, o plantão
sobre um lojista com liquidação falhando). Escreva o texto só com o que o funcionário disse e o que veio das
ferramentas. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela. Nunca
diga que a mensagem foi enviada: quem envia é o funcionário, ao confirmar.

## Quando não usar

Não use para falar com o lojista nem com pessoas fora da Stone: o Slack é só para colegas. Não coloque CPF,
cartão, conta ou telefone de lojista no texto; cite o código do lojista (como `M00001`). Se o funcionário pedir um
canal fora da lista, a ferramenta recusa e diz quais existem: repasse isso, não tente outro canal por conta própria.

## Parâmetros

- `canal` (texto, obrigatório): o apelido do canal, como `plantao`. Só os canais liberados nesta plataforma.
- `texto` (texto, obrigatório, até 2900 caracteres): a mensagem. Para quebrar linha, use `\n` dentro do JSON.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`canal` e `texto` como será enviado (dado pessoal sai mascarado, e o texto já leva a assinatura com o primeiro
nome do funcionário).

Erros possíveis: `parametro_invalido` (canal fora da lista, texto vazio ou longo demais) e
`integracao_indisponivel` (Slack desligado, fora do ar ou prévias demais esperando confirmação).

## Para quem mantém

- Área: `comunicacao`. Acesso: escrita em duas fases (`ferramentas/confirmacoes.py`), listada em
  `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria `comunicacao_interna` (todo cargo com área).
- Fase 2: `efetivar` publica pelo bot da plataforma (`chat.postMessage`). Canal conferido de novo na hora de
  publicar; o `ts` do Slack não volta (não serve a quem confirmou).
- LGPD: o texto passa pela máscara de texto livre antes da prévia, e é esse texto que sai; o destino é sempre um
  canal interno da lista.
- Integração: `slack` (`integracoes/slack/README.md`). Situação: ativa; modo simulado em memória, com o aviso em
  `fonte`.
