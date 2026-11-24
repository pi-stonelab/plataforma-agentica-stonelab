# calcular_parcelas

Divide um valor em parcelas, com entrada, e diz quem aprova o acordo: analista, coordenador, dupla aprovação ou ninguém.

## Quando usar

Use quando o usuário pedir uma proposta de acordo de parcelamento para um valor em atraso, por exemplo depois de calcular os encargos com `calcular_multa_atraso`. Passe o valor total a pagar (principal mais multa e juros) e o número de parcelas pedido. Se houver desconto ou perdão de encargos, passe também o valor principal (o das faturas, sem multa e juros).

## Quando não usar

Esta ferramenta só calcula: não busca a fatura, não fecha nem grava acordo. Para achar as faturas, use `listar_faturas_em_atraso`. Para calcular multa e juros, use `calcular_multa_atraso`. O resultado é uma proposta: o usuário precisa confirmar, e quem aprova é o que o campo `alcada` indicar.

## Parâmetros

- `valor_total` (decimal, obrigatório): valor a parcelar em reais, maior que 0 e até 1.000.000. Exemplo: `330.67`.
- `numero_parcelas` (inteiro, obrigatório): quantas parcelas, de 1 a 60. Acima de 12 o acordo é proibido. Exemplo: `4`.
- `entrada_percentual` (decimal, opcional): entrada paga antes das parcelas, em % do valor negociado, de 0 a 99. Se faltar, vale 20. Exemplo: `20`.
- `desconto_principal_percentual` (decimal, opcional): desconto no valor principal, em %, de 0 a 99. Se faltar, vale 0. Só use se o usuário pedir desconto. Exemplo: `5`.
- `valor_principal` (decimal, opcional): valor das faturas sem multa e juros, maior que 0 e até o `valor_total`. Se faltar, vale o `valor_total`. Exemplo: `320.00`.
- `perdao_encargos` (decimal, opcional): quanto da multa e dos juros perdoar, em reais, até `valor_total` menos `valor_principal`. Se faltar, vale 0. Só use se o usuário pedir. Exemplo: `10.67`.

## O que devolve

Em `dados`: `valor_informado`, `numero_parcelas`, `entrada_percentual`, `desconto_principal_percentual`, `alcada`, `motivo`, `valor_negociado` (valor depois do desconto e do perdão), `entrada` e `parcelas` (lista com `numero` e `valor`). Os valores em reais são texto como `R$ 66,14`: repita sem converter. As parcelas são iguais e a última absorve a diferença de centavos; entrada mais parcelas dão o `valor_negociado`. A entrada arredonda para cima e o desconto para baixo, para nenhum dos dois sair do percentual pedido.

`alcada` segue as alçadas do DOC-MOCK §7.9. `analista`: até 6 parcelas, entrada de pelo menos 20%, sem desconto no principal e perdão de encargos só em dívida de até R$ 2.000,00. `coordenador`: mais de 6 e até 12 parcelas, entrada abaixo de 20%, desconto no principal de até 10% ou perdão de encargos em dívida maior. `dupla_aprovacao`: acima de R$ 10.000,00 renegociados, duas pessoas aprovam e quem pede nunca aprova. `proibido`: mais de 12 parcelas ou desconto acima de 10% do principal; nesse caso `parcelas` vem vazia e nada é calculado: explique o motivo ao usuário e não ofereça o acordo. Diga sempre quem aprova e que a proposta depende de confirmação.

Erros possíveis: `parametro_invalido` (valor, parcelas ou percentuais fora das faixas, principal ou perdão fora do valor total, ou valor pequeno demais para as parcelas).

## Para quem mantém

- Área: `financeiro`.
- Acesso: cálculo.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Regras: a alçada é `regras.alcada_do_acordo` (DOC-MOCK §7.9), a mesma que o mock usa nos acordos plantados, lida pela fachada; esta ficha só explica a decisão em `motivo`. A entrada separada das parcelas e o padrão de 20% são escolha desta ferramenta (o DOC-MOCK não diz se a entrada conta dentro das parcelas); entrada abaixo de 20% exige o coordenador porque a fonte não diz quem aprova.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
