# resumir_volume_chamados

Conta os chamados de cada fila num período: abertos, resolvidos e quantos estouraram o prazo de atendimento.

## Quando usar

Use quando o supervisor perguntar quantos chamados a equipe recebeu ou resolveu, ou quantos estouraram o prazo, por exemplo "quantos críticos estouraram o prazo esta semana?". Sem datas, vale a semana atual (de segunda até ontem).

## Quando não usar

Para um chamado específico, use `consultar_chamado`. Para os chamados de um lojista, use `listar_chamados_cliente`. O que aconteceu hoje ainda não está na base analítica: avise e, se precisar, consulte o chamado no CRM.

## Parâmetros

- `data_inicio` (data, opcional): primeiro dia, no formato AAAA-MM-DD. Exemplo: `2026-10-12`.
- `data_fim` (data, opcional): último dia, no formato AAAA-MM-DD. Se faltar, vale ontem. Exemplo: `2026-10-14`.
- `prioridade` (texto, opcional): só uma prioridade: `baixa`, `média`, `alta` ou `crítica`. Exemplo: `crítica`.

## O que devolve

Em `dados`: `data_inicio`, `data_fim`, `data_corte` (último dia que a base tem), `prioridade`, `filas` (cada uma com `fila`, `quantidade_abertos`, `quantidade_resolvidos` e `quantidade_estourados`), `total` e `aviso`. Diga sempre a `data_corte`: um chamado que estourou hoje só aparece amanhã.

Erros possíveis: `parametro_invalido` (prioridade desconhecida, data_inicio depois de data_fim ou período acima de 92 dias) e `integracao_indisponivel` (base analítica fora do ar).

## Para quem mantém

- Área: `dados_e_indicadores` (cenário 11 e onboarding 4 do DOC-MOCK). Era a planejada `resumir_volume_tickets`, renomeada para o vocabulário do mock.
- Acesso: leitura.
- Integração:
  - `bigquery` (ver `integracoes/bigquery/README.md`): tabela `analitica_chamados_diarios` do mock, cortada em ontem, lida por `dados_sinteticos.chamados_por_fila`.
- Permissão: categoria `indicador_agregado` e ficha N2 do atendimento (supervisor e especialista N2).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
