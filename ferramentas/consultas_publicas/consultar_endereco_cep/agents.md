# consultar_endereco_cep

Devolve o endereço público de um CEP: logradouro, bairro, cidade e UF.

## Quando usar

Use quando o usuário informar um CEP e quiser confirmar a rua, o bairro ou a cidade.

## Quando não usar

Esta ferramenta não traz o endereço cadastrado de um cliente. Para os dados do cliente, use `consultar_cliente`.

## Parâmetros

- `cep` (texto, obrigatório): CEP com 8 dígitos, com ou sem hífen. Exemplo: `01310-100`.

## O que devolve

Em `dados`: `cep` (só os 8 dígitos), `logradouro`, `bairro`, `cidade` e `uf`.

Erros possíveis: `parametro_invalido` (CEP fora do formato) e `nao_encontrado` (o CEP não consta na base).

## Para quem mantém

- Área: `consultas_publicas`.
- Acesso: leitura.
- Integração:
  - `apis_publicas` (ver `integracoes/apis_publicas/README.md`): [preencher: quais APIs, por exemplo CEP e câmbio]
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
