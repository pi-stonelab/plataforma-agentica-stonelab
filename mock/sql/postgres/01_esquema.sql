-- Mock da Stone (Plataforma Agêntica Institucional). 100% sintético: nenhum dado real.
-- Gerado por `python -m mock.exportar` a partir de mock/modelos.py e mock/gerar.py
-- (semente 20261015, esquema versão 4). Não edite à mão: rode o exportador.

CREATE TABLE analitica_atualizacao (
    id INTEGER NOT NULL,
    data_corte DATE NOT NULL,
    CONSTRAINT pk_analitica_atualizacao PRIMARY KEY (id),
    CONSTRAINT ck_analitica_atualizacao_uma_linha CHECK (id = 1)
);
COMMENT ON TABLE analitica_atualizacao IS 'Quando a base analítica foi copiada e até que dia ela vai. Interno.';

CREATE TABLE analitica_chamados_diarios (
    dia DATE NOT NULL,
    fila VARCHAR(20) NOT NULL,
    prioridade VARCHAR(10) NOT NULL,
    quantidade_abertos INTEGER NOT NULL,
    quantidade_resolvidos INTEGER NOT NULL,
    quantidade_estourados INTEGER NOT NULL,
    CONSTRAINT pk_analitica_chamados_diarios PRIMARY KEY (dia, fila, prioridade),
    CONSTRAINT ck_analitica_chamados_diarios_fila CHECK (fila IN ('varejo', 'pme', 'contas_chave', 'ouvidoria')),
    CONSTRAINT ck_analitica_chamados_diarios_prioridade CHECK (prioridade IN ('baixa', 'média', 'alta', 'crítica'))
);
COMMENT ON TABLE analitica_chamados_diarios IS 'Chamados por dia de abertura, fila e prioridade, com quantos estouraram o prazo do SLA até o corte. Agregado e interno.';

CREATE TABLE analitica_vendas_diarias (
    dia DATE NOT NULL,
    modalidade VARCHAR(20) NOT NULL,
    quantidade_aprovadas INTEGER NOT NULL,
    quantidade_negadas INTEGER NOT NULL,
    valor_bruto_dia_centavos BIGINT NOT NULL,
    valor_liquido_dia_centavos BIGINT NOT NULL,
    receita_mdr_dia_centavos BIGINT NOT NULL,
    CONSTRAINT pk_analitica_vendas_diarias PRIMARY KEY (dia, modalidade),
    CONSTRAINT ck_analitica_vendas_diarias_modalidade CHECK (modalidade IN ('debito', 'credito_a_vista', 'parcelado', 'pix'))
);
COMMENT ON TABLE analitica_vendas_diarias IS 'Vendas por dia e modalidade, até o dia de corte. Agregado e confidencial.';
COMMENT ON COLUMN analitica_vendas_diarias.quantidade_negadas IS 'Negadas e canceladas.';
COMMENT ON COLUMN analitica_vendas_diarias.receita_mdr_dia_centavos IS 'Bruto menos líquido: a receita de MDR.';

CREATE TABLE artigos_ajuda (
    codigo VARCHAR(5) NOT NULL,
    titulo_artigo VARCHAR(120) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    texto_artigo TEXT NOT NULL,
    termos_de_busca TEXT NOT NULL,
    atualizado_em DATE NOT NULL,
    CONSTRAINT pk_artigos_ajuda PRIMARY KEY (codigo),
    CONSTRAINT ck_artigos_ajuda_categoria CHECK (categoria IN ('Recebimento', 'Antecipação', 'Fatura e aluguel', 'Contestação', 'Pix e devolução', 'Alteração cadastral', 'Taxas e planos', 'Atendimento', 'Maquininha')),
    CONSTRAINT ck_artigos_ajuda_codigo_formato CHECK (codigo LIKE 'KB___')
);
COMMENT ON TABLE artigos_ajuda IS 'Base de conhecimento do atendimento: artigos públicos escritos pela equipe a partir das regras do DOC-MOCK. Público.';
COMMENT ON COLUMN artigos_ajuda.termos_de_busca IS 'Título, categoria, texto e sinônimos sem acento e em minúsculas, para a busca por palavra.';

