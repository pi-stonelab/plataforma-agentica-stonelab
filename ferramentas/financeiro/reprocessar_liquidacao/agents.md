# reprocessar_liquidacao

Prepara uma nova tentativa de uma liquidação que falhou. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando a analista de recebíveis pedir para reprocessar uma liquidação que falhou, depois de conferir com `consultar_liquidacoes_cliente` (o `id_liquidacao` vem de lá). Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use em liquidação paga nem quando a conta de recebimento não está ativa: a troca de conta é do N2, antes do reprocessamento.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00001`.
- `id_liquidacao` (inteiro, obrigatório): o `id_liquidacao` que `consultar_liquidacoes_cliente` devolveu.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_liquidacao`, `data`, `valor`, `motivo_falha` e `nova_tentativa_em`.

Erros possíveis: `parametro_invalido` (liquidação que não falhou; na confirmação, conta de recebimento não ativa), `nao_encontrado` (liquidação de outro lojista ou inexistente), `permissao_negada` e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`. Onboarding 6 da KAN-69: a analista confirma cada uma.
- Quem pode: financeiro com a categoria `liquidacao` (analista de recebíveis e coordenador financeiro).
- `mock/escritas.reprocessar_liquidacao`: a original vira "reprocessada", a nova nasce "agendada" ligada a ela (§7.3); o recebível continua retido até a nova ser paga.
