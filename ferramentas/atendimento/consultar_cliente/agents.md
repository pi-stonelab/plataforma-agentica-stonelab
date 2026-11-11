# consultar_cliente

Devolve os dados cadastrais de um cliente a partir do id_cliente.

## Quando usar

Use quando o usuário pedir nome, segmento, cidade ou situação de um cliente e você já tiver o id_cliente.

## Quando não usar

Para as transações do cliente, use `consultar_transacoes_cliente`. Esta ferramenta não busca por nome: se faltar o id_cliente, peça ao usuário.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `CLI-` seguido de quatro dígitos. Exemplo: `CLI-0001`.

## O que devolve

Em `dados`: `id_cliente`, `nome_fantasia`, `segmento`, `cidade`, `uf`, `situacao` e `cliente_desde` (data no formato AAAA-MM-DD).

Erros possíveis: `parametro_invalido` (id fora do formato), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (o cliente não existe).

## Para quem mantém

- Área: `atendimento`.
- Acesso: leitura.
- Integração:
  - `crm` (ver `integracoes/crm/README.md`): [aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
