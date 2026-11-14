# consultar_liquidacoes_cliente

Lista as liquidações (depósitos diários) de um cliente (lojista), com valor, situação e motivo da falha.

## Quando usar

Use quando o usuário perguntar por que o dinheiro de um cliente não caiu ou quiser ver os depósitos recentes dele, e você já tiver o id_cliente. Quem pergunta "o dinheiro não caiu" quer a liquidação mais recente: confira a primeira da lista e, se ela tiver falhado, o `motivo_falha`.

## Quando não usar

Para as vendas do cliente, use `consultar_transacoes_cliente`. Para os dados cadastrais, use `consultar_cliente`. Para o chamado que o sistema abriu por causa da falha, use `listar_chamados_cliente`. Esta ferramenta não troca a conta de recebimento nem refaz a liquidação: isso é com o especialista N2.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00001`.
- `data_inicio` (data, opcional): primeira data do período, no formato AAAA-MM-DD. Exemplo: `2026-10-01`.
- `data_fim` (data, opcional): última data do período, no formato AAAA-MM-DD. Exemplo: `2026-10-15`.
- `limite` (inteiro, opcional): quantas liquidações trazer, de 1 a 50. Se faltar, vem 20. Exemplo: `5`.

## O que devolve

Em `dados`: `codigo`, `liquidacoes`, `total_encontrado`, `truncado` e `janela_dias`. Cada liquidação tem `id_liquidacao`, `data` (AAAA-MM-DD), `valor` (texto como `R$ 1.842,30`; repita sem converter), `situacao` (paga, falhou ou devolvida) e `motivo_falha` (vazio quando a liquidação foi paga). No mock, `conta_invalida` quer dizer que a conta de recebimento do cliente está inválida e o dinheiro ficou retido. A lista vem da mais recente para a mais antiga. Se `truncado` for verdadeiro, há mais liquidações do que o limite: restrinja o período. Alguns cargos só consultam os últimos dias: `janela_dias` diz quantos (vazio = sem limite). Sem `data_inicio`, a consulta começa no início dessa janela.

Erros possíveis: `parametro_invalido` (id fora do formato, limite fora de 1 a 50 ou data_inicio depois de data_fim), `permissao_negada` (cliente fora da sua carteira, ou período além da janela do seu cargo) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro`.
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): banco simulado do mock (`mock/consultas.py`), lido por `dados_sinteticos.py`
- Permissão: nível e área na ficha em func.py; categoria `liquidacao`, escopo de carteira e janela de 90 dias do atendente N1 vêm do cargo (`mock/regras.py`). O atendente N1 lê liquidação por decisão O4 (o cenário 1 exige) [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
