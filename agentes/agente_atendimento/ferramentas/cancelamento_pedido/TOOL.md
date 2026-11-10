---
nome: cancelamento_pedido
acesso_agente: nao
perfis_permitidos: atendente
---

# cancelamento_pedido

> [ALTERAR: exemplo de ferramenta SEM acesso para o agente, usada para testar o bloqueio. O responsável pelas ferramentas decide o acesso real.]

## O que faz
Cancela um pedido e inicia o estorno.

## Como usar
Argumentos (JSON, uma linha):
`{"numero_pedido": "12345", "motivo": "texto"}`

## Acesso
Ação sensível: hoje só atendentes humanos podem executar. O agente deve explicar ao cliente e encaminhar a um atendente.
