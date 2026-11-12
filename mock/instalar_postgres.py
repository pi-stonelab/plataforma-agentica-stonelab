"""Instala o Postgres do mock num Postgres que já roda na máquina, sem Docker.

Faz o que o mock/docker-compose.yml faz na primeira subida: cria o dono e o papel só de leitura,
cria o banco do mock e carrega o SQL pronto de mock/sql/postgres/. Só aceita um Postgres da própria
máquina: o mock nunca deve ser instalado no banco da plataforma nem em servidor de outra pessoa.

    python -m mock.instalar_postgres [--porta 5433] [--recriar]

As senhas do dono e do papel de leitura vêm do .env (MOCK_POSTGRES_PASSWORD e MOCK_LEITURA_PASSWORD).
A do superusuário é pedida no terminal, ou lida de MOCK_POSTGRES_ADMIN_PASSWORD (CI), e nenhuma
senha é impressa nem gravada.
"""

import argparse
import getpass
import os
import re
import sys
from collections.abc import Sequence

import psycopg
from psycopg import sql
from sqlalchemy import func, select

from . import exportar, modelos
from .banco import criar_engine
from .gerar import recriar

VARIAVEL_SENHA_DO_DONO = "MOCK_POSTGRES_PASSWORD"
VARIAVEL_SENHA_DA_LEITURA = "MOCK_LEITURA_PASSWORD"
VARIAVEL_SENHA_DO_ADMIN = "MOCK_POSTGRES_ADMIN_PASSWORD"

BANCO_PADRAO = "stonelab_mock"
DONO_PADRAO = "mock"
PAPEL_DE_LEITURA_PADRAO = "mock_leitura"
PORTA_PADRAO = 5433
HOSTS_DA_PROPRIA_MAQUINA = frozenset({"127.0.0.1", "localhost", "::1"})
PADRAO_DE_NOME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ErroDeInstalacao(Exception):
    """Falha que o usuário pode corrigir; a mensagem diz como."""


def validar_nome(nome: str, rotulo: str, *, exige_mock: bool = False) -> str:
    if not PADRAO_DE_NOME.fullmatch(nome):
        raise ErroDeInstalacao(f"{rotulo} inválido: use letras minúsculas, números e _, começando por letra.")
    if exige_mock and "mock" not in nome:
        raise ErroDeInstalacao(f"{rotulo}: o nome precisa conter 'mock' para nunca coincidir com o da plataforma.")
    return nome


def validar_host(host: str) -> str:
    if host.lower() not in HOSTS_DA_PROPRIA_MAQUINA:
        raise ErroDeInstalacao("O mock só é instalado num Postgres desta máquina (127.0.0.1, localhost ou ::1).")
    return host


def _senha_do_ambiente(variavel: str) -> str:
    senha = os.environ.get(variavel, "")
    if not senha:
        raise ErroDeInstalacao(f"Defina {variavel} no .env antes de instalar.")
    return senha


def papeis_sql(banco: str, papel_de_leitura: str) -> list[sql.Composed]:
    """Permissões do papel só de leitura. Espelha mock/sql/postgres/03_papeis.sh (um teste confere)."""
    banco_id, papel_id = sql.Identifier(banco), sql.Identifier(papel_de_leitura)
    return [
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(banco_id),
        sql.SQL("REVOKE ALL ON SCHEMA public FROM PUBLIC"),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(banco_id, papel_id),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(papel_id),
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(papel_id),
    ]


def _conectar(host: str, porta: int, banco: str, usuario: str, senha: str) -> psycopg.Connection:
    try:
        return psycopg.connect(host=host, port=porta, dbname=banco, user=usuario, password=senha, autocommit=True)
    except psycopg.OperationalError as erro:
        motivo = " ".join(linha.strip() for linha in str(erro).splitlines() if linha.strip()) or "sem detalhe"
        raise ErroDeInstalacao(
            f"Não consegui entrar como '{usuario}' em {host}:{porta}/{banco}. "
            f"O serviço está rodando e a porta está certa? Detalhe: {motivo}"
        ) from erro


def _papel_existe(conexao: psycopg.Connection, papel: str) -> bool:
    return conexao.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (papel,)).fetchone() is not None


def _banco_existe(conexao: psycopg.Connection, banco: str) -> bool:
    return conexao.execute("SELECT 1 FROM pg_database WHERE datname = %s", (banco,)).fetchone() is not None


def _garantir_papel(conexao: psycopg.Connection, papel: str, senha: str) -> None:
    """Cria o papel ou, se já existe, só atualiza a senha para a do .env."""
    comando = "ALTER ROLE {} LOGIN PASSWORD {}" if _papel_existe(conexao, papel) else "CREATE ROLE {} LOGIN PASSWORD {}"
    conexao.execute(sql.SQL(comando).format(sql.Identifier(papel), sql.Literal(senha)))


def _exigir_banco_livre(conexao: psycopg.Connection, banco: str, *, recriar_banco: bool) -> None:
    """Recusa, antes de mexer em qualquer coisa, instalar por cima de um banco que já existe."""
    if _banco_existe(conexao, banco) and not recriar_banco:
        raise ErroDeInstalacao(f"O banco '{banco}' já existe. Nada foi alterado; use --recriar para voltar ao mundo original.")


def _criar_banco(conexao: psycopg.Connection, banco: str, dono: str) -> None:
    if _banco_existe(conexao, banco):
        conexao.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(banco)))
    conexao.execute(
        sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'").format(
            sql.Identifier(banco), sql.Identifier(dono)
        )
    )


