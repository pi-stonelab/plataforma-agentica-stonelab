# aprovar_acordo

Prepara a aprovação ou a recusa de um acordo pendente. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando o coordenador financeiro pedir para aprovar ou recusar um acordo que espera a aprovação dele (veja com `listar_acordos`). Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use para acordo que você mesmo pediu: quem pede nunca aprova. Não use para criar acordo (use `registrar_acordo`).

## Parâmetros

- `id_acordo` (texto, obrigatório): código do acordo. Exemplo: `AC0001`.
- `decisao` (texto, obrigatório): `aprovar` ou `recusar`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_acordo`, `decisao`, `id_cliente`, `faturas`, `valor_original`, `valor_renegociado`, `entrada`, `numero_de_parcelas`, `perdao_encargos`, `desconto_principal`, `alcada` e `id_solicitante`.

Erros possíveis: `parametro_invalido` (código ou decisão inválidos), `nao_encontrado` (acordo que não está pendente), `permissao_negada` (quem pediu o acordo, ou acordo acima da sua alçada) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`. Onboarding 8: a aprovação continua do coordenador.
- `mock/escritas.decidir_acordo`: quem pediu nunca decide (§8.1, segregação), quem decide precisa da alçada; a dupla aprovação é dada pelo coordenador (§8.2). Aprovado, as faturas passam a "em_acordo"; recusado, voltam para fora de acordo e a régua segue.
- Quem pode: nível N2 do financeiro com `cobranca` (coordenador financeiro).
