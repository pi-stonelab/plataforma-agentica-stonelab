# abrir_chamado_jira

Prepara um chamado interno no Jira e deixa a prévia esperando a confirmação do funcionário; nesta etapa nada é criado.

## Quando usar

Use quando o funcionário pedir para abrir um chamado para outro time da Stone ou registrar uma falha de sistema.
Escreva o resumo e a descrição só com o que o funcionário disse e o que veio das ferramentas. Depois de usar,
responda com FINAL dizendo que a prévia está esperando a confirmação na tela e repita o resumo. Nunca diga que o
chamado foi aberto: quem abre é o funcionário, ao confirmar.

## Quando não usar

Não use para registrar o atendimento de um lojista: para isso existe o chamado do CRM (`abrir_chamado`). Não
coloque CPF, cartão, conta ou telefone de lojista no texto; cite o código do lojista (como `M00001`).

## Parâmetros

- `resumo` (texto, obrigatório, até 200 caracteres, uma linha só): título do chamado. Exemplo: `Liquidação de
  14/10 da M00001 falhou por conta inválida`.
- `descricao` (texto, obrigatório, até 4000 caracteres): o que aconteceu e o que se pede. Para quebrar linha, use
  `\n` dentro do JSON.
- `projeto` (texto, opcional): a chave do projeto, como `KAN`. Sem ele, o primeiro projeto liberado.
- `tipo` (texto, opcional): o tipo de chamado, como `Tarefa`. Sem ele, o primeiro tipo liberado.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`projeto`, `tipo`, `resumo` e `descricao` como serão enviados (CPF, cartão e telefone saem mascarados). Depois
que o funcionário confirma, a tela mostra a `chave` criada.

Erros possíveis: `parametro_invalido` (texto vazio ou longo demais, resumo com mais de uma linha, projeto ou tipo
fora da lista; a mensagem lista os liberados) e `integracao_indisponivel` (Jira desligado, fora do ar ou prévias
demais esperando confirmação).

## Para quem mantém

- Área: `chamados_internos`. Acesso: escrita em duas fases (`ferramentas/confirmacoes.py`), listada em
  `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria `chamado_interno` (todo cargo com área).
- Fase 2: `efetivar` abre o chamado pela conta de serviço (`POST /rest/api/3/issue`, descrição em ADF). Recusa do
  Jira (4xx) = nada criado; sem resposta depois de enviar = "pode ter saído" (conferir no Jira antes de repetir).
- Projeto e tipo só da lista do `.env`, conferidos de novo na hora de abrir.
- LGPD: resumo e descrição passam pela máscara de texto livre antes da prévia, e é esse texto que sai.
- Situação: ativa. Modo simulado: chamado em memória, com o aviso em `fonte`.
