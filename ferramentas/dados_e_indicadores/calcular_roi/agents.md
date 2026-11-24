# calcular_roi

Calcula se um agente se paga: a economia em horas contra o custo, com o retorno percentual e em quantos meses volta.

## Quando usar

Use quando o usuário quiser saber se vale a pena um agente: quantas horas ele economiza por mês, quanto custa a hora de quem fazia o trabalho e quanto o agente custa. Os números vêm do usuário.

## Quando não usar

Não use para resultado financeiro da Stone (use `resumir_receita_periodo`). Não invente horas nem custos: se faltar algum, pergunte.

## Parâmetros

- `horas_economizadas_por_mes` (decimal, obrigatório): horas de trabalho que o agente poupa por mês, de 0 a 10.000. Exemplo: `40`.
- `custo_hora` (decimal, obrigatório): custo de uma hora de quem fazia o trabalho, em reais. Exemplo: `50.00`.
- `custo_mensal_agente` (decimal, obrigatório): quanto o agente custa por mês (modelo, infraestrutura), em reais. Exemplo: `300.00`.
- `custo_implantacao` (decimal, opcional): custo de criar o agente, em reais. Se faltar, vale 0. Exemplo: `2000.00`.
- `meses` (inteiro, opcional): horizonte da conta, de 1 a 60. Se faltar, vale 12. Exemplo: `12`.

## O que devolve

Em `dados`: `meses`, `economia_mensal`, `custo_mensal`, `ganho_liquido_mensal`, `ganho_total`, `custo_total`, `roi_percentual` (número com duas casas, como `328.57`: ganho total menos custo total, dividido pelo custo total; vazio se o custo for zero), `payback_meses` (meses para pagar a implantação; vazio se nunca paga) e `se_paga` (paga dentro do horizonte). Os valores em reais são texto como `R$ 2.000,00`: repita sem converter. Diga que é uma estimativa com os números informados.

Erros possíveis: `parametro_invalido` (horas, valores ou meses fora das faixas).

## Para quem mantém

- Área: `dados_e_indicadores` (proposta da Stone: "Gerir: controlar custos, retorno de investimento e manutenção dos agentes"; KAN-16).
- Acesso: cálculo.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: todo cargo com área.
- Conteúdo de terceiros na saída: não.
- Situação: ativa. A fórmula é a do ROI simples, sem desconto do dinheiro no tempo.
