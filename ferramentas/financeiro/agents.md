# financeiro

Vendas, depósitos, agenda de recebíveis, faturas, acordos e contestações de um cliente (lojista), e cálculos de multa, parcelas e antecipação.

## Como escolher

Escolha pela pergunta, entre as ferramentas da lista abaixo (só aparecem as liberadas para você):

- O que já aconteceu (vendas, depósitos) fica nas consultas de transações e de liquidações.
- O que ainda vai cair, ou por que um valor está retido, fica na agenda de recebíveis.
- Se os depósitos bateram com a agenda, use a conferência, não a lista de depósitos.
- Chargeback e devolução de Pix ficam nas contestações (e se o lojista passou do limite de chargeback, na taxa mensal dele); dívida com a Stone, nas faturas e nos acordos.
- Os cálculos (multa, parcelas, antecipação) só simulam: não executam nada.
- Nomes que você não vê na lista não estão liberados para você.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integrações da área: `sql`.
- Ferramentas (11):
  - `consultar_transacoes_cliente` (leitura)
  - `consultar_liquidacoes_cliente` (leitura)
  - `consultar_agenda_recebiveis` (leitura)
  - `conferir_liquidacoes` (leitura)
  - `listar_contestacoes_cliente` (leitura)
  - `consultar_taxa_contestacao_cliente` (leitura)
  - `listar_faturas_em_atraso` (leitura)
  - `listar_acordos` (leitura)
  - `calcular_multa_atraso` (cálculo)
  - `calcular_parcelas` (cálculo)
  - `simular_antecipacao` (cálculo)
- Saiu: `consultar_saldo_conta`. A Stone não guarda um saldo de conta do lojista no mock; o que ele tem a receber está na agenda (`consultar_agenda_recebiveis`). Ver `docs/decisoes.md`.
- Escrita (executar antecipação, aprovar acordo, enviar defesa) é do bloco D e fica de fora daqui.
