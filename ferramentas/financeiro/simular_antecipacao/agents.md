# simular_antecipacao

Simula quanto o cliente (lojista) recebe se antecipar hoje toda a agenda que dá para antecipar, ou diz por que ele não pode.

## Quando usar

Use quando o usuário perguntar quanto o lojista recebe se antecipar, ou se ele pode antecipar. Diga sempre o valor líquido, o desconto, a taxa mensal e o dia em que o dinheiro cai. Se `pode_antecipar` for falso, explique cada motivo de recusa.

## Quando não usar

Para ver as parcelas da agenda, use `consultar_agenda_recebiveis`. Esta ferramenta só simula: não pede nem executa a antecipação. Quem executa é o especialista N2, com o pedido do lojista registrado num chamado.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00004`.

## O que devolve

Em `dados`: `id_cliente`, `pode_antecipar`, `motivos_de_recusa` (lista em texto; vazia quando pode), `simulacao` e `aviso`. A `simulacao` (vazia quando não pode) traz `data_credito` (o dia em que o dinheiro cai, AAAA-MM-DD), `taxa_mensal_percentual` (número em percentual com duas casas, como `2.99`), `quantidade_de_parcelas`, `valor_antecipado` (soma das parcelas antecipadas), `desconto` e `valor_liquido` (o que o lojista recebe). As parcelas que já caem no dia do crédito, as retidas e as bloqueadas ficam de fora. O desconto é proporcional aos dias que faltam para cada parcela. Repita os valores sem converter.

Os motivos de recusa possíveis: lojista bloqueado, conta de recebimento em verificação, conta de recebimento inválida (o dinheiro fica retido até a conta ser corrigida pelo N2), fatura vencida há mais de 15 dias ou não há parcelas futuras para antecipar.

Erros possíveis: `parametro_invalido` (id fora do formato), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (cenário 4 do DOC-MOCK; regra da antecipação no §7.4).
- Acesso: cálculo sobre a agenda.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): `motivos_de_recusa_da_antecipacao` e `simulacao_de_antecipacao` da fachada (`dados_sinteticos.py`), com a taxa do plano e o desconto de `mock/regras.py`.
- Permissão: categoria `agenda_recebiveis` e escopo de carteira vêm do cargo (`mock/regras.py`). O N1 simula; executar é do N2 (escrita do bloco D).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
