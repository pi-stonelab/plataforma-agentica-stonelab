-- Mock da Stone (Plataforma Agêntica Institucional). 100% sintético: nenhum dado real.
-- Gerado por `python -m mock.exportar` a partir de mock/modelos.py e mock/gerar.py
-- (semente 20261015, esquema versão 2). Não edite à mão: rode o exportador.

-- times: Times de funcionários. Interno. Carteira vazia: time sem carteira própria.
CREATE TABLE times (
    id INTEGER NOT NULL,
    nome VARCHAR(60) NOT NULL,
    area VARCHAR(20) NOT NULL,
    carteira VARCHAR(20),
    CONSTRAINT pk_times PRIMARY KEY (id),
    CONSTRAINT ck_times_area CHECK (area IN ('atendimento', 'financeiro')),
    CONSTRAINT ck_times_carteira CHECK (carteira IN ('varejo', 'pme', 'contas_chave')),
    CONSTRAINT uq_times_nome UNIQUE (nome)
);

-- funcionarios: Diretório de funcionários (DOC-MOCK §3.3). Interno. Pessoa real de teste tem id F9xxx e nunca entra no SQL exportado.
CREATE TABLE funcionarios (
    id VARCHAR(5) NOT NULL,
    nome VARCHAR(80) NOT NULL,
    email VARCHAR(120) NOT NULL,
    cargo VARCHAR(40) NOT NULL,
    id_time INTEGER,
    situacao VARCHAR(12) NOT NULL,
    pessoa_real_teste BOOLEAN NOT NULL,
    CONSTRAINT pk_funcionarios PRIMARY KEY (id),
    CONSTRAINT ck_funcionarios_situacao CHECK (situacao IN ('ativo', 'afastado', 'desligado')),
    CONSTRAINT ck_funcionarios_cargo CHECK (cargo IN ('atendente_n1', 'especialista_n2', 'supervisor_atendimento', 'analista_ouvidoria', 'analista_cobranca', 'analista_disputas', 'analista_recebiveis', 'coordenador_financeiro', 'auditor_compliance', 'admin_plataforma')),
    CONSTRAINT ck_funcionarios_id_formato CHECK (id LIKE 'F____'),
    CONSTRAINT fk_funcionarios_id_time FOREIGN KEY(id_time) REFERENCES times (id)
);
CREATE INDEX ix_funcionarios_id_time ON funcionarios (id_time);

-- lojistas: Cadastro do lojista. Público ou interno; a carteira decide quem do atendimento vê.
CREATE TABLE lojistas (
    codigo VARCHAR(6) NOT NULL,
    nome_fantasia VARCHAR(80) NOT NULL,
    segmento VARCHAR(30) NOT NULL,
    porte VARCHAR(5) NOT NULL,
    cidade VARCHAR(60) NOT NULL,
    uf VARCHAR(2) NOT NULL,
    carteira VARCHAR(20) NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    data_entrada DATE NOT NULL,
    id_responsavel VARCHAR(5),
    CONSTRAINT pk_lojistas PRIMARY KEY (codigo),
    CONSTRAINT ck_lojistas_situacao CHECK (situacao IN ('ativo', 'inativo', 'bloqueado', 'encerrado')),
    CONSTRAINT ck_lojistas_porte CHECK (porte IN ('MEI', 'ME', 'EPP', 'media')),
    CONSTRAINT ck_lojistas_carteira CHECK (carteira IN ('varejo', 'pme', 'contas_chave')),
    CONSTRAINT ck_lojistas_codigo_formato CHECK (codigo LIKE 'M_____'),
    CONSTRAINT ck_lojistas_uf_formato CHECK (length(uf) = 2),
    CONSTRAINT fk_lojistas_id_responsavel FOREIGN KEY(id_responsavel) REFERENCES funcionarios (id)
);

-- contas_recebimento: Conta onde caem as liquidações, uma por lojista. RESTRITO: agência e conta.
CREATE TABLE contas_recebimento (
    id INTEGER NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    banco VARCHAR(40) NOT NULL,
    agencia VARCHAR(10) NOT NULL,
    conta VARCHAR(15) NOT NULL,
    situacao VARCHAR(15) NOT NULL,
    CONSTRAINT pk_contas_recebimento PRIMARY KEY (id),
    CONSTRAINT ck_contas_recebimento_situacao CHECK (situacao IN ('ativa', 'em_verificacao', 'invalida')),
    CONSTRAINT uq_contas_recebimento_id_lojista UNIQUE (id_lojista),
    CONSTRAINT fk_contas_recebimento_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);

