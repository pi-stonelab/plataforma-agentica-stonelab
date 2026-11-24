# BigQuery

Base analítica da Stone simulada: cópia agregada dos sistemas, atualizada uma vez por dia, que vai só até ontem (DOC-MOCK §4). Serve para indicadores e relatórios. A única exceção é o recorte de chargeback por lojista (`financeiro/consultar_taxa_contestacao_cliente`), que é dado de disputa e passa pelas portas do lojista.

## Ferramentas que usam

- `dados_e_indicadores/consultar_taxa_contestacao_mensal` (leitura)
- `financeiro/consultar_taxa_contestacao_cliente` (leitura)
- `dados_e_indicadores/resumir_receita_periodo` (leitura)
- `dados_e_indicadores/resumir_volume_chamados` (leitura)

## Conector

`integracoes/sistemas_internos.py` (`ConectorInterno`), modo sempre `simulado`. A saúde vem do sistema `analitica` de `mock.falhas` (fora do ar e "dado desatualizado", que atrasa o corte).

## Ligação

Tabelas `analitica_*` do mock (`analitica_vendas_diarias`, `analitica_chamados_diarios`, `analitica_contestacoes_mensais`, `analitica_resultado_diario`), cortadas em `HOJE_DO_MOCK - 1 dia` e lidas por `dados_sinteticos.py`.

## Hoje

Dados simulados. Trocar pelo BigQuery real é trocar o corpo das funções de leitura da base analítica em `mock/consultas.py`, mantendo a data de corte em cada resposta.
