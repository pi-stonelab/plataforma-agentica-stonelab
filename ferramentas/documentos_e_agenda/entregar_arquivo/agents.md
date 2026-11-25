# entregar_arquivo

Gera um arquivo (csv, xlsx ou txt) com o que o funcionário pediu e devolve o id dele para baixar na conversa.

## Quando usar

Use quando o funcionário pedir um arquivo pronto para baixar: uma lista, um relatório, um resumo em planilha. Depois
de usar, responda com FINAL dizendo que o arquivo está pronto para baixar na conversa e cite o nome (`arquivo`).
Não mostre o `arquivo_id` como se fosse um endereço: a tela cria o botão de baixar.

## Quando não usar

Não use para criar uma planilha na conta Google ou Microsoft dele (`criar_planilha`). Não coloque dado pessoal de
lojista (CPF, cartão, conta, telefone, e-mail): cite o código, como `M00001`. O que for sensível sai mascarado.

## Parâmetros

- `nome` (texto, obrigatório, uma linha, até 80 caracteres): o nome do arquivo, sem a extensão. Exemplo: `chamados da semana`.
- `formato` (texto, obrigatório): `csv`, `xlsx` ou `txt`.
- `conteudo` (texto, obrigatório, até 20000 caracteres): em csv e xlsx, uma linha por quebra de linha e as células
  separadas por `|` (a primeira linha costuma ser o cabeçalho); até 500 linhas, 20 colunas e 200 caracteres por
  célula. Em txt, o texto. Número (`7`, `12.5`) vira número no xlsx; o resto, texto. Nada vira fórmula.

## O que devolve

Em `dados`: `arquivo_id` (a tela usa para baixar), `arquivo` (o nome já com a extensão), `formato`, `tamanho` (bytes) e
`fonte`. O arquivo fica disponível por 7 dias e só para quem pediu.

Erros possíveis: `parametro_invalido` (formato desconhecido, conteúdo vazio, linhas ou células demais) e
`integracao_indisponivel` (anexos desligados, pasta fora do ar ou arquivos demais guardados para esta pessoa).

## Para quem mantém

- Área: `documentos_e_agenda`. Acesso: escrita, em `governanca.ESCRITA_SEM_CONFIRMACAO`: grava só na pasta de saída da
  própria plataforma, nada sai para outro sistema, e a pessoa decide se baixa. Categoria `documento_de_trabalho`.
- Integração: `anexos` (ver `integracoes/anexos/README.md`). O caminho do servidor nunca sai: só o `arquivo_id`.
  [A FAZER (Marcelo e Larissa): rota de download (`abrir_saida`) e o botão de baixar no chat]
- A planilha gerada é um .xlsx escrito por `formatos.escrever_xlsx` (sem fórmula nem macro); o csv usa `;` e UTF-8 com
  BOM (abre certo no Excel em português) e as células com cara de fórmula ganham um apóstrofo.
- Conteúdo de terceiros na saída: não.
- Situação: ativa.
