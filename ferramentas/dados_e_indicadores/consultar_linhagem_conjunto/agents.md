# consultar_linhagem_conjunto

Mostra de que tabelas um dado é calculado e quais tabelas dependem dele.

## Quando usar

Use quando o usuário perguntar de onde vem um número de relatório ("de onde sai a taxa de chargeback?") ou o que muda se uma tabela tiver erro. Pegue o nome exato da tabela com `buscar_conjuntos_dados`.

## Quando não usar

Esta ferramenta não lê o dado nem mostra colunas (use `consultar_esquema_conjunto`).

## Parâmetros

- `conjunto` (texto, obrigatório): nome exato da tabela. Exemplo: `vendas`.

## O que devolve

Em `dados`: `tabela`, `origem` (tabelas de onde ela é calculada; vazia se é uma tabela de origem) e `derivados` (tabelas calculadas a partir dela).

Erros possíveis: `nao_encontrado` (tabela que não existe).

## Para quem mantém

- Área: `dados_e_indicadores`.
- Acesso: leitura.
- Integração:
  - `datahub` (ver `integracoes/datahub/README.md`): a `origem` vem do dicionário do mock; os `derivados` são calculados invertendo a origem, em `ferramentas/dicionario.py`.
- Permissão: categoria `metadado` (todo cargo com área).
- Conteúdo de terceiros na saída: não.
- Situação: ativa.
