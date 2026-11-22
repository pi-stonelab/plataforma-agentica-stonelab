# consultar_cotacao_moeda

Devolve a cotação oficial de uma moeda estrangeira em reais (PTAX do Banco Central) num dia.

## Quando usar

Use quando o usuário pedir quanto vale uma moeda em reais, como o dólar ou o euro, hoje ou numa data.

## Quando não usar

Não serve para converter vendas de um lojista: as vendas do mock são todas em reais. Para valores do lojista, use `consultar_transacoes_cliente` ou `consultar_liquidacoes_cliente`.

## Parâmetros

- `moeda` (texto, obrigatório): código de 3 letras da moeda. Exemplo: `USD`.
- `data` (data, opcional): dia da cotação, no formato `2026-10-14`. Sem ela, vale hoje. Não pode ser depois de hoje.

## O que devolve

Em `dados`: `moeda`, `nome_da_moeda`, `data` (o dia da cotação usada), `boletim` (de qual boletim do dia veio, de preferência o de fechamento), `cotacao_compra` e `cotacao_venda` (reais por uma unidade da moeda, como `R$ 5,4321`) e `fonte`.

Fim de semana e feriado não têm cotação: a resposta traz o último dia útil antes da data pedida, e o campo `data` diz qual foi. Diga esse dia ao usuário.

Erros possíveis: `parametro_invalido` (moeda fora do formato, moeda que o Banco Central não publica ou data depois de hoje), `nao_encontrado` (sem cotação nos 7 dias até a data) e `integracao_indisponivel` (o Banco Central não respondeu).

## Para quem mantém

- Área: `consultas_publicas`.
- Acesso: leitura.
- Integração:
  - `apis_publicas` (ver `integracoes/apis_publicas/README.md`): PTAX do Banco Central, OData `Moedas` (lista das moedas, guardada por um dia) e `CotacaoMoedaDia` (boletins do dia). Com `APIS_PUBLICAS_MODO=simulado`, três moedas com valores fixos e ilustrativos, sem rede.
- Datas: "hoje" é `HOJE_DO_MOCK` (de `mock.regras`, pela fachada `dados_sinteticos.py`). Sábado e domingo são pulados sem chamar a API; dia útil sem boletim (feriado) volta um dia, até 7 dias.
- Permissão: categoria `cambio`, comum a todos os cargos com área (`mock.regras.CATEGORIAS_COMUNS`). [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não (números e o nome da moeda).
- Situação: ativa, consulta real ao Banco Central. Nos testes, para um servidor HTTP local (`backend/tests/apoio_http.py`).
