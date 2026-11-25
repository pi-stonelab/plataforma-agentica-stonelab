# adicionar_linha_planilha

Prepara uma linha nova no fim de uma planilha do próprio funcionário e deixa a prévia esperando a confirmação dele; nesta etapa nada é gravado.

## Quando usar

Use quando o funcionário pedir para registrar algo numa planilha que ele já tem (um acompanhamento, uma lista de
pendências). Pegue o `id_arquivo` com `buscar_arquivos`. Depois de usar, responda com FINAL dizendo que a prévia
está esperando a confirmação na tela. Nunca diga que a linha foi gravada: quem confirma é o funcionário.

## Quando não usar

Não use para criar uma planilha (`criar_planilha`), para mudar ou apagar linhas que já existem nem para guardar
dado pessoal de lojista (CPF, cartão, conta, telefone, e-mail): cite o código do lojista, como `M00001`.

## Parâmetros

- `id_arquivo` (texto, obrigatório): o id que `buscar_arquivos` devolveu, ou o link do arquivo no Google que o funcionário colou (o id sai da URL).
- `valores` (texto, obrigatório): as células da linha separadas por `|`, até 20 células de 200 caracteres.
  Exemplo: `19/10 | 100 | 90 | 2`. O que for escrito fica como texto (uma célula `=SOMA(A1)` não vira fórmula).
- `aba` (texto, opcional): o nome da aba. Padrão: a primeira.
- `servico` (texto, opcional): `google` ou `microsoft`. Só use se a ferramenta pedir.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`servico`, `planilha` (o título), `aba`, `valores` (cada célula já mascarada) e `aviso`.

Erros possíveis: `parametro_invalido` (id fora do formato, linha vazia ou grande demais), `nao_encontrado`
(planilha ou aba que não existe; a mensagem lista as abas), `integracao_indisponivel` (conta não ligada, sem a
permissão de escrever em planilhas, serviço fora do ar ou prévias demais esperando confirmação).

## Para quem mantém

- Área: `documentos_e_agenda`. Acesso: escrita em duas fases, em `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria
  `documento_de_trabalho`.
- Fase 1 lê o título e as abas (escopo de leitura) para a prévia; a fase 2 grava com o escopo de escrita
  (`spreadsheets` no Google, `Files.ReadWrite` na Microsoft). Google: `valueInputOption=RAW`; Microsoft: célula que
  começa com `= + - @` recebe um apóstrofo, para nunca virar fórmula.
- Integração: `google_workspace` ou `microsoft_365`, alternativas; conta OAuth de cada pessoa.
- Situação: ativa. Nos testes, servidores locais no formato das duas APIs.
