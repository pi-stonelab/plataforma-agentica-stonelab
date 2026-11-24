# executar_antecipacao

Prepara a antecipação que o lojista pediu num chamado (só N2). Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando um funcionário de nível N2 pedir para executar uma antecipação já registrada num chamado de Antecipação (o pedido do lojista precisa estar registrado). Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela e repita o valor líquido e a data do crédito.

## Quando não usar

Não use sem o chamado do pedido (registre com `registrar_pedido_antecipacao`) nem para simular (use `simular_antecipacao`).

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00004`.
- `id_chamado` (texto, obrigatório): o chamado de Antecipação com o pedido do lojista. Exemplo: `CH000071`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_chamado`, `quantidade_de_parcelas`, `valor_antecipado`, `taxa_mensal_percentual`, `desconto`, `valor_liquido` e `data_credito`.

Erros possíveis: `parametro_invalido` (chamado que não é de Antecipação ou está fechado, antecipação recusada com o motivo, nada para antecipar), `nao_encontrado`, `permissao_negada` (abaixo de N2 ou lojista fora da carteira) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- "A execução fica com o N2, com o pedido do lojista registrado" (DOC-MOCK §7.4). Quem pode: nível N2 com a categoria `agenda_recebiveis` (especialista N2, supervisor de atendimento, coordenador financeiro). Sem fonte para a lista exata: decisão D-B1 em `docs/decisoes.md`.
- `mock/escritas.executar_antecipacao` confere de novo as 4 recusas e as parcelas dentro da transação, grava a antecipação, marca as parcelas como antecipadas e deixa uma nota no chamado.
