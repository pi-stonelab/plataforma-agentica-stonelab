# financeiro

Vendas, depósitos, agenda de recebíveis, faturas, acordos e contestações de um cliente (lojista), e cálculos de multa, parcelas e antecipação.

## Como escolher

Escolha pela pergunta, entre as ferramentas da lista abaixo (só aparecem as liberadas para você):

- O que já aconteceu (vendas, depósitos) fica nas consultas de transações e de liquidações.
- O que ainda vai cair, ou por que um valor está retido, fica na agenda de recebíveis (o saldo todo, sem as parcelas, é uma consulta à parte).
- Se os depósitos bateram com a agenda, use a conferência, não a lista de depósitos.
- Chargeback e devolução de Pix ficam nas contestações (e se o lojista passou do limite de chargeback, na taxa mensal dele); dívida com a Stone, nas faturas e nos acordos.
- Os cálculos (multa, parcelas, antecipação) só simulam: não executam nada.
- Nomes que você não vê na lista não estão liberados para você.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integrações da área: `sql`.
- Ferramentas (18):
  - `consultar_transacoes_cliente` (leitura)
  - `consultar_liquidacoes_cliente` (leitura)
  - `consultar_agenda_recebiveis` (leitura)
  - `consultar_saldo_agenda` (leitura; só o saldo, é o que a cobrança vê da agenda)
  - `conferir_liquidacoes` (leitura)
  - `listar_contestacoes_cliente` (leitura)
  - `consultar_taxa_contestacao_cliente` (leitura)
  - `listar_faturas_em_atraso` (leitura)
  - `listar_acordos` (leitura)
  - `calcular_multa_atraso` (cálculo)
  - `calcular_parcelas` (cálculo)
  - `simular_antecipacao` (cálculo)
  - `executar_antecipacao` (escrita com confirmação, ativa, só N2)
  - `reprocessar_liquidacao` (escrita com confirmação, ativa)
  - `registrar_acordo` (escrita com confirmação, ativa)
  - `aprovar_acordo` (escrita com confirmação, ativa)
  - `retirar_acordo` (escrita com confirmação, ativa)
  - `registrar_defesa_chargeback` (escrita com confirmação, ativa, Disputas)
- Saiu: `consultar_saldo_conta`. A Stone não guarda um saldo de conta do lojista no mock; o que ele tem a receber está na agenda (`consultar_agenda_recebiveis`). Ver `docs/decisoes.md`.
- Enviar a defesa à bandeira continua de fora: `registrar_defesa_chargeback` só registra no cadastro da Stone os documentos que o lojista entregou.
