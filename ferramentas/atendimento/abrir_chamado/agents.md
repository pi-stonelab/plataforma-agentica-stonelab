# abrir_chamado

Prepara um chamado novo do lojista; só abre quando o funcionário confirma.

## Quando usar

Use quando o funcionário pedir para registrar um problema novo do lojista que ainda não tem chamado (confira antes com `listar_chamados_cliente`). A prioridade, o nível (N1 ou N2) e o prazo saem das regras da plataforma, não de você: mostre o que veio na prévia. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela. Nunca diga que o chamado foi aberto.

## Quando não usar

Não use para acrescentar informação a um chamado que já existe (use `adicionar_nota_chamado`) nem para registrar pedido de antecipação (use `registrar_pedido_antecipacao`).

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00001`.
- `categoria` (texto, obrigatório): uma de `Dúvida de produto`, `Recebimento`, `Maquininha`, `Fatura e aluguel`, `Antecipação`, `Alteração cadastral` ou `Contestação`.
- `resumo` (texto, obrigatório, até 1000 caracteres): o problema em poucas frases, sem CPF, cartão ou conta completos.
- `canal` (texto, opcional): por onde o lojista falou: `whatsapp` (padrão), `telefone`, `chat` ou `email`.
- `impede_vender` (texto, opcional): `sim` quando a maquininha impede o lojista de vender (o chamado vira crítico).
- `valor_envolvido` (decimal, opcional): valor em reais do problema, como `1250.00`; acima de R$ 1.000,00 o chamado vai para o N2.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `categoria`, `resumo` (mascarado), `canal`, `prioridade`, `nivel_atendimento` e `prazo_em`.

Erros possíveis: `parametro_invalido` (categoria, canal ou resumo inválidos), `permissao_negada` (lojista fora da sua carteira) e `integracao_indisponivel` (CRM fora do ar).

## Para quem mantém

- Área: `atendimento`. Escrita em duas fases (`ferramentas/confirmacoes.py`), listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- `montar` calcula prioridade, nível e prazo com `escritas_sinteticas.classificar_chamado` (DOC-MOCK §6.3 e §6.4), a mesma conta que a gravação usa. `efetivar` grava por `mock/escritas.abrir_chamado` com o funcionário que confirmou; quem abre fica responsável se o nível dele dá conta, senão o chamado fica "novo" na fila certa.
- Quem pode: os cargos que atendem chamados (`regras.NIVEL_DE_ATENDIMENTO_DO_CARGO`: N1, N2, supervisor e ouvidoria), dentro da carteira. O financeiro recebe `permissao_negada` da gravação.
- LGPD: o resumo passa pela máscara de texto livre antes da prévia, e é esse texto que vai ao banco.
- Situação: ativa, grava no CRM simulado (`MOCK_ESCRITA_DATABASE_URL` no Postgres, papel `mock_escrita`).
