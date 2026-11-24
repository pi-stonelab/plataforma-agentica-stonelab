# consultar_agenda_recebiveis

Mostra a agenda de recebíveis de um cliente (lojista): o que vai cair, parcela por parcela, e o que está retido ou bloqueado.

## Quando usar

Use quando o usuário perguntar quanto o cliente tem a receber, quando cai uma venda, ou por que um valor está retido ou bloqueado. Sem datas, a lista começa hoje (o que ainda vai cair). Para ver o que caiu num dia passado, passe `data_inicio` e `data_fim`.

## Quando não usar

Para o depósito que caiu (ou falhou) num dia, use `consultar_liquidacoes_cliente`. Para saber quanto ele recebe se antecipar, use `simular_antecipacao`. Para conferir se os depósitos bateram com a agenda, use `conferir_liquidacoes`.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00004`.
- `data_inicio` (data, opcional): primeira data prevista, no formato AAAA-MM-DD. Se faltar, é hoje; se só a `data_fim` for passada e já tiver passado, são os 30 dias que terminam nela. Exemplo: `2026-10-16`.
- `data_fim` (data, opcional): última data prevista, no formato AAAA-MM-DD. Exemplo: `2026-12-31`.
- `situacao` (texto, opcional): só as parcelas `previsto`, `pago`, `retido`, `bloqueado` ou `antecipado`. Exemplo: `retido`.
- `limite` (inteiro, opcional): quantas parcelas trazer, de 1 a 50. Se faltar, vêm 20. Exemplo: `10`.

## O que devolve

Em `dados`: `codigo`, `agenda_futura`, `parcelas`, `total_encontrado`, `truncado` e `janela_dias`. A `agenda_futura` resume tudo o que ainda vai cair, por situação (`previsto`, `retido`, `bloqueado`, `antecipado`), com `quantidade` e `valor`, sem depender das datas pedidas. Cada parcela tem `codigo` (como `R0000747`), `id_venda`, `numero_parcela`, `data_prevista`, `valor` e `situacao`, da data mais próxima para a mais distante. Valores em reais são texto como `R$ 217,54`: repita sem converter. `retido` quer dizer preso por chargeback ou por falha na liquidação; `bloqueado`, por decisão judicial ou da Stone.

Erros possíveis: `parametro_invalido` (id fora do formato, situação desconhecida, limite fora de 1 a 50 ou data_inicio depois de data_fim), `permissao_negada` (cliente fora da sua carteira, ou período antes da janela do seu cargo) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (cenários 1 e 4 do DOC-MOCK; regras da agenda no §7.2).
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): tabela `recebiveis` do mock (`buscar_agenda` e `resumo_da_agenda`), lida por `dados_sinteticos.py`.
- Permissão: categoria `agenda_recebiveis`, escopo de carteira e janela de 90 dias do atendente N1 vêm do cargo (`mock/regras.py`).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
