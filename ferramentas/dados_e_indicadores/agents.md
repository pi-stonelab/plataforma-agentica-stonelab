# dados_e_indicadores

Indicadores da Stone (receitas, chamados por fila, taxa de chargeback), cálculo de retorno de um agente e o dicionário de dados.

## Como escolher

Escolha pela pergunta, entre as ferramentas da lista abaixo (só aparecem as liberadas para você):

- Números da empresa inteira (relatório da semana, chamados por fila, taxa de chargeback) vêm da base analítica, que vai só até ontem: diga sempre a `data_corte`.
- Dado de um lojista não fica aqui: use as áreas de atendimento e de financeiro.
- Onde fica um dado, que colunas tem, de que sistema é e de onde vem: use as ferramentas do dicionário, que não leem dado nenhum.
- Se um agente se paga: `calcular_roi`, com os números que o usuário der.
- Nomes que você não vê na lista não estão liberados para você.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integrações da área: `bigquery` (base analítica do mock, cortada em ontem) e `datahub` (dicionário de dados do mock).
- Ferramentas (8):
  - `resumir_receita_periodo` (leitura)
  - `resumir_volume_chamados` (leitura; era `resumir_volume_tickets`)
  - `consultar_taxa_contestacao_mensal` (leitura)
  - `buscar_conjuntos_dados` (leitura)
  - `consultar_esquema_conjunto` (leitura)
  - `consultar_responsavel_conjunto` (leitura)
  - `consultar_linhagem_conjunto` (leitura)
  - `calcular_roi` (cálculo)
- Regras comuns em `ferramentas/indicadores.py` (período até ontem, meses AAAA-MM) e `ferramentas/dicionario.py` (leitura do dicionário).
