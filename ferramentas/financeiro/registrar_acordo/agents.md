# registrar_acordo

Prepara um acordo com as faturas vencidas do lojista. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando a cobrança pedir para fechar um acordo, depois de mostrar os encargos (`calcular_multa_atraso`) e as parcelas (`calcular_parcelas`). Dentro da alçada de quem pede, o acordo fica ativo na confirmação; acima, vai para o coordenador. Diga ao funcionário o que a prévia mostra em `aprovacao` e em `atencao` (acordos já abertos do lojista, que somam para a alçada, e falta de outra pessoa para aprovar). O pedido que não coube na sua alçada pode ser retirado depois com `retirar_acordo`. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use para aprovar acordo pendente (use `aprovar_acordo`) nem para simular parcelas (use `calcular_parcelas`).

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00003`.
- `numero_parcelas` (inteiro, obrigatório): de 1 a 12.
- `entrada_percentual` (decimal, opcional): entrada em percentual do valor renegociado, como `20`. Sem ela, 20%.
- `perdoar_encargos` (texto, opcional): `sim` para perdoar os encargos de atraso.
- `desconto_principal_percentual` (decimal, opcional): desconto no principal, como `5`. Só o coordenador, até 10%.
- `faturas` (texto, opcional): códigos separados por vírgula, como `I000123, I000124`. Sem ele, todas as vencidas fora de acordo.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `faturas`, `valor_original`, `encargos`, `perdao_encargos`, `desconto_principal`, `valor_renegociado`, `entrada`, `numero_de_parcelas` (parcelas além da entrada), `valor_da_parcela`, `valor_da_ultima_parcela` (só quando a última absorve centavos, como em `calcular_parcelas`), `aprovacao` e `atencao` (quando existe).

Erros possíveis: `parametro_invalido` (parcelas fora de 1 a 12, acordo fora das regras, faturas inválidas), `nao_encontrado` (sem fatura vencida fora de acordo), `permissao_negada` (cargo que não negocia, lojista fora da carteira) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`. Cenário 3 e onboarding 1.
- A conta é `mock/escritas.montar_acordo` na prévia e de novo na gravação, com as mesmas faturas (o código delas vai no pedido). Alçadas do DOC-MOCK §7.9 em `regras.alcada_do_acordo` e `regras.ALCADAS_DE_ACORDO_DO_CARGO`; nunca aprova sozinho o que passa da alçada (E17, E20).
- Quem pode: analista de cobrança e coordenador financeiro.
