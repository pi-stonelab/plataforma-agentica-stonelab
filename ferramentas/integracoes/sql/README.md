# Banco SQL de transações

[preencher: o que é este sistema e para que a plataforma o usa]

## Ferramentas que usam

- `financeiro/consultar_transacoes_cliente` (leitura)
- `financeiro/listar_faturas_em_atraso` (leitura)
- `financeiro/consultar_saldo_conta` (leitura)
- `financeiro/listar_contestacoes_cliente` (leitura)

## Conector

[preencher: como a plataforma fala com ele e como checa se está de pé]

## Ligação

[aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]

## Hoje

Dados simulados em `ferramentas/dados_sinteticos.py` (`buscar_cliente` e `buscar_transacoes`): lê as vendas do lojista no banco do mock (`mock/consultas.py`). Trocar pelo real é trocar o corpo dessas funções.
