# Banco SQL de transações

O core, o cadastro, a cobrança e as disputas da Stone simulada: vendas, agenda de recebíveis, depósitos, faturas, acordos, chargebacks e casos de Pix de cada lojista.

## Ferramentas que usam

- `financeiro/consultar_transacoes_cliente` (leitura)
- `financeiro/consultar_liquidacoes_cliente` (leitura)
- `financeiro/consultar_agenda_recebiveis` (leitura)
- `financeiro/consultar_saldo_agenda` (leitura)
- `financeiro/conferir_liquidacoes` (leitura)
- `financeiro/listar_contestacoes_cliente` (leitura)
- `financeiro/listar_faturas_em_atraso` (leitura)
- `financeiro/listar_acordos` (leitura)
- `financeiro/simular_antecipacao` (cálculo sobre a agenda)

## Conector

`integracoes/sistemas_internos.py` (`ConectorInterno`), modo sempre `simulado`: o core, o cadastro, a cobrança e as disputas são o mock. A saúde vem dos sistemas `cadastro`, `core`, `cobranca` e `disputas` de `mock.falhas`.

## Ligação

[aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]

## Hoje

Dados simulados em `ferramentas/dados_sinteticos.py` (`buscar_transacoes`, `buscar_liquidacoes`, `buscar_agenda`, `resumo_da_agenda`, `agenda_e_liquidacoes_por_dia`, `buscar_faturas_em_atraso`, `buscar_acordos`, `buscar_chargebacks`, `buscar_casos_pix` e a simulação de antecipação): lê o banco do mock (`mock/consultas.py`). Trocar pelo real é trocar o corpo dessas funções.
