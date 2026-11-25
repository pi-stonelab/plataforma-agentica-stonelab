# chamados_internos

Chamados internos da Stone no Jira (pedidos a outros times, falha de sistema): consultar, abrir e comentar.

## Como escolher

- O funcionário cita uma chave como `KAN-123` e quer saber como está: `consultar_chamado_jira`.
- Precisa pedir algo a outro time ou registrar uma falha de sistema: `abrir_chamado_jira`.
- Quer acrescentar uma informação a um chamado interno que já existe: `comentar_chamado_jira`.
- Chamado de lojista (código `CH000001`) não é daqui: use as ferramentas de `atendimento`.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integração da área: `jira` (`ferramentas/integracoes/jira/`).
- Ferramentas ativas (3):
  - `consultar_chamado_jira` (leitura)
  - `abrir_chamado_jira` (escrita em duas fases)
  - `comentar_chamado_jira` (escrita em duas fases)
- Projetos e tipos vêm da lista do `.env` (`JIRA_PROJETOS`, `JIRA_TIPOS`); sem token, a área some do índice.