CREATE TABLE times (
    id SERIAL NOT NULL,
    nome VARCHAR(60) NOT NULL,
    area VARCHAR(20) NOT NULL,
    carteira VARCHAR(20),
    CONSTRAINT pk_times PRIMARY KEY (id),
    CONSTRAINT ck_times_area CHECK (area IN ('atendimento', 'financeiro')),
    CONSTRAINT ck_times_carteira CHECK (carteira IN ('varejo', 'pme', 'contas_chave')),
    CONSTRAINT uq_times_nome UNIQUE (nome)
);
COMMENT ON TABLE times IS 'Times de funcionários. Interno. Carteira vazia: time sem carteira própria.';

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
COMMENT ON TABLE funcionarios IS 'Diretório de funcionários (DOC-MOCK §3.3). Interno. Pessoa real de teste tem id F9xxx e nunca entra no SQL exportado.';
COMMENT ON COLUMN funcionarios.nome IS 'Dado pessoal. Nenhuma ferramenta devolve.';
COMMENT ON COLUMN funcionarios.email IS 'Dado pessoal. Nenhuma ferramenta devolve.';
COMMENT ON COLUMN funcionarios.cargo IS 'Decide nível, área e categorias de dado.';

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
COMMENT ON TABLE lojistas IS 'Cadastro do lojista. Público ou interno; a carteira decide quem do atendimento vê.';
COMMENT ON COLUMN lojistas.carteira IS 'Escopo do atendimento.';
COMMENT ON COLUMN lojistas.id_responsavel IS 'Especialista N2 das contas-chave.';

CREATE TABLE acordos (
    codigo VARCHAR(6) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    valor_original_centavos BIGINT NOT NULL,
    valor_renegociado_centavos BIGINT NOT NULL,
    entrada_centavos BIGINT NOT NULL,
    numero_de_parcelas INTEGER NOT NULL,
    perdao_encargos_centavos BIGINT NOT NULL,
    desconto_principal_centavos BIGINT NOT NULL,
    alcada VARCHAR(20) NOT NULL,
    id_solicitante VARCHAR(5) NOT NULL,
    id_aprovador VARCHAR(5),
    criado_em DATE NOT NULL,
    situacao VARCHAR(20) NOT NULL,
    CONSTRAINT pk_acordos PRIMARY KEY (codigo),
    CONSTRAINT ck_acordos_situacao CHECK (situacao IN ('pendente_aprovacao', 'ativo', 'quitado', 'quebrado', 'recusado')),
    CONSTRAINT ck_acordos_alcada CHECK (alcada IN ('analista', 'coordenador', 'dupla_aprovacao', 'proibido')),
    CONSTRAINT ck_acordos_codigo_formato CHECK (codigo LIKE 'AC____'),
    CONSTRAINT ck_acordos_parcelas_validas CHECK (numero_de_parcelas BETWEEN 1 AND 12),
    CONSTRAINT ck_acordos_entrada_ate_o_valor CHECK (entrada_centavos BETWEEN 0 AND valor_renegociado_centavos),
    CONSTRAINT ck_acordos_descontos_nao_negativos CHECK (desconto_principal_centavos >= 0 AND perdao_encargos_centavos >= 0),
    CONSTRAINT ck_acordos_aprovador_conforme_situacao CHECK ((situacao IN ('pendente_aprovacao', 'recusado') AND id_aprovador IS NULL) OR (situacao NOT IN ('pendente_aprovacao', 'recusado') AND id_aprovador IS NOT NULL)),
    CONSTRAINT ck_acordos_dupla_aprovacao_por_outra_pessoa CHECK (alcada <> 'dupla_aprovacao' OR id_aprovador IS NULL OR id_aprovador <> id_solicitante),
    CONSTRAINT fk_acordos_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_acordos_id_solicitante FOREIGN KEY(id_solicitante) REFERENCES funcionarios (id),
    CONSTRAINT fk_acordos_id_aprovador FOREIGN KEY(id_aprovador) REFERENCES funcionarios (id)
);
CREATE INDEX ix_acordos_id_lojista ON acordos (id_lojista);
CREATE INDEX ix_acordos_situacao ON acordos (situacao);
COMMENT ON TABLE acordos IS 'Acordos de renegociação da Cobrança (DOC-MOCK §7.9). A alçada diz quem aprova. Confidencial.';
COMMENT ON COLUMN acordos.valor_original_centavos IS 'Soma das faturas incluídas.';
COMMENT ON COLUMN acordos.valor_renegociado_centavos IS 'Faturas mais multa e juros até a criação, menos o perdão e o desconto.';
COMMENT ON COLUMN acordos.perdao_encargos_centavos IS 'Multa e juros perdoados: o analista perdoa em dívida de até R$ 2.000 (§7.9).';
COMMENT ON COLUMN acordos.desconto_principal_centavos IS 'Desconto no principal: só o coordenador, até 10% do principal (§7.9).';

