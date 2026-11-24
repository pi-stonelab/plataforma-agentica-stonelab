# consultar_taxa_contestacao_cliente

Mostra, mês a mês, a taxa de chargeback de um cliente (lojista) e os meses em que ela passou do limite do monitoramento de risco.

## Quando usar

Use quando o usuário perguntar se um lojista está perto ou acima do limite de chargeback, ou como a taxa dele evoluiu. O limite vale por lojista: mais de 1% das vendas no cartão do mês em chargeback, contado em quantidade. Sem meses, valem os últimos 6 até o mês atual. Diga quais meses estão em `meses_acima_do_limite`.

## Quando não usar

Para os chargebacks em si (prazo, documentos, valor retido), use `listar_contestacoes_cliente`. Para a taxa da Stone inteira, use `consultar_taxa_contestacao_mensal`, que não compara com o limite.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00002`.
- `mes_inicio` (texto, opcional): primeiro mês, no formato AAAA-MM. Exemplo: `2026-05`.
- `mes_fim` (texto, opcional): último mês, no formato AAAA-MM. Se faltar, vale o mês atual. Exemplo: `2026-10`.

O período tem no máximo 24 meses.

## O que devolve

Em `dados`: `id_cliente`, `mes_inicio`, `mes_fim`, `data_corte`, `limite_de_monitoramento_percentual` (número, como `1.0`), `meses` e `meses_acima_do_limite` (lista de meses AAAA-MM). Cada mês traz `mes`, `quantidade_vendas_cartao`, `quantidade_chargebacks`, `taxa_chargeback_percentual` (número em percentual com duas casas, como `1.25`; vazio se o lojista não teve venda no cartão no mês) e `acima_do_limite` (verdadeiro ou falso). Um mês com poucas vendas oscila muito: diga as quantidades junto da taxa. O mês atual vai só até a `data_corte`.

Erros possíveis: `parametro_invalido` (id ou mês fora do formato, mes_inicio depois de mes_fim ou mais de 24 meses), `permissao_negada` (cliente fora da sua carteira), `nao_encontrado` (só para quem vê todas as carteiras) e `integracao_indisponivel` (base analítica fora do ar).

## Para quem mantém

- Área: `financeiro` (DOC-MOCK §7.6: mais de 1% das vendas do mês em chargeback, em quantidade, liga o monitoramento de risco; §11.3: um lojista fica acima do limite de propósito).
- Acesso: leitura.
- Integração:
  - `bigquery` (ver `integracoes/bigquery/README.md`): tabela `analitica_contestacoes_mensais` do mock, recorte por lojista (`dados_sinteticos.contestacoes_do_lojista_por_mes`). É dado de disputa daquele lojista, por isso passa pelas portas do lojista (carteira) e exige a categoria `disputa`.
- Permissão: categoria `disputa` (mesmos cargos de `listar_contestacoes_cliente`) e escopo de carteira vêm do cargo (`mock/regras.py`).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos. A comparação com o limite usa as quantidades (`chargebacks * 100 > vendas`), sem o arredondamento da taxa.
