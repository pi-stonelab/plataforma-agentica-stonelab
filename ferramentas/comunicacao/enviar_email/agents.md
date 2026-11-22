# enviar_email

Prepara um e-mail para um contato cadastrado do lojista e deixa a prévia esperando a confirmação do funcionário; nesta etapa nada é enviado.

## Quando usar

Use quando o funcionário pedir para mandar um e-mail ao lojista, por exemplo com o resumo das vendas ou a explicação de uma liquidação que falhou. Antes, busque com as outras ferramentas os dados que vão no texto e escreva só o que veio delas. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação dele na tela e repita o assunto. Nunca diga que o e-mail foi enviado: quem envia é o funcionário, ao confirmar.

## Quando não usar

Não use para mensagens entre funcionários nem para um endereço digitado na conversa: o destinatário é sempre um contato cadastrado do lojista. Se a prévia já foi criada e o funcionário quer mudar o texto, crie uma prévia nova com o texto corrigido; a antiga expira sozinha.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00001`.
- `assunto` (texto, obrigatório, até 120 caracteres, em uma linha só): assunto do e-mail. Exemplo: `Liquidação de 14/10/2026`.
- `corpo` (texto, obrigatório, até 2000 caracteres): o texto do e-mail, em português e sem CPF, cartão ou conta completos. Para quebrar linha, use `\n` dentro do JSON.
- `papel_contato` (texto, opcional): qual contato do lojista recebe: `financeiro`, `socio` ou `operador_caixa`. Sem ele, vai para o `financeiro` e, se o lojista não tiver, para o `socio`.

## O que devolve

Em `dados`: `confirmacao_id` (como `CONF-ABCDEFGHJK`), `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos), `para` (código do lojista, papel do contato e e-mail mascarado), `assunto` e `corpo` como serão enviados (CPF e cartão escritos no texto saem mascarados).

Erros possíveis: `parametro_invalido` (assunto ou corpo vazio ou longo demais, papel desconhecido, código fora do formato), `permissao_negada` (lojista fora da sua carteira), `nao_encontrado` (lojista sem contato com esse papel) e `integracao_indisponivel` (cadastro fora do ar ou prévias demais esperando confirmação).

## Para quem mantém

- Área: `comunicacao`. Acesso: escrita em duas fases (`ferramentas/confirmacoes.py`), listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- Fase 1 (o agente): `montar` valida, confere a carteira, acha o e-mail do contato no cadastro simulado e guarda o pedido. O modelo vê a prévia já mascarada e nunca vê nem escolhe o endereço.
- Fase 2 (a pessoa): `confirmacoes.confirmar(confirmacao_id, usuario)` revalida cargo e carteira e chama `efetivar`, que envia por SMTP (`ferramentas/email_smtp.py`), pela conta da plataforma, com o primeiro nome de quem confirmou no remetente ("Ana via Stone") e o e-mail dele no "responder para". O modelo nunca vê o e-mail do funcionário. Sem `EMAIL_SMTP_HOST` no .env o envio está desligado, e `montar` já responde `integracao_indisponivel`. Uso único, só o mesmo funcionário, validade de 15 minutos. Não existe ferramenta de confirmar: o agente não alcança a fase 2.
- Quem pode: os cargos com a categoria `contato` (atendimento N1 e N2, supervisor, ouvidoria, cobrança e coordenador financeiro), sempre dentro da própria carteira.
- LGPD: assunto e corpo passam pela máscara de texto livre antes da prévia, e é esse texto que vai. O conteúdo some do pedido ao confirmar, cancelar ou expirar. O registro de chamadas guarda só metadados.
- Integração: `email` (`ferramentas/integracoes/email/`), envio por SMTP com a conta de envio da plataforma. O sistema `email` de `mock.falhas` desliga o envio. Gmail e Outlook pela conta de cada pessoa ficam para os conectores do Google e da Microsoft, com ferramentas próprias.
- Ligações com outras frentes:
  - Tabela e rotas de confirmação: marcador do back-end em `ferramentas/confirmacoes.py`.
  - [A FAZER (Larissa, interface): cartão de revisão com o assunto, o corpo, o contato mascarado e o tempo restante, com os botões enviar e descartar]
  - [A FAZER (Christopher e Isack, agentes, KAN-55): avisar no `Turno` que há prévia aguardando, para o orquestrador mostrar o cartão sem depender do texto do FINAL]
  - [DECIDIR (Pedro e Brenno, segurança): se o supervisor pode confirmar a prévia de outra pessoa; hoje só quem pediu confirma]
  - [DECIDIR (Pedro e Brenno, segurança): como impedir que o corpo leve dado de outro lojista da carteira; hoje depende da revisão de quem confirma]
- Limites conhecidos: e-mail e telefone escritos no corpo não são mascarados (MED-4, só CPF e cartão); não há limite de envios por hora; a fila de prévias fica em memória; depois de um envio incerto (o servidor não confirmou), conferir a caixa de saída antes de pedir outra prévia.
- Situação: ativa, dados sintéticos, envio por SMTP. Nos testes, para um servidor SMTP local (`backend/tests/apoio_smtp.py`).