CREATE TABLE analitica_contestacoes_mensais (
    mes VARCHAR(7) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    quantidade_vendas_cartao INTEGER NOT NULL,
    quantidade_chargebacks INTEGER NOT NULL,
    CONSTRAINT pk_analitica_contestacoes_mensais PRIMARY KEY (mes, id_lojista),
    CONSTRAINT ck_analitica_contestacoes_mensais_mes_formato CHECK (mes LIKE '____-__'),
    CONSTRAINT fk_analitica_contestacoes_mensais_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
COMMENT ON TABLE analitica_contestacoes_mensais IS 'Vendas no cartão e chargebacks (no mês da venda contestada) por mês e lojista, até o corte (DOC-MOCK §7.6: mais de 1% liga o monitoramento de risco). Agregado e confidencial.';

CREATE TABLE contas_recebimento (
    id SERIAL NOT NULL,
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
COMMENT ON TABLE contas_recebimento IS 'Conta onde caem as liquidações, uma por lojista. RESTRITO: agência e conta.';
COMMENT ON COLUMN contas_recebimento.agencia IS 'RESTRITO (conta).';
COMMENT ON COLUMN contas_recebimento.conta IS 'RESTRITO (conta).';

CREATE TABLE contatos_lojista (
    id SERIAL NOT NULL,
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
COMMENT ON TABLE contatos_lojista IS 'Pessoas de contato do lojista. RESTRITO: nome, CPF, telefone e e-mail saem mascarados.';
COMMENT ON COLUMN contatos_lojista.nome IS 'RESTRITO (nome).';
COMMENT ON COLUMN contatos_lojista.cpf IS 'RESTRITO (cpf).';
COMMENT ON COLUMN contatos_lojista.telefone IS 'RESTRITO (telefone).';
COMMENT ON COLUMN contatos_lojista.email IS 'RESTRITO (email).';

CREATE TABLE liquidacoes (
    id SERIAL NOT NULL,
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
COMMENT ON TABLE liquidacoes IS 'Depósito diário ao lojista (recebíveis do dia menos descontos). Confidencial.';

CREATE TABLE vendas (
    codigo VARCHAR(8) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    data_hora TIMESTAMP WITHOUT TIME ZONE NOT NULL,
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
COMMENT ON TABLE vendas IS 'Vendas no cartão ou Pix. Nunca o número do cartão: só bandeira e 4 últimos dígitos.';
COMMENT ON COLUMN vendas.ultimos4 IS 'RESTRITO (cartao).';

CREATE TABLE casos_pix (
    codigo VARCHAR(7) NOT NULL,
    id_venda VARCHAR(8) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    data_abertura DATE NOT NULL,
    prazo_contestacao DATE NOT NULL,
    valor_bloqueado_centavos BIGINT NOT NULL,
    motivo_alegado VARCHAR(40) NOT NULL,
    tem_comprovante_entrega BOOLEAN NOT NULL,
    id_analista VARCHAR(5),
    situacao VARCHAR(15) NOT NULL,
    CONSTRAINT pk_casos_pix PRIMARY KEY (codigo),
    CONSTRAINT ck_casos_pix_situacao CHECK (situacao IN ('bloqueado', 'contestado', 'devolvido', 'liberado')),
    CONSTRAINT ck_casos_pix_codigo_formato CHECK (codigo LIKE 'PX_____'),
    CONSTRAINT ck_casos_pix_motivo_alegado CHECK (motivo_alegado IN ('golpe_produto_nao_entregue', 'fraude_conta_invadida')),
    CONSTRAINT ck_casos_pix_valor_positivo CHECK (valor_bloqueado_centavos > 0),
    CONSTRAINT ck_casos_pix_prazo_depois_da_abertura CHECK (prazo_contestacao > data_abertura),
    CONSTRAINT uq_casos_pix_id_venda UNIQUE (id_venda),
    CONSTRAINT fk_casos_pix_id_venda FOREIGN KEY(id_venda) REFERENCES vendas (codigo),
    CONSTRAINT fk_casos_pix_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_casos_pix_id_analista FOREIGN KEY(id_analista) REFERENCES funcionarios (id)
);
CREATE INDEX ix_casos_pix_id_lojista_data_abertura ON casos_pix (id_lojista, data_abertura);
COMMENT ON TABLE casos_pix IS 'Pedidos de devolução de Pix pelo MED do Banco Central (DOC-MOCK §7.7). Confidencial.';
COMMENT ON COLUMN casos_pix.motivo_alegado IS 'O que quem pagou alegou (regras.MOTIVOS_DO_MED).';

CREATE TABLE chargebacks (
    codigo VARCHAR(7) NOT NULL,
    id_venda VARCHAR(8) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    motivo VARCHAR(40) NOT NULL,
    data_notificacao DATE NOT NULL,
    prazo_defesa DATE NOT NULL,
    valor_contestado_centavos BIGINT NOT NULL,
    documentos_enviados VARCHAR(200) NOT NULL,
    id_analista VARCHAR(5),
    situacao VARCHAR(20) NOT NULL,
    CONSTRAINT pk_chargebacks PRIMARY KEY (codigo),
    CONSTRAINT ck_chargebacks_situacao CHECK (situacao IN ('aguardando_defesa', 'em_analise', 'reapresentado', 'aceito', 'ganho', 'perdido')),
    CONSTRAINT ck_chargebacks_motivo CHECK (motivo IN ('compra_nao_reconhecida', 'mercadoria_nao_recebida', 'produto_diferente', 'cobranca_duplicada', 'valor_divergente', 'cancelamento_nao_processado')),
    CONSTRAINT ck_chargebacks_codigo_formato CHECK (codigo LIKE 'CB_____'),
    CONSTRAINT ck_chargebacks_valor_positivo CHECK (valor_contestado_centavos > 0),
    CONSTRAINT ck_chargebacks_prazo_depois_do_aviso CHECK (prazo_defesa > data_notificacao),
    CONSTRAINT uq_chargebacks_id_venda UNIQUE (id_venda),
    CONSTRAINT fk_chargebacks_id_venda FOREIGN KEY(id_venda) REFERENCES vendas (codigo),
    CONSTRAINT fk_chargebacks_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_chargebacks_id_analista FOREIGN KEY(id_analista) REFERENCES funcionarios (id)
);
CREATE INDEX ix_chargebacks_id_lojista_data_notificacao ON chargebacks (id_lojista, data_notificacao);
COMMENT ON TABLE chargebacks IS 'Chargebacks do sistema de Disputas (DOC-MOCK §7.6). O valor fica retido na agenda enquanto o caso corre. Confidencial.';
COMMENT ON COLUMN chargebacks.documentos_enviados IS 'Documentos já enviados, separados por vírgula (regras.ROTULOS_DOS_DOCUMENTOS).';

CREATE TABLE faturas (
    codigo VARCHAR(7) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    tipo VARCHAR(15) NOT NULL,
    mes_referencia VARCHAR(7) NOT NULL,
    vencimento DATE NOT NULL,
    valor_centavos BIGINT NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    id_acordo VARCHAR(6),
    CONSTRAINT pk_faturas PRIMARY KEY (codigo),
    CONSTRAINT ck_faturas_tipo CHECK (tipo IN ('aluguel', 'tarifa', 'saldo_negativo')),
    CONSTRAINT ck_faturas_situacao CHECK (situacao IN ('aberta', 'paga', 'vencida', 'em_acordo', 'cancelada')),
    CONSTRAINT ck_faturas_codigo_formato CHECK (codigo LIKE 'I______'),
    CONSTRAINT ck_faturas_mes_referencia_formato CHECK (mes_referencia LIKE '____-__'),
    CONSTRAINT ck_faturas_valor_positivo CHECK (valor_centavos > 0),
    CONSTRAINT ck_faturas_acordo_conforme_situacao CHECK ((situacao = 'em_acordo' AND id_acordo IS NOT NULL) OR (situacao <> 'em_acordo' AND (id_acordo IS NULL OR situacao = 'vencida'))),
    CONSTRAINT fk_faturas_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_faturas_id_acordo FOREIGN KEY(id_acordo) REFERENCES acordos (codigo)
);
CREATE INDEX ix_faturas_id_lojista_vencimento ON faturas (id_lojista, vencimento);
COMMENT ON TABLE faturas IS 'O que o lojista deve à Stone (aluguel, tarifa ou saldo negativo). Confidencial.';

CREATE TABLE recebiveis (
    codigo VARCHAR(8) NOT NULL,
    id_venda VARCHAR(8) NOT NULL,
    id_lojista VARCHAR(6) NOT NULL,
    numero_parcela INTEGER NOT NULL,
    data_prevista DATE NOT NULL,
    valor_parcela_centavos BIGINT NOT NULL,
    situacao VARCHAR(12) NOT NULL,
    CONSTRAINT pk_recebiveis PRIMARY KEY (codigo),
    CONSTRAINT ck_recebiveis_situacao CHECK (situacao IN ('previsto', 'pago', 'retido', 'bloqueado', 'antecipado')),
    CONSTRAINT ck_recebiveis_codigo_formato CHECK (codigo LIKE 'R_______'),
    CONSTRAINT ck_recebiveis_parcela_valida CHECK (numero_parcela BETWEEN 1 AND 12),
    CONSTRAINT ck_recebiveis_valor_positivo CHECK (valor_parcela_centavos > 0),
    CONSTRAINT fk_recebiveis_id_venda FOREIGN KEY(id_venda) REFERENCES vendas (codigo),
    CONSTRAINT fk_recebiveis_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo)
);
CREATE INDEX ix_recebiveis_id_lojista_data_prevista ON recebiveis (id_lojista, data_prevista);
CREATE INDEX ix_recebiveis_id_venda ON recebiveis (id_venda);
COMMENT ON TABLE recebiveis IS 'Agenda de recebíveis (DOC-MOCK §7.2): quanto cai e quando, por parcela de venda aprovada. Pix não entra. Confidencial.';

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
    aberto_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    prazo_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    resolvido_em TIMESTAMP WITHOUT TIME ZONE,
    resumo TEXT NOT NULL,
    id_liquidacao INTEGER,
    id_fatura VARCHAR(7),
    CONSTRAINT pk_chamados PRIMARY KEY (codigo),
    CONSTRAINT ck_chamados_categoria CHECK (categoria IN ('Dúvida de produto', 'Recebimento', 'Maquininha', 'Fatura e aluguel', 'Antecipação', 'Alteração cadastral', 'Contestação')),
    CONSTRAINT ck_chamados_prioridade CHECK (prioridade IN ('baixa', 'média', 'alta', 'crítica')),
    CONSTRAINT ck_chamados_fila CHECK (fila IN ('varejo', 'pme', 'contas_chave', 'ouvidoria')),
    CONSTRAINT ck_chamados_situacao CHECK (situacao IN ('novo', 'em_atendimento', 'aguardando_lojista', 'resolvido', 'fechado')),
    CONSTRAINT ck_chamados_aberto_por CHECK (aberto_por IN ('sistema', 'lojista', 'funcionario')),
    CONSTRAINT ck_chamados_codigo_formato CHECK (codigo LIKE 'CH______'),
    CONSTRAINT ck_chamados_protocolo_formato CHECK (protocolo LIKE '________-______'),
    CONSTRAINT ck_chamados_prazo_depois_da_abertura CHECK (prazo_em > aberto_em),
    CONSTRAINT ck_chamados_resolvido_conforme_situacao CHECK ((situacao IN ('resolvido', 'fechado') AND resolvido_em IS NOT NULL) OR (situacao NOT IN ('resolvido', 'fechado') AND resolvido_em IS NULL)),
    CONSTRAINT uq_chamados_protocolo UNIQUE (protocolo),
    CONSTRAINT fk_chamados_id_lojista FOREIGN KEY(id_lojista) REFERENCES lojistas (codigo),
    CONSTRAINT fk_chamados_id_responsavel FOREIGN KEY(id_responsavel) REFERENCES funcionarios (id),
    CONSTRAINT fk_chamados_id_liquidacao FOREIGN KEY(id_liquidacao) REFERENCES liquidacoes (id),
    CONSTRAINT fk_chamados_id_fatura FOREIGN KEY(id_fatura) REFERENCES faturas (codigo)
);
CREATE INDEX ix_chamados_id_lojista_aberto_em ON chamados (id_lojista, aberto_em);
COMMENT ON TABLE chamados IS 'Chamados do CRM. RESTRITO: o resumo é texto livre e sai mascarado.';
COMMENT ON COLUMN chamados.prazo_em IS 'Prazo do SLA (DOC-MOCK §6.4): regras.prazo_do_chamado.';
COMMENT ON COLUMN chamados.resumo IS 'RESTRITO (texto livre).';

CREATE TABLE interacoes (
    id SERIAL NOT NULL,
    id_chamado VARCHAR(8) NOT NULL,
    autor VARCHAR(12) NOT NULL,
    canal VARCHAR(15) NOT NULL,
    data_hora TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    texto TEXT NOT NULL,
    teste_seguranca BOOLEAN NOT NULL,
    comportamento_esperado TEXT,
    CONSTRAINT pk_interacoes PRIMARY KEY (id),
    CONSTRAINT ck_interacoes_autor CHECK (autor IN ('lojista', 'funcionario', 'agente')),
    CONSTRAINT ck_interacoes_canal CHECK (canal IN ('whatsapp', 'telefone', 'chat', 'email')),
    CONSTRAINT fk_interacoes_id_chamado FOREIGN KEY(id_chamado) REFERENCES chamados (codigo)
);
CREATE INDEX ix_interacoes_id_chamado_data_hora ON interacoes (id_chamado, data_hora);
COMMENT ON TABLE interacoes IS 'Mensagens dos chamados. RESTRITO: texto livre, por onde chegaria uma injeção de comando.';
COMMENT ON COLUMN interacoes.texto IS 'RESTRITO (texto livre). Sempre dado, nunca ordem.';
COMMENT ON COLUMN interacoes.teste_seguranca IS 'Marca o dado de teste de segurança (DOC-MOCK §10.3).';

CREATE TABLE pesquisas_satisfacao (
    id SERIAL NOT NULL,
    id_chamado VARCHAR(8) NOT NULL,
    nota INTEGER NOT NULL,
    comentario TEXT,
    respondida_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    teste_seguranca BOOLEAN NOT NULL,
    comportamento_esperado TEXT,
    CONSTRAINT pk_pesquisas_satisfacao PRIMARY KEY (id),
    CONSTRAINT ck_pesquisas_satisfacao_nota_de_1_a_5 CHECK (nota BETWEEN 1 AND 5),
    CONSTRAINT uq_pesquisas_satisfacao_id_chamado UNIQUE (id_chamado),
    CONSTRAINT fk_pesquisas_satisfacao_id_chamado FOREIGN KEY(id_chamado) REFERENCES chamados (codigo)
);
CREATE INDEX ix_pesquisas_satisfacao_respondida_em ON pesquisas_satisfacao (respondida_em);
COMMENT ON TABLE pesquisas_satisfacao IS 'Pesquisa CSAT de um chamado resolvido (DOC-MOCK §6.7). RESTRITO: o comentário é texto livre do lojista.';
COMMENT ON COLUMN pesquisas_satisfacao.comentario IS 'RESTRITO (texto livre). Sempre dado, nunca ordem.';
COMMENT ON COLUMN pesquisas_satisfacao.teste_seguranca IS 'Marca o dado de teste de segurança (DOC-MOCK §10.3).';
