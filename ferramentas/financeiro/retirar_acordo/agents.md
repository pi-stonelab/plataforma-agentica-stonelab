# retirar_acordo

Prepara a retirada de um acordo que você pediu e que ainda espera aprovação. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando o funcionário quiser desistir de um acordo que ele mesmo registrou e que está pendente de aprovação (veja com `listar_acordos`), por exemplo porque ninguém pode aprová-lo ou porque o lojista mudou o pedido. O acordo é cancelado e as faturas ficam livres para um acordo novo. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use para acordo de outra pessoa (a ferramenta responde que não encontrou), nem para acordo já ativo, recusado ou expirado. Para recusar o acordo de outra pessoa, use `aprovar_acordo` com `recusar`.

## Parâmetros

- `id_acordo` (texto, obrigatório): código do acordo pendente que o funcionário pediu. Exemplo: `AC0002`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_acordo`, `id_cliente`, `faturas`, `valor_renegociado`, `alcada` (quem aprovaria) e `efeito`.

Erros possíveis: `parametro_invalido` (código fora do formato, ou acordo que já não espera aprovação na confirmação), `nao_encontrado` (acordo que não está pendente ou que não é seu), `permissao_negada` (lojista fora do escopo) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- `mock/escritas.retirar_acordo`: só o solicitante retira, só enquanto o acordo está em `pendente_aprovacao`; o acordo vira `cancelado`, `id_decisor` guarda quem retirou e as faturas voltam a ficar fora de acordo (a régua segue). Sem esta saída, o acordo pendente prendia as faturas até expirar (validade de 7 dias, pergunta H2).
- A prévia do `registrar_acordo` avisa quando não existe outra pessoa que possa aprovar, que é o caso mais comum de uso desta ferramenta.
