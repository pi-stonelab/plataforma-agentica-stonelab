# comentar_chamado_jira

Prepara um comentário num chamado interno do Jira e deixa a prévia esperando a confirmação do funcionário; nesta etapa nada é gravado.

## Quando usar

Use quando o funcionário pedir para acrescentar uma informação a um chamado interno que já existe (chave como
`KAN-123`). A prévia mostra o resumo do chamado para ele conferir que é o certo. Depois de usar, responda com
FINAL dizendo que a prévia está esperando a confirmação na tela. Nunca diga que o comentário foi gravado.

## Quando não usar

Não use para chamado de lojista (código como `CH000001`): esse é do CRM, nas ferramentas de atendimento. Não
coloque CPF, cartão, conta ou telefone de lojista no texto.

## Parâmetros

- `chave` (texto, obrigatório): a chave do chamado. Exemplo: `KAN-123`. Só projetos liberados.
- `texto` (texto, obrigatório, até 2000 caracteres): o comentário. Para quebrar linha, use `\n` dentro do JSON.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `chave_jira`, `resumo` (do
chamado, para conferir) e `texto` como será gravado (dado pessoal sai mascarado).

Erros possíveis: `parametro_invalido` (chave fora do formato ou de projeto não liberado, texto vazio ou longo
demais), `nao_encontrado` (o chamado não existe ou a conta não o vê) e `integracao_indisponivel`.

## Para quem mantém

- Área: `chamados_internos`. Acesso: escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
  Categoria `chamado_interno`.
- Fase 1 lê o chamado (para a prévia mostrar o resumo); fase 2 grava pelo `POST /rest/api/3/issue/{chave}/comment`
  (corpo em ADF). Projeto conferido de novo na hora de gravar.
- LGPD: o texto passa pela máscara de texto livre antes da prévia, e é esse texto que sai.
- Situação: ativa. Modo simulado: comentário em memória, com o aviso em `fonte`.
