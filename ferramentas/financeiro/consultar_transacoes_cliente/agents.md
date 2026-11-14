# consultar_transacoes_cliente

Lista as vendas mais recentes de um cliente (lojista), com filtro opcional por período.

## Quando usar

Use quando o usuário perguntar pelas vendas de um cliente e você já tiver o id_cliente.

## Quando não usar

Para os dados cadastrais do cliente, use `consultar_cliente`. Para calcular multa de uma fatura, use `calcular_multa_atraso`.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00001`.
- `data_inicio` (data, opcional): primeira data do período, no formato AAAA-MM-DD. Exemplo: `2026-03-01`.
- `data_fim` (data, opcional): última data do período, no formato AAAA-MM-DD. Exemplo: `2026-03-31`.
- `limite` (inteiro, opcional): quantas transações trazer, de 1 a 50. Se faltar, vem 20. Exemplo: `10`.

## O que devolve

Em `dados`: `codigo`, `transacoes`, `total_encontrado`, `truncado` e `janela_dias`. Cada transação tem `codigo`, `data_hora`, `modalidade` (debito, credito_a_vista, parcelado ou pix), `parcelas`, `valor_bruto` e `valor_liquido` (texto como `R$ 1.842,30`; repita sem converter) e `situacao` (aprovada, negada ou cancelada). A lista vem da mais recente para a mais antiga. Se `truncado` for verdadeiro, há mais transações do que o limite: restrinja o período em vez de pedir tudo. Alguns cargos só consultam os últimos dias: `janela_dias` diz quantos (vazio = sem limite). Sem `data_inicio`, a consulta começa no início dessa janela.

Erros possíveis: `parametro_invalido` (id fora do formato, limite fora de 1 a 50 ou data_inicio depois de data_fim), `permissao_negada` (cliente fora da sua carteira, ou período além da janela do seu cargo) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro`.
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): banco simulado do mock (`mock/consultas.py`), lido por `dados_sinteticos.py`
- Permissão: nível e área na ficha em func.py; categoria `venda`, escopo de carteira e janela de 90 dias do atendente N1 vêm do cargo (`mock/regras.py`) [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
