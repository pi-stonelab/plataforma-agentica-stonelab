# calcular_parcelas

Divide um valor em parcelas, com entrada, e diz quem pode aprovar o acordo: analista, coordenador ou ninguém.

## Quando usar

Use quando o usuário pedir uma proposta de acordo de parcelamento para um valor em atraso, por exemplo depois de calcular os encargos com `calcular_multa_atraso`. Passe o valor total a pagar e o número de parcelas pedido.

## Quando não usar

Esta ferramenta só calcula: não busca a fatura, não fecha nem grava acordo. Para achar as faturas, use `listar_faturas_em_atraso`. Para calcular multa e juros, use `calcular_multa_atraso`. O resultado é uma proposta: o usuário precisa confirmar, e quem aprova é o que o campo `quem_aprova` indicar.

## Parâmetros

- `valor_total` (decimal, obrigatório): valor a parcelar em reais, maior que 0 e até 1.000.000. Exemplo: `330.67`.
- `numero_parcelas` (inteiro, obrigatório): quantas parcelas, de 1 a 60. Acima de 12 o acordo é proibido. Exemplo: `4`.
- `entrada_percentual` (decimal, opcional): entrada paga antes das parcelas, em % do valor negociado, de 0 a 99. Se faltar, vale 20. Exemplo: `20`.
- `desconto_principal_percentual` (decimal, opcional): desconto no valor principal, em %, de 0 a 99. Se faltar, vale 0. Só use se o usuário pedir desconto. Exemplo: `5`.

## O que devolve

Em `dados`: `valor_informado`, `numero_parcelas`, `entrada_percentual`, `desconto_principal_percentual`, `quem_aprova`, `motivo`, `valor_negociado` (valor depois do desconto), `entrada` e `parcelas` (lista com `numero` e `valor`). Os valores em reais são texto como `R$ 66,13`: repita sem converter. As parcelas são iguais e a última absorve a diferença de centavos; entrada mais parcelas dão o `valor_negociado`.

`quem_aprova` segue as alçadas do DOC-MOCK §7.9. `analista`: até 6 parcelas, entrada de pelo menos 20% e sem desconto. `coordenador`: mais de 6 e até 12 parcelas, entrada abaixo de 20% ou desconto no principal de até 10%. `proibido`: mais de 12 parcelas ou desconto acima de 10%; nesse caso `parcelas` vem vazia e nada é calculado: explique o motivo ao usuário e não ofereça o acordo. Diga sempre quem aprova e que a proposta depende de confirmação.

Erros possíveis: `parametro_invalido` (valor, parcelas ou percentuais fora das faixas, ou valor pequeno demais para as parcelas).

## Para quem mantém

- Área: `financeiro`.
- Acesso: cálculo.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Regras: as alçadas ficam como constantes no topo de func.py (fonte DOC-MOCK §7.9); a ideia é migrá-las para `mock/regras.py`. A entrada separada das parcelas e o padrão de 20% são escolha desta ferramenta (o DOC-MOCK não diz se a entrada conta dentro das parcelas); entrada abaixo de 20% foi tratada como "exige coordenador" porque a fonte não diz quem aprova.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
