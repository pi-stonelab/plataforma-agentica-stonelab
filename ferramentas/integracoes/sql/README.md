# Banco SQL de transações

[preencher: o que é este sistema e para que a plataforma o usa]

## Ferramentas que usam

- `financeiro/consultar_transacoes_cliente` (leitura)
- `financeiro/listar_faturas_em_atraso` (leitura)
- `financeiro/consultar_liquidacoes_cliente` (leitura)
- `financeiro/consultar_saldo_conta` (leitura)
- `financeiro/listar_contestacoes_cliente` (leitura)

## Conector

`integracoes/sistemas_internos.py` (`ConectorInterno`), modo sempre `simulado`: o core, o cadastro e a cobrança são o mock. A saúde vem dos sistemas `cadastro`, `core` e `cobranca` de `mock.falhas`.

## Ligação

[aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]

## Hoje

Dados simulados em `ferramentas/dados_sinteticos.py` (`buscar_cliente`, `buscar_transacoes`, `buscar_liquidacoes` e `buscar_faturas_em_atraso`): lê vendas, liquidações e faturas do lojista no banco do mock (`mock/consultas.py`). Trocar pelo real é trocar o corpo dessas funções.
