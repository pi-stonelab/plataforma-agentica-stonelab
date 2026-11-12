# listar_faturas_em_atraso

Lista as faturas vencidas e ainda não pagas de um cliente (lojista), com os dias de atraso de cada uma.

## Quando usar

Use quando o usuário quiser saber o que o cliente deve à Stone (aluguel, tarifa ou saldo negativo) e há quantos dias, e você já tiver o id_cliente. O valor e os dias de cada fatura são o que `calcular_multa_atraso` pede.

## Quando não usar

Esta ferramenta não calcula multa nem juros: para isso use `calcular_multa_atraso`. Para dividir o valor em parcelas, use `calcular_parcelas`. Para as vendas, use `consultar_transacoes_cliente`. Ela só lê: não gera acordo nem envia cobrança.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00003`.

## O que devolve

Em `dados`: `codigo`, `faturas`, `total_encontrado`, `truncado` e `valor_total` (soma dos valores das faturas da lista, texto como `R$ 399,80`; repita sem converter). Cada fatura tem `codigo` (como `I000121`), `tipo` (aluguel, tarifa ou saldo_negativo), `mes_referencia` (AAAA-MM), `vencimento` (AAAA-MM-DD), `valor` (texto como `R$ 320,00`), `situacao` (vencida) e `dias_em_atraso`. A soma não inclui multa nem juros. A lista vem da fatura de vencimento mais recente para a mais antiga. Cliente sem fatura vencida volta com a lista vazia.

Erros possíveis: `parametro_invalido` (id fora do formato), `permissao_negada` (o cliente está fora da sua carteira; a resposta é a mesma quando o código não existe) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro`.
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): banco simulado do mock (`mock/consultas.py`), lido por `dados_sinteticos.py`
- Permissão: nível e área na ficha em func.py; categoria `cobranca` e escopo de carteira vêm do cargo (`mock/regras.py`) [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
