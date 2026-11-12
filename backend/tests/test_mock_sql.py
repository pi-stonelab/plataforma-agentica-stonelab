"""O SQL pronto de mock/sql/ (o que vai para o Git) é o mesmo mundo que o código gera."""

import sqlite3
from contextlib import closing

from mock import exportar  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import criar_engine
from mock.gerar import ARQUIVOS_SQL_SQLITE, PASTA_SQL_SQLITE, garantir_mundo_local, recriar
from mock.modelos import VERSAO_DO_ESQUEMA, BaseMock

from .test_mock_gerar import _conteudo_do_banco
from .test_regressao_contrato import achados_de_lgpd

TABELAS = set(BaseMock.metadata.tables)


def _url(caminho) -> str:
    return f"sqlite:///{caminho.as_posix()}"


def test_sql_do_git_esta_atualizado_com_o_codigo():
    assert exportar.desatualizados() == [], "rode: python -m mock.exportar"


def test_conferir_pela_linha_de_comando():
    assert exportar.principal(["--conferir"]) == 0


def test_sqlite_montado_do_sql_e_igual_ao_gerado_pelo_codigo(tmp_path):
    caminho = tmp_path / "mock.sqlite"
    assert garantir_mundo_local(_url(caminho)) is True
    do_sql = criar_engine(_url(caminho))
    do_codigo = criar_engine("sqlite://")
    recriar(do_codigo)
    try:
        assert _conteudo_do_banco(do_sql) == _conteudo_do_banco(do_codigo)
    finally:
        do_sql.dispose()


def test_sqlite_montado_do_sql_tem_versao_e_chaves_consistentes(tmp_path):
    caminho = tmp_path / "mock.sqlite"
    garantir_mundo_local(_url(caminho))
    with closing(sqlite3.connect(caminho)) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == VERSAO_DO_ESQUEMA
        assert conexao.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conexao.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        reais = conexao.execute("SELECT count(*) FROM funcionarios WHERE pessoa_real_teste").fetchone()[0]
    assert reais == 0


def test_sql_nao_tem_dado_pessoal_real():
    for caminho in sorted(exportar.PASTA_SQL.rglob("*.sql")):
        assert achados_de_lgpd(caminho.read_text(encoding="utf-8")) == set(), caminho.name


def test_os_dois_bancos_tem_esquema_e_dados():
    for banco in exportar.DIALETOS:
        pasta = exportar.PASTA_SQL / banco
        assert (pasta / exportar.ARQUIVO_ESQUEMA).exists()
        assert (pasta / exportar.ARQUIVO_DADOS).exists()
    assert [PASTA_SQL_SQLITE / nome for nome in ARQUIVOS_SQL_SQLITE] == [
        exportar.PASTA_SQL / "sqlite" / exportar.ARQUIVO_ESQUEMA,
        exportar.PASTA_SQL / "sqlite" / exportar.ARQUIVO_DADOS,
    ]


def test_esquema_cria_todas_as_tabelas_e_so_elas():
    for banco in exportar.DIALETOS:
        texto = (exportar.PASTA_SQL / banco / exportar.ARQUIVO_ESQUEMA).read_text(encoding="utf-8")
        criadas = {linha.split()[2] for linha in texto.splitlines() if linha.startswith("CREATE TABLE ")}
        assert criadas == TABELAS, banco
        assert "DROP " not in texto.upper()  # o SQL pronto nunca apaga nada


def test_pasta_sql_so_tem_os_arquivos_esperados():
    """Nada de dump solto: a pasta é a única exceção ao *.sql ignorado da raiz."""
    esperados = set(exportar.arquivos()) | {
        exportar.PASTA_SQL / "postgres" / "03_papeis.sh",
        exportar.PASTA_SQL / ".gitignore",
        exportar.PASTA_SQL / ".gitattributes",
    }
    presentes = {caminho for caminho in exportar.PASTA_SQL.rglob("*") if caminho.is_file()}
    assert presentes == esperados


def test_script_de_papeis_so_concede_leitura():
    texto = (exportar.PASTA_SQL / "postgres" / "03_papeis.sh").read_text(encoding="utf-8")
    concessoes = [linha for linha in texto.splitlines() if linha.startswith("GRANT ")]
    assert concessoes and all(" TO mock_leitura;" in linha for linha in concessoes)
    privilegios = {linha.removeprefix("GRANT ").split(" ON ")[0] for linha in concessoes}
    assert privilegios == {"CONNECT", "USAGE", "SELECT"}
    assert "\r" not in texto  # roda no Linux do container
