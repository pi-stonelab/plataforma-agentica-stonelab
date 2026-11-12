#!/bin/sh
# Papel só de leitura do mock (mock_leitura): só SELECT nas tabelas do mock. É o papel das
# ferramentas, em MOCK_DATABASE_URL. O dono (POSTGRES_USER) só serve para criar e recriar.
#
# O Postgres do mock/docker-compose.yml roda este arquivo uma vez, na primeira subida, depois do
# 01_esquema.sql e do 02_dados.sql. Ele pode ser executado ou lido com "source", então não muda
# opções do shell nem usa exit. A senha vem do .env e nunca fica escrita no repositório.
: "${MOCK_LEITURA_PASSWORD:?defina MOCK_LEITURA_PASSWORD no .env}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v banco="$POSTGRES_DB" -v senha="$MOCK_LEITURA_PASSWORD" <<'SQL'
CREATE ROLE mock_leitura LOGIN PASSWORD :'senha';

-- ninguém além do dono usa o banco por padrão
REVOKE ALL ON DATABASE :"banco" FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- o papel de leitura só conecta e lê
GRANT CONNECT ON DATABASE :"banco" TO mock_leitura;
GRANT USAGE ON SCHEMA public TO mock_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mock_leitura;
SQL