def _carregar_sql_pronto(conexao: psycopg.Connection) -> None:
    for nome in (exportar.ARQUIVO_ESQUEMA, exportar.ARQUIVO_DADOS):
        conexao.execute((exportar.PASTA_SQL / "postgres" / nome).read_text(encoding="utf-8"))


def _contagens_esperadas() -> dict[str, int]:
    """Linhas por tabela do mundo gerado pelo código, que o banco instalado precisa repetir."""
    engine = criar_engine("sqlite://")
    recriar(engine)
    try:
        with engine.connect() as conexao:
            return {
                tabela.name: conexao.execute(select(func.count()).select_from(tabela)).scalar_one()
                for tabela in modelos.BaseMock.metadata.sorted_tables
            }
    finally:
        engine.dispose()


def conferir_instalacao(conexao: psycopg.Connection, papel_de_leitura: str) -> list[str]:
    """Problemas encontrados lendo pelo papel de leitura; lista vazia quer dizer que está tudo certo."""
    problemas = []
    for tabela, esperado in _contagens_esperadas().items():
        encontrado = conexao.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabela))).fetchone()[0]
        if encontrado != esperado:
            problemas.append(f"{tabela}: {encontrado} linhas, esperado {esperado}")
        pode_escrever = conexao.execute(
            "SELECT has_table_privilege(%s, %s, 'INSERT, UPDATE, DELETE, TRUNCATE')", (papel_de_leitura, tabela)
        ).fetchone()[0]
        if pode_escrever:
            problemas.append(f"{tabela}: o papel de leitura consegue escrever")
    return problemas


def instalar(
    *,
    host: str,
    porta: int,
    banco: str,
    dono: str,
    papel_de_leitura: str,
    admin: str,
    senha_do_admin: str,
    senha_do_dono: str,
    senha_da_leitura: str,
    recriar_banco: bool,
) -> None:
    validar_host(host)
    validar_nome(banco, "Banco", exige_mock=True)
    validar_nome(dono, "Dono")
    validar_nome(papel_de_leitura, "Papel de leitura")
    if len({dono, papel_de_leitura, admin}) != 3:
        raise ErroDeInstalacao("O superusuário, o dono e o papel de leitura precisam ser três papéis diferentes.")
    if senha_do_dono == senha_da_leitura:
        raise ErroDeInstalacao("A senha do dono e a do papel de leitura precisam ser diferentes.")

    with _conectar(host, porta, "postgres", admin, senha_do_admin) as conexao:
        _exigir_banco_livre(conexao, banco, recriar_banco=recriar_banco)
        _garantir_papel(conexao, dono, senha_do_dono)
        _garantir_papel(conexao, papel_de_leitura, senha_da_leitura)
        _criar_banco(conexao, banco, dono)
    with _conectar(host, porta, banco, dono, senha_do_dono) as conexao:
        _carregar_sql_pronto(conexao)
    with _conectar(host, porta, banco, admin, senha_do_admin) as conexao:
        for comando in papeis_sql(banco, papel_de_leitura):
            conexao.execute(comando)
    with _conectar(host, porta, banco, papel_de_leitura, senha_da_leitura) as conexao:
        problemas = conferir_instalacao(conexao, papel_de_leitura)
    if problemas:
        raise ErroDeInstalacao("A conferência final falhou: " + "; ".join(problemas))


def _analisar(argumentos: Sequence[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Instala o Postgres do mock numa máquina que já tem Postgres.")
    analisador.add_argument("--host", default="127.0.0.1")
    analisador.add_argument("--porta", type=int, default=PORTA_PADRAO)
    analisador.add_argument("--banco", default=BANCO_PADRAO)
    analisador.add_argument("--dono", default=DONO_PADRAO)
    analisador.add_argument("--papel-de-leitura", default=PAPEL_DE_LEITURA_PADRAO)
    analisador.add_argument("--admin", default="postgres", help="superusuário que cria os papéis e o banco")
    analisador.add_argument("--recriar", action="store_true", help="apaga o banco do mock e instala de novo")
    return analisador.parse_args(argumentos)


def principal(argumentos: Sequence[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parametros = _analisar(argumentos)
    try:
        validar_host(parametros.host)
        senha_do_dono = _senha_do_ambiente(VARIAVEL_SENHA_DO_DONO)
        senha_da_leitura = _senha_do_ambiente(VARIAVEL_SENHA_DA_LEITURA)
        senha_do_admin = os.environ.get(VARIAVEL_SENHA_DO_ADMIN) or getpass.getpass(
            f"Senha do superusuário '{parametros.admin}' do Postgres: "
        )
        instalar(
            host=parametros.host,
            porta=parametros.porta,
            banco=parametros.banco,
            dono=parametros.dono,
            papel_de_leitura=parametros.papel_de_leitura,
            admin=parametros.admin,
            senha_do_admin=senha_do_admin,
            senha_do_dono=senha_do_dono,
            senha_da_leitura=senha_da_leitura,
            recriar_banco=parametros.recriar,
        )
    except ErroDeInstalacao as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Mock instalado em {parametros.host}:{parametros.porta}/{parametros.banco}.")
    print("Coloque no .env (com a senha do papel de leitura no lugar indicado):")
    print(
        f"MOCK_DATABASE_URL=postgresql+psycopg://{parametros.papel_de_leitura}:<{VARIAVEL_SENHA_DA_LEITURA}>"
        f"@{parametros.host}:{parametros.porta}/{parametros.banco}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
