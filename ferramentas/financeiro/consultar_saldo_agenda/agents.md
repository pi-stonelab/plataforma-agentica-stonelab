# consultar_saldo_agenda

Mostra quanto um cliente (lojista) ainda tem a receber na agenda, por situação, sem listar as parcelas.

## Quando usar

Use quando o usuário só precisar do saldo: quanto o cliente tem a receber no total, quanto está retido ou bloqueado. É o que a cobrança vê da agenda do lojista. Diga a `data_base`: o saldo conta só o que cai a partir dela.

## Quando não usar

Para as parcelas (data e valor de cada uma) e a simulação de antecipação, use `consultar_agenda_recebiveis` e `simular_antecipacao`, que nem todo cargo alcança. Para dívida e faturas, use `listar_faturas_em_atraso`.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00003`.

## O que devolve

Em `dados`: `id_cliente`, `data_base` (AAAA-MM-DD) e `agenda_futura`, que resume tudo o que ainda vai cair por situação (`previsto`, `retido`, `bloqueado`, `antecipado`), cada uma com `quantidade` e `valor`. Valores em reais são texto como `R$ 12.000,00`: repita sem converter. `retido` quer dizer preso por chargeback ou por falha na liquidação; `bloqueado`, por decisão judicial ou da Stone.

Erros possíveis: `parametro_invalido` (id fora do formato), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (DOC-MOCK §8.2: a cobrança vê "só faturas, pagamentos, acordos e o saldo da agenda").
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): tabela `recebiveis` do mock (`resumo_da_agenda`), lida por `dados_sinteticos.py`.
- Permissão: categoria própria `saldo_agenda` (a de `agenda_recebiveis`, que dá as parcelas e a simulação, inclui esta). Escopo de carteira vem do cargo (`mock/regras.py`).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
