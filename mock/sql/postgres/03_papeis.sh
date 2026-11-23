#!/bin/sh
# Papéis do Postgres do mock. Gerado por `python -m mock.exportar` a partir de mock/escritas.py
# (PRIVILEGIOS_DE_ESCRITA). Não edite à mão: rode o exportador.
#
# - mock_leitura: só SELECT. É o das ferramentas de leitura, em MOCK_DATABASE_URL.
# - mock_escrita: lê tudo, insere e altera só o que as ferramentas de escrita gravam depois da confirmação
#   da pessoa (mock/escritas.py), em MOCK_ESCRITA_DATABASE_URL. Nunca apaga nem cria tabela.
# O dono (POSTGRES_USER) só serve para criar e recriar.
#
# O Postgres do mock/docker-compose.yml roda este arquivo uma vez, na primeira subida, depois do
# 01_esquema.sql e do 02_dados.sql. Ele pode ser executado ou lido com "source", então não muda
# opções do shell nem usa exit. As senhas vêm do .env e nunca ficam escritas no repositório.
: "${MOCK_LEITURA_PASSWORD:?defina MOCK_LEITURA_PASSWORD no .env}"
: "${MOCK_ESCRITA_PASSWORD:?defina MOCK_ESCRITA_PASSWORD no .env}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v banco="$POSTGRES_DB" -v senha="$MOCK_LEITURA_PASSWORD" -v senha_escrita="$MOCK_ESCRITA_PASSWORD" <<'SQL'
CREATE ROLE mock_leitura LOGIN PASSWORD :'senha';
CREATE ROLE mock_escrita LOGIN PASSWORD :'senha_escrita';

-- ninguém além do dono usa o banco por padrão
REVOKE ALL ON DATABASE :"banco" FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- o papel de leitura só conecta e lê
GRANT CONNECT ON DATABASE :"banco" TO mock_leitura;
GRANT USAGE ON SCHEMA public TO mock_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mock_leitura;

-- o papel de escrita lê tudo e grava só o que mock/escritas.py precisa
GRANT CONNECT ON DATABASE :"banco" TO mock_escrita;
GRANT USAGE ON SCHEMA public TO mock_escrita;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mock_escrita;
GRANT INSERT ON acordos TO mock_escrita;
GRANT UPDATE (situacao, id_aprovador) ON acordos TO mock_escrita;
GRANT INSERT ON antecipacoes TO mock_escrita;
GRANT INSERT ON chamados TO mock_escrita;
GRANT UPDATE (situacao, id_responsavel, resolvido_em, nivel_atendimento, suspeita_fraude) ON chamados TO mock_escrita;
GRANT UPDATE (situacao, id_acordo) ON faturas TO mock_escrita;
GRANT INSERT ON interacoes TO mock_escrita;
GRANT INSERT ON liquidacoes TO mock_escrita;
GRANT UPDATE (situacao) ON liquidacoes TO mock_escrita;
GRANT UPDATE (situacao, id_antecipacao) ON recebiveis TO mock_escrita;
GRANT USAGE ON SEQUENCE interacoes_id_seq, liquidacoes_id_seq TO mock_escrita;
SQL
