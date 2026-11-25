# Estado final das ferramentas (24/11)

Frente 4 (Ferramentas e Integrações). Números tirados de `catalogo.carregar()`: 59 ferramentas em 8 áreas, todas
ativas (35 de leitura, 20 de escrita, 4 de cálculo). Das 20 escritas, 18 são em duas fases (prévia e confirmação) e duas gravam direto: `solicitar_ferramenta_ausente` e
`entregar_arquivo` (só gera um arquivo para a própria pessoa). Ativa quer dizer com lógica no `func.py`; as de integração externa só respondem com a integração
ligada no `.env`.

## Ferramentas por área

### atendimento (14)

- `abrir_chamado`: escrita com confirmação; integração crm; nível N1; áreas atendimento.
- `adicionar_nota_chamado`: escrita com confirmação; integração crm; nível N1; áreas atendimento.
- `atualizar_situacao_chamado`: escrita com confirmação; integração crm; nível N1; áreas atendimento.
- `buscar_clientes`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `consultar_base_conhecimento`: leitura; integração crm; nível N1; áreas todas.
- `consultar_chamado`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `consultar_cliente`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `consultar_contatos_lojista`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `consultar_historico_contato`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `listar_chamados_cliente`: leitura; integração crm; nível N1; áreas atendimento, financeiro.
- `listar_meus_chamados`: leitura; integração crm; nível N1; áreas atendimento.
- `registrar_pedido_antecipacao`: escrita com confirmação; integração crm, sql; nível N1; áreas atendimento.
- `resumir_satisfacao`: leitura; integração crm; nível N1; áreas atendimento.
- `verificar_identidade_contato`: leitura; integração crm; nível N1; áreas atendimento, financeiro.

### chamados_internos (3)

- `abrir_chamado_jira`: escrita com confirmação; integração jira; nível N1; áreas todas.
- `comentar_chamado_jira`: escrita com confirmação; integração jira; nível N1; áreas todas.
- `consultar_chamado_jira`: leitura; integração jira; nível N1; áreas todas.

### documentos_e_agenda (9)

- `adicionar_linha_planilha`: escrita com confirmação; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `buscar_arquivos`: leitura; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `criar_evento_agenda`: escrita com confirmação; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `criar_planilha`: escrita com confirmação; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `entregar_arquivo`: escrita; integração anexos; nível N1; áreas todas.
- `ler_arquivo_anexado`: leitura; integração anexos; nível N1; áreas todas.
- `ler_documento`: leitura; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `ler_planilha`: leitura; integração google_workspace, microsoft_365; nível N1; áreas todas.
- `listar_eventos_agenda`: leitura; integração google_workspace, microsoft_365; nível N1; áreas todas.

### financeiro (18)

- `aprovar_acordo`: escrita com confirmação; integração sql; nível N2; áreas financeiro.
- `calcular_multa_atraso`: calculo; integração nenhuma; nível N1; áreas todas.
- `calcular_parcelas`: calculo; integração nenhuma; nível N1; áreas todas.
- `conferir_liquidacoes`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `consultar_agenda_recebiveis`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `consultar_liquidacoes_cliente`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `consultar_saldo_agenda`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `consultar_taxa_contestacao_cliente`: leitura; integração bigquery; nível N1; áreas atendimento, financeiro.
- `consultar_transacoes_cliente`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `executar_antecipacao`: escrita com confirmação; integração crm, sql; nível N2; áreas atendimento, financeiro.
- `listar_acordos`: leitura; integração sql; nível N1; áreas financeiro.
- `listar_contestacoes_cliente`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `listar_faturas_em_atraso`: leitura; integração sql; nível N1; áreas atendimento, financeiro.
- `registrar_acordo`: escrita com confirmação; integração sql; nível N1; áreas financeiro.
- `registrar_defesa_chargeback`: escrita com confirmação; integração sql; nível N1; áreas financeiro.
- `reprocessar_liquidacao`: escrita com confirmação; integração sql; nível N1; áreas financeiro.
- `retirar_acordo`: escrita com confirmação; integração sql; nível N1; áreas financeiro.
- `simular_antecipacao`: calculo; integração sql; nível N1; áreas atendimento, financeiro.

### dados_e_indicadores (8)

- `buscar_conjuntos_dados`: leitura; integração datahub; nível N1; áreas todas.
- `calcular_roi`: calculo; integração nenhuma; nível N1; áreas todas.
- `consultar_esquema_conjunto`: leitura; integração datahub; nível N1; áreas todas.
- `consultar_linhagem_conjunto`: leitura; integração datahub; nível N1; áreas todas.
- `consultar_responsavel_conjunto`: leitura; integração datahub; nível N1; áreas todas.
- `consultar_taxa_contestacao_mensal`: leitura; integração bigquery; nível N2; áreas financeiro.
- `resumir_receita_periodo`: leitura; integração bigquery; nível N1; áreas financeiro.
- `resumir_volume_chamados`: leitura; integração bigquery; nível N2; áreas atendimento.

### comunicacao (4)

- `buscar_emails`: leitura; integração email_leitura; nível N1; áreas atendimento, financeiro.
- `enviar_aviso_telegram`: escrita com confirmação; integração telegram; nível N1; áreas todas.
- `enviar_email`: escrita com confirmação; integração email; nível N1; áreas atendimento, financeiro.
- `enviar_mensagem_slack`: escrita com confirmação; integração slack; nível N1; áreas todas.

