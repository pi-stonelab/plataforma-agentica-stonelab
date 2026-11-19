// Gerado por frontend/scripts/gerar_catalogo_mock.py. Não editar à mão.
export const CATALOGO = [
  {
    "nome": "abrir_chamado_jira",
    "area": "chamados_internos",
    "descricao": "Abre um chamado no Jira.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "jira"
    ]
  },
  {
    "nome": "abrir_ticket",
    "area": "atendimento",
    "descricao": "Abre um ticket para um cliente.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "adicionar_linha_planilha",
    "area": "documentos_e_agenda",
    "descricao": "Acrescenta uma linha a uma planilha.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "adicionar_nota_ticket",
    "area": "atendimento",
    "descricao": "Acrescenta uma nota interna a um ticket.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "atualizar_status_ticket",
    "area": "atendimento",
    "descricao": "Muda o status de um ticket.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "buscar_arquivos",
    "area": "documentos_e_agenda",
    "descricao": "Procura arquivos pelo nome ou conteúdo.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "buscar_clientes",
    "area": "atendimento",
    "descricao": "Busca clientes por um critério, como nome ou documento.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "buscar_conjuntos_dados",
    "area": "dados_e_indicadores",
    "descricao": "Procura conjuntos de dados pelo nome ou assunto.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "datahub"
    ]
  },
  {
    "nome": "buscar_emails",
    "area": "comunicacao",
    "descricao": "Procura e-mails do usuário.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "calcular_multa_atraso",
    "area": "financeiro",
    "descricao": "Calcula a multa, os juros e o valor total de uma fatura paga com atraso.",
    "acesso": "calculo",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "publica",
    "status": "ativa",
    "integracoes": []
  },
  {
    "nome": "calcular_parcelas",
    "area": "financeiro",
    "descricao": "Valor das parcelas de um valor financiado.",
    "acesso": "calculo",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "publica",
    "status": "planejada",
    "integracoes": []
  },
  {
    "nome": "calcular_roi",
    "area": "dados_e_indicadores",
    "descricao": "Retorno sobre investimento a partir de custo e ganho.",
    "acesso": "calculo",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "publica",
    "status": "planejada",
    "integracoes": []
  },
  {
    "nome": "comentar_chamado_jira",
    "area": "chamados_internos",
    "descricao": "Comenta em um chamado do Jira.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "jira"
    ]
  },
  {
    "nome": "consultar_chamado_jira",
    "area": "chamados_internos",
    "descricao": "Detalhe de um chamado no Jira.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "jira"
    ]
  },
  {
    "nome": "consultar_cliente",
    "area": "atendimento",
    "descricao": "Devolve os dados cadastrais de um cliente a partir do id_cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "ativa",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "consultar_cotacao_moeda",
    "area": "consultas_publicas",
    "descricao": "Cotação de uma moeda.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "publica",
    "status": "planejada",
    "integracoes": [
      "apis_publicas"
    ]
  },
  {
    "nome": "consultar_endereco_cep",
    "area": "consultas_publicas",
    "descricao": "Devolve o endereço público de um CEP: logradouro, bairro, cidade e UF.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "publica",
    "status": "ativa",
    "integracoes": [
      "apis_publicas"
    ]
  },
  {
    "nome": "consultar_esquema_conjunto",
    "area": "dados_e_indicadores",
    "descricao": "Colunas e tipos de um conjunto de dados.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "datahub"
    ]
  },
  {
    "nome": "consultar_historico_contato",
    "area": "atendimento",
    "descricao": "Histórico de contatos com um cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "consultar_linhagem_conjunto",
    "area": "dados_e_indicadores",
    "descricao": "De onde vem um conjunto de dados.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "datahub"
    ]
  },
  {
    "nome": "consultar_responsavel_conjunto",
    "area": "dados_e_indicadores",
    "descricao": "Quem responde por um conjunto de dados.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "datahub"
    ]
  },
  {
    "nome": "consultar_saldo_conta",
    "area": "financeiro",
    "descricao": "Saldo da conta de um cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N2",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "sigilosa",
    "status": "planejada",
    "integracoes": [
      "sql"
    ]
  },
  {
    "nome": "consultar_taxa_contestacao_mensal",
    "area": "dados_e_indicadores",
    "descricao": "Taxa de contestação por mês.",
    "acesso": "leitura",
    "nivel_minimo": "N2",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "bigquery"
    ]
  },
  {
    "nome": "consultar_ticket",
    "area": "atendimento",
    "descricao": "Detalhe de um ticket.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "consultar_transacoes_cliente",
    "area": "financeiro",
    "descricao": "Lista as transações mais recentes de um cliente, com filtro opcional por período.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "sigilosa",
    "status": "ativa",
    "integracoes": [
      "sql"
    ]
  },
  {
    "nome": "criar_evento_agenda",
    "area": "documentos_e_agenda",
    "descricao": "Cria um evento na agenda do usuário.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "criar_planilha",
    "area": "documentos_e_agenda",
    "descricao": "Cria uma planilha nova.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "entregar_arquivo",
    "area": "documentos_e_agenda",
    "descricao": "Entrega um arquivo gerado ao usuário no chat.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "anexos"
    ]
  },
  {
    "nome": "enviar_aviso_telegram",
    "area": "comunicacao",
    "descricao": "Envia um aviso curto por Telegram.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "telegram"
    ]
  },
  {
    "nome": "enviar_email",
    "area": "comunicacao",
    "descricao": "Envia um e-mail depois da confirmação do usuário.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "enviar_mensagem_slack",
    "area": "comunicacao",
    "descricao": "Envia uma mensagem para um canal ou pessoa.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "slack"
    ]
  },
  {
    "nome": "ler_arquivo_anexado",
    "area": "documentos_e_agenda",
    "descricao": "Lê um arquivo que o usuário anexou no chat.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "anexos"
    ]
  },
  {
    "nome": "ler_documento",
    "area": "documentos_e_agenda",
    "descricao": "Lê o texto de um documento.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "ler_planilha",
    "area": "documentos_e_agenda",
    "descricao": "Lê um intervalo de uma planilha.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "listar_contestacoes_cliente",
    "area": "financeiro",
    "descricao": "Contestações abertas por um cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "sigilosa",
    "status": "planejada",
    "integracoes": [
      "sql"
    ]
  },
  {
    "nome": "listar_eventos_agenda",
    "area": "documentos_e_agenda",
    "descricao": "Eventos da agenda do usuário em um período.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "google_workspace",
      "microsoft_365"
    ]
  },
  {
    "nome": "listar_faturas_em_atraso",
    "area": "financeiro",
    "descricao": "Faturas em atraso de um cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "sigilosa",
    "status": "planejada",
    "integracoes": [
      "sql"
    ]
  },
  {
    "nome": "listar_tickets_cliente",
    "area": "atendimento",
    "descricao": "Tickets de atendimento de um cliente.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "atendimento",
      "financeiro"
    ],
    "sensibilidade": "pessoal",
    "status": "planejada",
    "integracoes": [
      "crm"
    ]
  },
  {
    "nome": "resumir_receita_periodo",
    "area": "dados_e_indicadores",
    "descricao": "Receita total de um período.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "bigquery"
    ]
  },
  {
    "nome": "resumir_volume_tickets",
    "area": "dados_e_indicadores",
    "descricao": "Quantidade de tickets por período.",
    "acesso": "leitura",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "dados",
      "financeiro"
    ],
    "sensibilidade": "interna",
    "status": "planejada",
    "integracoes": [
      "bigquery"
    ]
  },
  {
    "nome": "solicitar_ferramenta_ausente",
    "area": "plataforma",
    "descricao": "Registra o pedido de uma ferramenta que a plataforma ainda não tem.",
    "acesso": "escrita",
    "nivel_minimo": "N1",
    "areas_permitidas": [
      "todas"
    ],
    "sensibilidade": "interna",
    "status": "ativa",
    "integracoes": []
  }
];
