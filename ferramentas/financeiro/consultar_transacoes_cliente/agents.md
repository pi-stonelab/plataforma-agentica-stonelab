# consultar_transacoes_cliente

Lista as transações mais recentes de um cliente, com filtro opcional por período.

## Quando usar

Use quando o usuário perguntar por pagamentos, estornos ou contestações de um cliente e você já tiver o id_cliente.

## Quando não usar

Para os dados cadastrais do cliente, use `consultar_cliente`. Para calcular multa de uma fatura, use `calcular_multa_atraso`.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `CLI-` seguido de quatro dígitos. Exemplo: `CLI-0001`.
- `data_inicio` (data, opcional): primeira data do período, no formato AAAA-MM-DD. Exemplo: `2026-03-01`.
- `data_fim` (data, opcional): última data do período, no formato AAAA-MM-DD. Exemplo: `2026-03-31`.
- `limite` (inteiro, opcional): quantas transações trazer, de 1 a 50. Se faltar, vem 20. Exemplo: `10`.

## O que devolve

Em `dados`: `id_cliente`, `transacoes`, `total_encontrado` e `truncado`. Cada transação tem `id_transacao`, `data` (AAAA-MM-DD), `valor`, `tipo` (credito, debito ou pix) e `situacao` (aprovada, estornada ou contestada). A lista vem da mais recente para a mais antiga. Se `truncado` for verdadeiro, há mais transações do que o limite: restrinja o período em vez de pedir tudo.

Erros possíveis: `parametro_invalido` (id fora do formato, limite fora de 1 a 50 ou data_inicio depois de data_fim), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (o cliente não existe).

## Para quem mantém

- Área: `financeiro`.
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): [aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
