# consultar_taxa_contestacao_mensal

Mostra, mês a mês, a taxa de chargeback da Stone somando todos os lojistas, e o limite que liga o monitoramento.

## Quando usar

Use quando o coordenador perguntar pela taxa de chargeback da empresa, pela evolução nos últimos meses ou se a taxa passou do limite do monitoramento. Sem meses, valem os últimos 6 até o mês atual.

## Quando não usar

Para os chargebacks de um lojista, use `listar_contestacoes_cliente`. Esta ferramenta não traz dado de nenhum lojista: só totais.

## Parâmetros

- `mes_inicio` (texto, opcional): primeiro mês, no formato AAAA-MM. Exemplo: `2026-05`.
- `mes_fim` (texto, opcional): último mês, no formato AAAA-MM. Se faltar, vale o mês atual. Exemplo: `2026-10`.

O período tem no máximo 24 meses.

## O que devolve

Em `dados`: `mes_inicio`, `mes_fim`, `data_corte`, `meses` (cada um com `mes`, `quantidade_vendas_cartao`, `quantidade_chargebacks` e `taxa_chargeback`, como `1,25%`) e `limite_de_monitoramento` (como `1,00%`). Diga quais meses passaram do limite. O mês atual vai só até a `data_corte`.

Erros possíveis: `parametro_invalido` (mês fora do formato, mes_inicio depois de mes_fim ou mais de 24 meses) e `integracao_indisponivel` (base analítica fora do ar).

## Para quem mantém

- Área: `dados_e_indicadores` (DOC-MOCK §7.6: taxa de chargeback e o limite que liga o monitoramento).
- Acesso: leitura.
- Integração:
  - `bigquery` (ver `integracoes/bigquery/README.md`): tabela `analitica_contestacoes_mensais` do mock, só os totais da Stone (`dados_sinteticos.contestacoes_por_mes`). O recorte por lojista é dado de disputa e não passa por aqui (decisão do bloco A).
- Permissão: categoria `indicador_agregado` e ficha N2 do financeiro (coordenador financeiro).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
