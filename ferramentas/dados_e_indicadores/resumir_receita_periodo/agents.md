# resumir_receita_periodo

Resume receitas, perdas e resultado da Stone num período, com as vendas por modalidade, para o relatório semanal.

## Quando usar

Use quando o usuário pedir o relatório semanal (ou de outro período) de receitas e despesas da Stone, o resultado do período ou as vendas somadas por modalidade. Sem datas, vale a última semana até ontem.

## Quando não usar

Para as vendas de um lojista, use `consultar_transacoes_cliente`. Para as vendas de hoje, também: a base analítica só vai até ontem. Para a taxa de chargeback do mês, use `consultar_taxa_contestacao_mensal`.

## Parâmetros

- `data_inicio` (data, opcional): primeiro dia, no formato AAAA-MM-DD. Exemplo: `2026-10-08`.
- `data_fim` (data, opcional): último dia, no formato AAAA-MM-DD. Se faltar, vale ontem. Exemplo: `2026-10-14`.

O período tem no máximo 92 dias.

## O que devolve

Em `dados`: `data_inicio`, `data_fim`, `data_corte` (último dia que a base tem), `receitas` (`mdr`, `aluguel_e_tarifas`, `total`), `perdas` (`inadimplencia`, `concessoes_em_acordos`, `chargebacks_perdidos`, `total`), `resultado` (receitas menos perdas), `maior_venda` (`dia` e `valor`, para explicar um pico), `vendas_por_modalidade` (cada uma com quantidades, `valor_bruto`, `valor_liquido` e `receita_mdr`), `vendas_total` e `aviso`. Os valores em reais são texto como `R$ 1.364,96`: repita sem converter. Diga sempre a `data_corte` e, se a `maior_venda` for muito maior que as outras, diga que ela explica o pico.

Erros possíveis: `parametro_invalido` (data_inicio depois de data_fim ou período acima de 92 dias) e `integracao_indisponivel` (base analítica fora do ar).

## Para quem mantém

- Área: `dados_e_indicadores` (KAN-14, caso de uso 4; despesas como "perdas" pela decisão A9 em `docs/decisoes.md`, a validar com a Milene).
- Acesso: leitura.
- Integração:
  - `bigquery` (ver `integracoes/bigquery/README.md`): tabelas `analitica_resultado_diario` e `analitica_vendas_diarias` do mock, cortadas em ontem, lidas por `dados_sinteticos.py` (`resumo_de_resultado` e `resumo_de_vendas`).
- Permissão: categoria `indicador_agregado` (todo cargo com área) e ficha só para o financeiro.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
