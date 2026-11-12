"""Instalador do Postgres do mock (mock/instalar_postgres.py).

As regras de recusa e o espelho de 03_papeis.sh rodam sempre. A instalação de verdade só roda com
`MOCK_TESTE_POSTGRES_ADMIN_URL`: a URL de um superusuário de um Postgres de teste. Ela usa nomes
próprios de banco e de papéis e os apaga no fim, sem tocar no resto do servidor.
"""

import os
import re
import secrets

import psycopg
import pytest
from mock import (  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
    exportar,
    instalar_postgres,
)
from mock.instalar_postgres import ErroDeInstalacao
from psycopg import sql
from sqlalchemy.engine import make_url

URL_ADMIN = os.environ.get("MOCK_TESTE_POSTGRES_ADMIN_URL", "").strip() or None
BANCO_DE_TESTE = "mock_instalador_teste"
DONO_DE_TESTE = "mock_dono_teste"
LEITURA_DE_TESTE = "mock_leitura_teste"


def _senha() -> str:
    return secrets.token_urlsafe(18)


def _argumentos_de_instalacao(**trocas) -> dict:
    argumentos = {
        "host": "127.0.0.1",
        "porta": 1,
        "banco": BANCO_DE_TESTE,
        "dono": DONO_DE_TESTE,
        "papel_de_leitura": LEITURA_DE_TESTE,
        "admin": "postgres",
        "senha_do_admin": _senha(),
        "senha_do_dono": _senha(),
        "senha_da_leitura": _senha(),
        "recriar_banco": False,
    }
    argumentos.update(trocas)
    return argumentos


@pytest.mark.parametrize("host", ["db.exemplo.com", "10.0.0.5", "192.168.0.10", ""])
def test_recusa_postgres_que_nao_e_desta_maquina(host):
    with pytest.raises(ErroDeInstalacao, match="desta máquina"):
        instalar_postgres.instalar(**_argumentos_de_instalacao(host=host))


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "LOCALHOST", "::1"])
def test_aceita_os_enderecos_da_propria_maquina(host):
    assert instalar_postgres.validar_host(host) == host


@pytest.mark.parametrize(
    "banco",
    ["stonelab", "plataforma", 'mock"; DROP DATABASE x; --', "Mock_Maiusculo", "mock banco", "1mock", "mock-banco", ""],
)
def test_recusa_nome_de_banco_que_nao_e_do_mock_ou_e_perigoso(banco):
    with pytest.raises(ErroDeInstalacao):
        instalar_postgres.instalar(**_argumentos_de_instalacao(banco=banco))


@pytest.mark.parametrize("papel", ['mock"; --', "Dono", "dono com espaço", "", "a" * 64])
def test_recusa_nome_de_papel_perigoso(papel):
    with pytest.raises(ErroDeInstalacao):
        instalar_postgres.instalar(**_argumentos_de_instalacao(dono=papel))
    with pytest.raises(ErroDeInstalacao):
        instalar_postgres.instalar(**_argumentos_de_instalacao(papel_de_leitura=papel))


def test_recusa_papeis_repetidos_e_senhas_iguais():
    with pytest.raises(ErroDeInstalacao, match="três papéis diferentes"):
        instalar_postgres.instalar(**_argumentos_de_instalacao(papel_de_leitura=DONO_DE_TESTE))
    with pytest.raises(ErroDeInstalacao, match="três papéis diferentes"):
        instalar_postgres.instalar(**_argumentos_de_instalacao(admin=DONO_DE_TESTE))
    igual = _senha()
    with pytest.raises(ErroDeInstalacao, match="senha do dono e a do papel de leitura"):
        instalar_postgres.instalar(**_argumentos_de_instalacao(senha_do_dono=igual, senha_da_leitura=igual))


def test_papeis_sql_espelha_o_03_papeis_sh():
    """As permissões do instalador e as do Docker não podem se separar."""
    texto = (exportar.PASTA_SQL / "postgres" / "03_papeis.sh").read_text(encoding="utf-8")
    bloco = re.search(r"<<'SQL'\n(.*?)\nSQL", texto, re.DOTALL).group(1)
    sem_comentarios = "\n".join(linha for linha in bloco.splitlines() if not linha.lstrip().startswith("--"))
    do_sh = {
        " ".join(comando.split()).replace(':"banco"', f'"{BANCO_DE_TESTE}"').replace("mock_leitura", f'"{LEITURA_DE_TESTE}"')
        for comando in sem_comentarios.split(";")
        if comando.strip().startswith(("REVOKE", "GRANT"))
    }
    do_instalador = {
        " ".join(comando.as_string().split()) for comando in instalar_postgres.papeis_sql(BANCO_DE_TESTE, LEITURA_DE_TESTE)
    }
    assert do_instalador == do_sh


