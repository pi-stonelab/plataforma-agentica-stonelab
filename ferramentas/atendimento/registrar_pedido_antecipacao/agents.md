# registrar_pedido_antecipacao

Prepara o pedido de antecipação do lojista para o N2 executar. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando o lojista pedir para antecipar e o funcionário quiser encaminhar o pedido. Antes, mostre a simulação com `simular_antecipacao`. A execução é sempre do N2. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela e que o N2 executa depois.

## Quando não usar

Não use para executar a antecipação (é `executar_antecipacao`, do N2) nem quando a simulação recusou: o lojista ouve o motivo.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00004`.
- `resumo` (texto, obrigatório, até 1000 caracteres): o pedido do lojista, como ele fez.
- `canal` (texto, opcional): `whatsapp` (padrão), `telefone`, `chat` ou `email`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `resumo`, `canal`, `valor_antecipado`, `desconto`, `valor_liquido`, `data_credito`, `nivel_atendimento` (`N2`) e `prazo_em`.

Erros possíveis: `parametro_invalido` (resumo vazio, canal desconhecido, antecipação recusada com o motivo, nada para antecipar), `permissao_negada` (lojista fora da carteira) e `integracao_indisponivel`.

## Para quem mantém

- Área: `atendimento`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- Abre um chamado de categoria `Antecipação` com nível mínimo N2 (`escritas_sinteticas.abrir_chamado`), que o `executar_antecipacao` exige. As recusas do §7.4 são checadas na prévia e de novo na execução.
- Quem pode: cargos que atendem chamados e veem a agenda (N1 e N2 do atendimento, supervisor), dentro da carteira.
