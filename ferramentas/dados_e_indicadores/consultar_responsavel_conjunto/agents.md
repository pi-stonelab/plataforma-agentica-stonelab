# consultar_responsavel_conjunto

Diz de que sistema é uma tabela de dados, para saber a quem perguntar ou pedir correção.

## Quando usar

Use quando o usuário perguntar quem é o dono de um dado ou a quem pedir correção de uma tabela. Pegue o nome exato da tabela com `buscar_conjuntos_dados`.

## Quando não usar

Esta ferramenta não diz o nome de nenhuma pessoa: o responsável é o sistema dono.

## Parâmetros

- `conjunto` (texto, obrigatório): nome exato da tabela. Exemplo: `faturas`.

## O que devolve

Em `dados`: `tabela`, `sistema`, `nome_do_sistema` e `orientacao`.

Erros possíveis: `nao_encontrado` (tabela que não existe).

## Para quem mantém

- Área: `dados_e_indicadores`.
- Acesso: leitura.
- Integração:
  - `datahub` (ver `integracoes/datahub/README.md`): dicionário do mock, via `ferramentas/dicionario.py`.
- Permissão: categoria `metadado` (todo cargo com área).
- Regra: o responsável é o sistema dono da tabela; o mock não tem um time nomeado por sistema (decisão sem fonte, `docs/decisoes.md`).
- Conteúdo de terceiros na saída: não.
- Situação: ativa.
