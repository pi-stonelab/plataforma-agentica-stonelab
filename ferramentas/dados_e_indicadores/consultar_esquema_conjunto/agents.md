# consultar_esquema_conjunto

Mostra as colunas de uma tabela de dados, com o tipo, a descrição e quais guardam dado restrito.

## Quando usar

Use quando o usuário perguntar que campos uma tabela tem ou se ela guarda dado pessoal. Pegue o nome exato da tabela com `buscar_conjuntos_dados`.

## Quando não usar

Esta ferramenta não lê o dado. Para saber de onde a tabela vem, use `consultar_linhagem_conjunto`.

## Parâmetros

- `conjunto` (texto, obrigatório): nome exato da tabela. Exemplo: `contatos_lojista`.

## O que devolve

Em `dados`: `tabela`, `descricao_da_tabela` e `colunas` (cada uma com `coluna`, `tipo_da_coluna`, `descricao_da_coluna` e `restrita`). Coluna restrita sai mascarada em toda ferramenta que a lê.

Erros possíveis: `nao_encontrado` (tabela que não existe).

## Para quem mantém

- Área: `dados_e_indicadores`.
- Acesso: leitura.
- Integração:
  - `datahub` (ver `integracoes/datahub/README.md`): dicionário do mock, via `ferramentas/dicionario.py`.
- Permissão: categoria `metadado` (todo cargo com área).
- Conteúdo de terceiros na saída: não.
- Situação: ativa.