def test_principal_sem_senha_do_dono_falha_sem_pedir_a_do_admin(monkeypatch, capsys):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *_, **__: None)
    monkeypatch.delenv(instalar_postgres.VARIAVEL_SENHA_DO_DONO, raising=False)
    monkeypatch.setenv(instalar_postgres.VARIAVEL_SENHA_DA_LEITURA, _senha())
    monkeypatch.setattr("getpass.getpass", lambda *_: pytest.fail("não deveria pedir a senha do superusuário"))
    assert instalar_postgres.principal([]) == 1
    assert instalar_postgres.VARIAVEL_SENHA_DO_DONO in capsys.readouterr().err


def test_nenhuma_senha_aparece_na_saida_quando_a_conexao_falha(monkeypatch, capsys):
    senhas = {_senha(), _senha(), _senha()}
    dono, leitura, admin = sorted(senhas)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *_, **__: None)
    monkeypatch.setenv(instalar_postgres.VARIAVEL_SENHA_DO_DONO, dono)
    monkeypatch.setenv(instalar_postgres.VARIAVEL_SENHA_DA_LEITURA, leitura)
    monkeypatch.setenv(instalar_postgres.VARIAVEL_SENHA_DO_ADMIN, admin)
    assert instalar_postgres.principal(["--porta", "1"]) == 1
    saida = capsys.readouterr()
    for senha in senhas:
        assert senha not in saida.out + saida.err


pytestmark_instalacao = pytest.mark.skipif(URL_ADMIN is None, reason="MOCK_TESTE_POSTGRES_ADMIN_URL não declarada")


@pytest.fixture(scope="module")
def servidor():
    url = make_url(URL_ADMIN)
    dados = {"host": url.host or "127.0.0.1", "porta": url.port or 5432, "admin": url.username, "senha": url.password}
    yield dados
    with psycopg.connect(
        host=dados["host"], port=dados["porta"], dbname="postgres", user=dados["admin"], password=dados["senha"],
        autocommit=True,
    ) as conexao:  # fmt: skip
        conexao.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(BANCO_DE_TESTE)))
        for papel in (DONO_DE_TESTE, LEITURA_DE_TESTE):
            conexao.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(papel)))


@pytest.fixture(scope="module")
def senhas():
    return {"dono": _senha(), "leitura": _senha()}


def _instalar(servidor, senhas, **trocas):
    instalar_postgres.instalar(
        **_argumentos_de_instalacao(
            host=servidor["host"], porta=servidor["porta"], admin=servidor["admin"],
            senha_do_admin=servidor["senha"], senha_do_dono=senhas["dono"],
            senha_da_leitura=senhas["leitura"], **trocas,
        )
    )  # fmt: skip


def _entrar(servidor, usuario, senha):
    return psycopg.connect(
        host=servidor["host"], port=servidor["porta"], dbname=BANCO_DE_TESTE, user=usuario, password=senha,
        autocommit=True,
    )  # fmt: skip


@pytestmark_instalacao
def test_instala_e_o_papel_de_leitura_so_le(servidor, senhas):
    _instalar(servidor, senhas)
    with _entrar(servidor, LEITURA_DE_TESTE, senhas["leitura"]) as conexao:
        assert conexao.execute("SELECT count(*) FROM lojistas").fetchone()[0] == 20
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conexao.execute("DELETE FROM lojistas")


@pytestmark_instalacao
def test_segunda_instalacao_sem_recriar_nao_altera_nada(servidor, senhas):
    with pytest.raises(ErroDeInstalacao, match="já existe"):
        _instalar(servidor, {"dono": _senha(), "leitura": _senha()})
    with _entrar(servidor, DONO_DE_TESTE, senhas["dono"]) as conexao:
        assert conexao.execute("SELECT count(*) FROM lojistas").fetchone()[0] == 20


@pytestmark_instalacao
def test_recriar_volta_ao_mundo_original(servidor, senhas):
    with _entrar(servidor, DONO_DE_TESTE, senhas["dono"]) as conexao:
        conexao.execute("DELETE FROM interacoes")
    _instalar(servidor, senhas, recriar_banco=True)
    with _entrar(servidor, LEITURA_DE_TESTE, senhas["leitura"]) as conexao:
        assert conexao.execute("SELECT count(*) FROM interacoes").fetchone()[0] > 0


@pytestmark_instalacao
def test_senha_errada_do_papel_de_leitura_nao_entra(servidor, senhas):
    with pytest.raises(psycopg.OperationalError):
        _entrar(servidor, LEITURA_DE_TESTE, _senha())