### consultas_publicas (2)

- `consultar_cotacao_moeda`: leitura; integração apis_publicas; nível N1; áreas todas.
- `consultar_endereco_cep`: leitura; integração apis_publicas; nível N1; áreas todas.

### plataforma (1)

- `solicitar_ferramenta_ausente`: escrita; integração nenhuma; nível N1; áreas todas.


Quem usa: o agente geral lista todas as que o cargo alcança; o agente de atendimento tem lista fixa de 33. Ficam fora
dele os indicadores gerenciais, o dicionário de dados, os avisos internos (Jira, Slack, Telegram), a conta pessoal
(agenda, planilhas, documentos), as de outro papel (`aprovar_acordo`, `reprocessar_liquidacao`, `retirar_acordo`,
`registrar_defesa_chargeback`) e `listar_meus_chamados`, que aguarda decisão do Christopher e do Isack.

## Como rodar
- Suíte: `python -m pytest backend/tests -q -p no:cacheprovider` (cerca de 4000 testes, 2 minutos). Duas falhas são
  conhecidas e vêm dos e-mails `@stonelab.dev` em `frontend/` (`test_regressao_contrato.py`).
- Lint: `ruff check ferramentas mock agentes backend/tests`. Restam 6 avisos DTZ antigos.
- Integração: `python -m ferramentas.integracoes testar <serviço>` (por exemplo `jira`, `slack`, `telegram`, `email`,
  `google_workspace`, `microsoft_365`, `sql`). Em modo simulado, o teste responde sem rede.
- Mundo do mock: `python -m mock.gerar`; `python -m mock.exportar` regenera `mock/sql/*` (inclui os privilégios de
  escrita de `03_papeis.sh`, que vêm de `PRIVILEGIOS_DE_ESCRITA`).

## O que o Pedro preenche no `.env` (nomes; nunca os valores)
- Modelo: `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`, `LLM_URL`, `LLM_MODELO` (do back-end e do terminal).
- Banco: `MOCK_DATABASE_URL` e `MOCK_ESCRITA_DATABASE_URL` (usuário só com os privilégios de escrita do mock).
- E-mail: `EMAIL_SMTP_*`, `EMAIL_REMETENTE`; leitura: `EMAIL_IMAP_*`.
- Jira: `JIRA_MODO`, `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_PROJETOS`, `JIRA_TIPOS`.
- Slack: `SLACK_TOKEN`, `SLACK_CANAIS`. Telegram: `TELEGRAM_TOKEN`, `TELEGRAM_CHATS`.
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`. Microsoft: `MICROSOFT_CLIENT_ID` e o tenant
  (ver `.env.example`).
- Cada serviço tem um `*_MODO` (`simulado` ou `real`); sem credencial fica simulado.

## O que é real e o que é simulado
- Real: ViaCEP e PTAX do Banco Central (APIs públicas); o SQL do mock (SQLite ou Postgres); a lógica de máscara,
  permissão, confirmação, idempotência e registro.
- Simulado (ou real só com credencial): Jira, Slack, Telegram, e-mail, Google Workspace, Microsoft 365 e anexos. Em
  modo simulado, a mensagem "sai" para uma caixa de saída em memória (`integracoes/simuladas.py`).
- Sintético: todo dado de lojista, funcionário, chamado, acordo e chargeback. "Hoje" é 15/10/2026.

## Dependências de outras frentes (marcadores `[A FAZER (...)]`, de `python -m ferramentas.pendencias`)
- Marcelo e Isabel (back-end): `ferramentas/catalogo.py:175` (rota `GET /ferramentas`), `ferramentas/governanca.py:198`
  (`adicionar_destino` no `lifespan`), `ferramentas/confirmacoes.py:89, 359, 385, 406` (tabela de pedidos, chamada
  depois do turno e rota de confirmação com 409), `ferramentas/integracoes/oauth.py:16` e
  `google_workspace/README.md:50` (rotas de autorizar), `ferramentas/integracoes/credenciais.py:17`
  (`ProvedorNoBanco`), `integracoes/anexos/conector.py:21` (upload), `integracoes/formatos.py:365` (`pypdf` no
  `requirements.txt` do back-end).
- Larissa (interface): `oauth.py:20` e `google_workspace/README.md:54` (conectar conta), `anexos/conector.py:26`
  (anexar), `enviar_email/agents.md:37` (cartão de revisão), `confirmacoes.py:317` (aviso de demonstração).
- Christopher e Isack (agentes): `agentes/agente_atendimento/agente.py:46` (lista vinda da configuração, KAN-55) e
  `enviar_email/agents.md:38` (avisar no `Turno` que há prévia).
- Enrico (QA): `confirmacoes.py:16` (contar pedidos por estado, KAN-38).

## Riscos e perguntas abertas
- Perguntas H1 a H16 em `docs/decisoes.md` (alçada, segregação, 15 funcionários, dupla aprovação acima de R$ 10 mil).
- Contrato da interface (`frontend/CONTRATO_API.md`) sem `confirmacoes[]` e sem as telas do E2 (U5 e U6, em
  `docs/mensagens-para-o-grupo.md`).
- A confirmação pode devolver `EfeitoIncerto` (falha depois do commit): o back-end precisa dizer "pode ter sido feito".
- Pedidos em memória: sem a tabela do back-end, reiniciar o servidor perde as prévias pendentes.
- Os limites (10 passos, 120 s por turno) ainda não foram medidos com o modelo real.
