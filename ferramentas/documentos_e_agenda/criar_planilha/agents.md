# criar_planilha

Prepara uma planilha nova na conta do próprio funcionário (Google ou Microsoft) e deixa a prévia esperando a confirmação dele; nesta etapa nada é criado.

## Quando usar

Use quando o funcionário pedir uma planilha nova com colunas e, se quiser, algumas linhas já preenchidas (uma lista,
um acompanhamento). Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na
tela. Nunca diga que a planilha foi criada: quem confirma é o funcionário.

## Quando não usar

Não use para acrescentar uma linha a uma planilha que já existe (`adicionar_linha_planilha`), para gerar um arquivo
para baixar na conversa (`entregar_arquivo`) nem para exportar dado pessoal de lojista (CPF, cartão, conta,
telefone, e-mail): cite o código do lojista, como `M00001`. O que for sensível sai mascarado.

## Parâmetros

- `titulo` (texto, obrigatório, uma linha, até 100 caracteres): o nome da planilha.
- `colunas` (texto, obrigatório): os cabeçalhos separados por `|`. Exemplo: `Data | Chamado | Situação`.
- `linhas` (texto, opcional): uma linha por quebra de linha, as células separadas por `|`. Até 50 linhas, 20
  colunas e 200 caracteres por célula. Número (`7`, `12.5`) vira número; o resto, texto.
- `servico` (texto, opcional): `google` ou `microsoft`. Só use se a ferramenta pedir.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`servico`, `titulo`, `colunas`, `tamanho`, `linhas` (as 10 primeiras, já mascaradas) e `aviso`. Depois da
confirmação, a pessoa recebe o `id_arquivo` e o `link` da planilha.

Erros possíveis: `parametro_invalido` (título vazio, mais células que colunas, linhas demais),
`integracao_indisponivel` (conta não ligada, sem a permissão de escrever em planilhas, serviço fora do ar ou
prévias demais esperando confirmação).

## Para quem mantém

- Área: `documentos_e_agenda`. Acesso: escrita em duas fases, em `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria
  `documento_de_trabalho`.
- Fase 2: Google `spreadsheets.create` (valores como texto ou número, nunca fórmula); Microsoft envia um .xlsx
  gerado aqui (`formatos.escrever_xlsx`) para o OneDrive (`Files.ReadWrite`). O registro guarda o `id_arquivo` como
  referência externa.
- Integração: `google_workspace` ou `microsoft_365`, alternativas; conta OAuth de cada pessoa.
- Situação: ativa. Nos testes, servidores locais no formato das duas APIs.
