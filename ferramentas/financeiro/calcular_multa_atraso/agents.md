# calcular_multa_atraso

Calcula a multa, os juros e o valor total de uma fatura paga com atraso.

## Quando usar

Use quando o usuário informar o valor de uma fatura e quantos dias ela está vencida e quiser saber quanto ela custa hoje.

## Quando não usar

Esta ferramenta só calcula: ela não busca a fatura nem o cliente. Para ver as transações de um cliente, use `consultar_transacoes_cliente`.

## Parâmetros

- `valor_fatura` (decimal, obrigatório): valor original da fatura em reais, maior que 0 e até 1.000.000. Exemplo: `1000.00`.
- `dias_atraso` (inteiro, obrigatório): dias corridos de atraso, de 0 a 3650. Exemplo: `30`.

## O que devolve

Em `dados`: `valor_fatura`, `dias_atraso`, `multa`, `juros`, `valor_total` e `regra`, com valores em reais e duas casas. A multa é de 2% do valor quando há pelo menos 1 dia de atraso. Os juros são de 1% ao mês, proporcionais aos dias. Exemplo: 1000,00 com 30 dias dá multa de 20,00, juros de 10,00 e total de 1030,00.

Erros possíveis: `parametro_invalido` (valor ou dias fora das faixas, ou fora do tipo).

## Para quem mantém

- Área: `financeiro`.
- Acesso: cálculo.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
