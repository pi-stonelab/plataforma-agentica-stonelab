# APIs públicas

Duas APIs abertas, sem credencial: o ViaCEP (endereço de um CEP) e a PTAX do Banco Central (cotação oficial de
moedas). Nenhuma recebe dado de lojista: só o CEP ou o código da moeda e a data.

## Ferramentas que usam

- `consultas_publicas/consultar_endereco_cep` (leitura)
- `consultas_publicas/consultar_cotacao_moeda` (leitura)

## Conector

`conector.py` (`ConectorApisPublicas`), sobre a base `integracoes/conector.py` e o cliente `integracoes/http.py`.
Cada API tem o próprio disjuntor (`viacep` e `ptax`): o ViaCEP fora do ar não pausa a cotação. A saúde vem das
últimas chamadas; `python -m ferramentas.integracoes testar apis_publicas` (com `MODO_TERMINAL=1`) consulta o CEP
da Praça da Sé e a lista de moedas.

## Ligação

- ViaCEP: `GET {VIACEP_URL}/ws/{cep}/json/`. CEP inexistente volta `{"erro": "true"}` (o ViaCEP já usou o booleano
  `true`; os dois valem). Campos usados: `cep`, `logradouro`, `bairro`, `localidade` e `uf`.
- PTAX: OData em `{BCB_PTAX_URL}`. `Moedas?$top=100&$format=json` (campos `simbolo` e `nomeFormatado`; a lista fica
  guardada por um dia) e `CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)?@moeda='USD'&@dataCotacao='MM-DD-AAAA'`
  (campos `cotacaoCompra`, `cotacaoVenda`, `dataHoraCotacao` e `tipoBoletim`; o de fechamento é o preferido).
- Variáveis (`.env.example`): `APIS_PUBLICAS_MODO` (`real`, o padrão; `simulado`; `desligado`), `VIACEP_URL`
  (padrão `https://viacep.com.br`) e `BCB_PTAX_URL` (padrão
  `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata`). HTTPS obrigatório fora do localhost.

## Hoje

Consulta real. No modo `simulado`, sem rede: os 3 CEPs de exemplo de `ferramentas/dados_sinteticos.py` e três
moedas com valores fixos e ilustrativos (a resposta diz isso no campo `fonte`). Nos testes, um servidor HTTP local
que fala como as duas APIs (`backend/tests/apoio_http.py`).
