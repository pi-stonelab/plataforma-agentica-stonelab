# solicitar_ferramenta_ausente

Registra o pedido de uma ferramenta que a plataforma ainda não tem.

## Quando usar

Use quando o usuário pedir algo que nenhuma ferramenta liberada resolve. Descreva a ferramenta que faltou, em uma ou duas frases. Depois de registrar, diga ao usuário só o código do pedido. Não prometa aviso, prazo nem resposta de ninguém.

## Quando não usar

Não use para tentar de novo uma ferramenta que deu erro, nem quando alguma ferramenta liberada já resolve o pedido.

## Parâmetros

- `nome_sugerido` (texto, obrigatório): nome da ferramenta em minúsculas, com letras, números e sublinhado, de 3 a 60 caracteres, começando por letra, sem 6 ou mais dígitos seguidos (o nome vai para a fila do Jira e não pode carregar CPF nem cartão; nome que a máscara de texto livre alteraria também é recusado). Exemplo: `listar_chargebacks`.
- `descricao` (texto, obrigatório): o que a ferramenta deveria fazer, em uma ou duas frases, sem dados de clientes. Exemplo: `Listar as contestações abertas de um cliente`.

## O que devolve

Em `dados`: `id_pedido` (como `PED-0001`), `nome_sugerido` e `vezes_pedida` (quantas vezes esse nome já foi pedido).

Erros possíveis: `parametro_invalido` (nome fora do formato ou com número longo, ou descrição vazia) e `integracao_indisponivel` (a fila de pedidos está cheia).

## Para quem mantém

- Área: `plataforma`.
- Acesso: escrita.
- Integração: nenhuma, roda só com os parâmetros recebidos.
- Permissão: provisória na ficha em func.py [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Escrita: a descrição passa pela máscara de texto livre antes de entrar na fila; a fila tem trava (`TRAVA_DOS_PEDIDOS`), então duas chamadas simultâneas não repetem o `id_pedido`. Só registra o pedido em memória, sem efeito fora da plataforma e sem avisar ninguém. Fica ativa por exceção explícita em `governanca.ESCRITA_SEM_CONFIRMACAO`.
- Automação semanal [aqui conectamos com o back-end e o Jira: juntar os pedidos acumulados da semana e enviar a um card único de pedidos de ferramenta, KAN-27].
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
