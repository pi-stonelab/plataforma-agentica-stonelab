# solicitar_ferramenta_ausente

Registra o pedido de uma ferramenta que a plataforma ainda não tem.

## Quando usar

Use quando o usuário pedir algo que nenhuma ferramenta liberada resolve. Descreva a ferramenta que faltou, para a equipe avaliar.

## Quando não usar

Não use para tentar de novo uma ferramenta que deu erro, nem quando alguma ferramenta liberada já resolve o pedido.

## Parâmetros

- `nome_sugerido` (texto, obrigatório): nome da ferramenta em minúsculas, com letras, números e sublinhado, de 3 a 60 caracteres, começando por letra. Exemplo: `listar_chargebacks`.
- `descricao` (texto, obrigatório): o que a ferramenta deveria fazer, em uma ou duas frases, sem dados de clientes. Exemplo: `Listar as contestações abertas de um cliente`.

## O que devolve

Em `dados`: `id_pedido` (como `PED-0001`), `nome_sugerido` e `vezes_pedida` (quantas vezes esse nome já foi pedido).

Erros possíveis: `parametro_invalido` (nome fora do formato ou descrição vazia) e `integracao_indisponivel` (a fila de pedidos está cheia).

## Para quem mantém

- Área: `plataforma`.
- Acesso: escrita.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Escrita: só registra o pedido em memória, sem efeito fora da plataforma. Fica ativa por exceção explícita em `governanca.ESCRITA_SEM_CONFIRMACAO`.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