-- contatos_lojista: Pessoas de contato do lojista. RESTRITO: nome, CPF, telefone e e-mail saem mascarados.
CREATE TABLE contatos_lojista (
    id INTEGER NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    nome VARCHAR(80) NOT NULL,
    cpf VARCHAR(14) NOT NULL,
    papel VARCHAR(20) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    CONSTRAINT pk_contatos_lojista PRIMARY KEY (id),
    CONSTRAINT ck_contatos_lojista_papel CHECK (papel IN ('socio', 'financeiro', 'operador_caixa')),
    CONSTRAINT fk_contatos_lojista_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
CREATE INDEX ix_contatos_lojista_id_lojista ON contatos_lojista (id_lojista);

-- faturas: O que o lojista deve à Stone (aluguel, tarifa ou saldo negativo). Confidencial.
CREATE TABLE faturas (
    codigo VARCHAR(7) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    tipo VARCHAR(15) NOT NULL,
    mes_referencia VARCHAR(7) NOT NULL,
    vencimento DATE NOT NULL,
    valor_centavos BIGINT NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    CONSTRAINT pk_faturas PRIMARY KEY (codigo),
    CONSTRAINT ck_faturas_tipo CHECK (tipo IN ('aluguel', 'tarifa', 'saldo_negativo')),
    CONSTRAINT ck_faturas_situacao CHECK (situacao IN ('aberta', 'paga', 'vencida', 'em_acordo', 'cancelada')),
    CONSTRAINT ck_faturas_codigo_formato CHECK (codigo LIKE 'I______'),
    CONSTRAINT ck_faturas_mes_referencia_formato CHECK (mes_referencia LIKE '____-__'),
    CONSTRAINT ck_faturas_valor_positivo CHECK (valor_centavos > 0),
    CONSTRAINT fk_faturas_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
CREATE INDEX ix_faturas_id_lojista_vencimento ON faturas (id_lojista, vencimento);

-- liquidacoes: Depósito diário ao lojista (recebíveis do dia menos descontos). Confidencial.
CREATE TABLE liquidacoes (
    id INTEGER NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    data DATE NOT NULL,
    valor_total_centavos BIGINT NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    motivo_falha VARCHAR(30),
    CONSTRAINT pk_liquidacoes PRIMARY KEY (id),
    CONSTRAINT ck_liquidacoes_situacao CHECK (situacao IN ('paga', 'falhou', 'devolvida')),
    CONSTRAINT ck_liquidacoes_valor_nao_negativo CHECK (valor_total_centavos >= 0),
    CONSTRAINT ck_liquidacoes_motivo_so_quando_falha CHECK ((situacao = 'paga' AND motivo_falha IS NULL) OR (situacao <> 'paga' AND motivo_falha IS NOT NULL)),
    CONSTRAINT fk_liquidacoes_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
CREATE INDEX ix_liquidacoes_id_lojista_data ON liquidacoes (id_lojista, data);

-- vendas: Vendas no cartão ou Pix. Nunca o número do cartão: só bandeira e 4 últimos dígitos.
CREATE TABLE vendas (
    codigo VARCHAR(8) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    data_hora DATETIME NOT NULL,
    modalidade VARCHAR(20) NOT NULL,
    parcelas INTEGER NOT NULL,
    bandeira VARCHAR(15),
    ultimos4 VARCHAR(4),
    valor_bruto_centavos BIGINT NOT NULL,
    valor_liquido_centavos BIGINT NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    CONSTRAINT pk_vendas PRIMARY KEY (codigo),
    CONSTRAINT ck_vendas_modalidade CHECK (modalidade IN ('debito', 'credito_a_vista', 'parcelado', 'pix')),
    CONSTRAINT ck_vendas_situacao CHECK (situacao IN ('aprovada', 'negada', 'cancelada')),
    CONSTRAINT ck_vendas_bandeira CHECK (bandeira IN ('visa', 'mastercard', 'elo')),
    CONSTRAINT ck_vendas_codigo_formato CHECK (codigo LIKE 'T_______'),
    CONSTRAINT ck_vendas_ultimos4_formato CHECK (ultimos4 IS NULL OR length(ultimos4) = 4),
    CONSTRAINT ck_vendas_cartao_conforme_modalidade CHECK ((modalidade = 'pix' AND bandeira IS NULL AND ultimos4 IS NULL) OR (modalidade <> 'pix' AND bandeira IS NOT NULL AND ultimos4 IS NOT NULL)),
    CONSTRAINT ck_vendas_parcelas_conforme_modalidade CHECK ((modalidade = 'parcelado' AND parcelas BETWEEN 2 AND 12) OR (modalidade <> 'parcelado' AND parcelas = 1)),
    CONSTRAINT ck_vendas_valor_bruto_positivo CHECK (valor_bruto_centavos > 0),
    CONSTRAINT ck_vendas_valor_liquido_ate_o_bruto CHECK (valor_liquido_centavos BETWEEN 0 AND valor_bruto_centavos),
    CONSTRAINT ck_vendas_sem_liquido_se_nao_aprovada CHECK (situacao = 'aprovada' OR valor_liquido_centavos = 0),
    CONSTRAINT fk_vendas_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
CREATE INDEX ix_vendas_id_lojista_data_hora ON vendas (id_lojista, data_hora);

-- chamados: Chamados do CRM. RESTRITO: o resumo é texto livre e sai mascarado.
CREATE TABLE chamados (
    codigo VARCHAR(8) NOT NULL,
    protocolo VARCHAR(15) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    prioridade VARCHAR(10) NOT NULL,
    fila VARCHAR(20) NOT NULL,
    id_responsavel VARCHAR(5),
    situacao VARCHAR(25) NOT NULL,
    aberto_por VARCHAR(12) NOT NULL,
    aberto_em DATETIME NOT NULL,
    resumo TEXT NOT NULL,
    id_liquidacao INTEGER,
    id_fatura VARCHAR(7),
    CONSTRAINT pk_chamados PRIMARY KEY (codigo),
    CONSTRAINT ck_chamados_categoria CHECK (categoria IN ('Dúvida de produto', 'Recebimento', 'Maquininha', 'Fatura e aluguel', 'Antecipação', 'Alteração cadastral', 'Contestação')),
    CONSTRAINT ck_chamados_prioridade CHECK (prioridade IN ('baixa', 'média', 'alta')),
    CONSTRAINT ck_chamados_fila CHECK (fila IN ('varejo', 'pme', 'contas_chave')),
    CONSTRAINT ck_chamados_situacao CHECK (situacao IN ('novo', 'em_atendimento', 'aguardando_lojista', 'resolvido', 'fechado')),
    CONSTRAINT ck_chamados_aberto_por CHECK (aberto_por IN ('sistema', 'lojista', 'funcionario')),
    CONSTRAINT ck_chamados_codigo_formato CHECK (codigo LIKE 'CH______'),
    CONSTRAINT ck_chamados_protocolo_formato CHECK (protocolo LIKE '________-______'),
    CONSTRAINT uq_chamados_protocolo UNIQUE (protocolo),
    CONSTRAINT fk_chamados_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_chamados_id_responsavel FOREIGN KEY(id_responsavel) REFERENCES funcionarios (id),
    CONSTRAINT fk_chamados_id_liquidacao FOREIGN KEY(id_liquidacao) REFERENCES liquidacoes (id),
    CONSTRAINT fk_chamados_id_fatura FOREIGN KEY(id_fatura) REFERENCES faturas (codigo)
);
CREATE INDEX ix_chamados_id_lojista_aberto_em ON chamados (id_lojista, aberto_em);

-- interacoes: Mensagens dos chamados. RESTRITO: texto livre, por onde chegaria uma injeção de comando.
CREATE TABLE interacoes (
    id INTEGER NOT NULL,
    id_chamado VARCHAR(8) NOT NULL,
    autor VARCHAR(12) NOT NULL,
    canal VARCHAR(15) NOT NULL,
    data_hora DATETIME NOT NULL,
    texto TEXT NOT NULL,
    teste_seguranca BOOLEAN NOT NULL,
    comportamento_esperado TEXT,
    CONSTRAINT pk_interacoes PRIMARY KEY (id),
    CONSTRAINT ck_interacoes_autor CHECK (autor IN ('lojista', 'funcionario', 'agente')),
    CONSTRAINT ck_interacoes_canal CHECK (canal IN ('whatsapp', 'telefone', 'chat', 'email')),
    CONSTRAINT fk_interacoes_id_chamado FOREIGN KEY(id_chamado) REFERENCES chamados (codigo)
);
CREATE INDEX ix_interacoes_id_chamado_data_hora ON interacoes (id_chamado, data_hora);

PRAGMA user_version = 2;
