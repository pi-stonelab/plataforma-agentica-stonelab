# executar_antecipacao

Prepara a antecipação que o lojista pediu num chamado (só N2). Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando um funcionário de nível N2 pedir para executar uma antecipação já registrada num chamado de Antecipação (o pedido do lojista precisa estar registrado). Se o lojista pediu só uma parte do valor, passe `valor_maximo`; sem ele, a execução antecipa toda a agenda disponível, e a prévia diz isso. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela e repita o valor líquido e a data do crédito. Quem registrou o pedido do lojista não o executa: se for a mesma pessoa, diga que outro N2 precisa executar.

## Quando não usar

Não use sem o chamado do pedido (registre com `registrar_pedido_antecipacao`) nem para simular (use `simular_antecipacao`).

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00004`.
- `id_chamado` (texto, obrigatório): o chamado de Antecipação com o pedido do lojista. Exemplo: `CH000071`.
- `valor_maximo` (decimal, opcional): em reais, o quanto o lojista quer antecipar, no máximo. Entram as parcelas mais próximas, inteiras, até esse valor. Exemplo: `3000`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_chamado`, `alcance`, `quantidade_de_parcelas`, `valor_antecipado`, `taxa_mensal_percentual`, `desconto`, `valor_liquido` e `data_credito`.

Erros possíveis: `parametro_invalido` (chamado que não é de Antecipação ou está fechado, antecipação recusada com o motivo, nada para antecipar), `nao_encontrado`, `permissao_negada` (abaixo de N2, lojista fora da carteira ou você registrou o pedido) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- "A execução fica com o N2, com o pedido do lojista registrado" (DOC-MOCK §7.4). Quem pode: nível N2 com as categorias `chamado` e `agenda_recebiveis`: o especialista N2 e o supervisor de atendimento. O coordenador financeiro não executa: o §8.2 dá a execução só ao N2 e o cargo dele não lê chamado de atendimento (pergunta H5 em `docs/decisoes.md`).
- O texto do pedido do lojista (resumo do chamado) aparece só no cartão, para a pessoa conferir; não vai ao modelo.
- `mock/escritas.executar_antecipacao` confere de novo as 4 recusas e as parcelas dentro da transação, recusa quem registrou o pedido (segregação, H4), grava a antecipação, marca as parcelas como antecipadas e deixa uma nota no chamado. A prévia vem de um ensaio dessa mesma execução, desfeito no fim.
