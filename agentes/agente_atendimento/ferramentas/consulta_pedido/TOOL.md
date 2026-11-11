---
nome: consulta_pedido
acesso_agente: sim
perfis_permitidos: cliente, atendente
---

# consulta_pedido

> [ALTERAR: confirmar os perfis reais em `perfis_permitidos` e se o agente deve mesmo ter acesso]

## O que faz
Consulta o status, a previsão de entrega e os itens de um pedido pelo número.

## Quando usar
Quando o cliente pergunta "onde está meu pedido", prazo de entrega ou o que foi comprado.

## Como usar
Argumentos (JSON, uma linha):
`{"numero_pedido": "12345"}`

Se o cliente não informou o número do pedido, pergunte antes de usar.

## O que devolve
JSON com `status`, `previsao_entrega` e `itens`. Se o pedido não existir, devolve uma mensagem de "não encontrado".

## Limitações
- Só consulta; não altera nada.
- [ADICIONAR: limites reais da API, como tempo de resposta e dados que ela não traz]
