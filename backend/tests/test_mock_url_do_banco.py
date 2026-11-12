"""MOCK_DATABASE_URL (P2 da crítica B): uma variável própria para o banco do mock."""

import pytest
from ferramentas import dados_sinteticos
from mock.banco import criar_engine, criar_tabelas, url_padrao
from mock.falhas import desligar_todas, ligar
from mock.gerar import principal, recriar

POSTGRES = "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab"


@pytest.fixture(autouse=True)
def sem_variaveis(monkeypatch):
    monkeypatch.delenv("MOCK_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(dados_sinteticos._CONEXAO, "engine", None)
    yield
    desligar_todas()


@pytest.fixture
def pasta_local(tmp_path, monkeypatch):
    monkeypatch.setattr("mock.banco.PASTA_LOCAL", tmp_path / "dados_locais")
    monkeypatch.setattr("mock.banco.CAMINHO_LOCAL_PADRAO", tmp_path / "dados_locais" / "mock.sqlite")
    return tmp_path / "dados_locais"


def test_variavel_declarada_vence_o_sqlite_local(monkeypatch, pasta_local):
    monkeypatch.setenv("MOCK_DATABASE_URL", "sqlite:////tmp/outro_mock.sqlite")
    assert url_padrao() == "sqlite:////tmp/outro_mock.sqlite"
    assert not pasta_local.exists()


def test_sem_variavel_o_padrao_e_o_sqlite_local(pasta_local):
    assert url_padrao() == f"sqlite:///{(pasta_local / 'mock.sqlite').as_posix()}"


def test_database_url_da_plataforma_continua_ignorada(monkeypatch, pasta_local):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    assert url_padrao().startswith("sqlite:///")


def test_mock_database_url_igual_a_da_plataforma_e_recusada(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.setenv("MOCK_DATABASE_URL", POSTGRES)
    with pytest.raises(ValueError, match="banco da plataforma") as erro:
        url_padrao()
    assert "senha-secreta" not in str(erro.value)


MESMO_BANCO_ESCRITO_DE_OUTRO_JEITO = [
    "postgresql://outro:outra@servidor.exemplo/stonelab",  # driver e usuário diferentes
    "postgresql+psycopg2://alguem:senha-secreta@servidor.exemplo/stonelab",
    "postgresql+asyncpg://alguem:senha-secreta@servidor.exemplo/stonelab",
    "postgres://alguem:senha-secreta@servidor.exemplo/stonelab",  # apelido do Heroku
    "postgres+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab",
    "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab/",  # barra no fim
    "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab?sslmode=require",
    "postgresql+psycopg://alguem:senha-secreta@SERVIDOR.Exemplo/stonelab",  # host em maiúsculas
    "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo:5432/stonelab",  # porta padrão
    "postgresql+psycopg://%61lguem:senha-secreta@servidor.exemplo/stonelab",  # usuário percent-encoded
    "  postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab  ",  # espaços
]


@pytest.mark.parametrize("escrita", MESMO_BANCO_ESCRITO_DE_OUTRO_JEITO)
def test_mock_database_url_com_o_mesmo_banco_escrito_de_outro_jeito_e_recusada(monkeypatch, escrita):
    """MED-3 da auditoria C: a comparação é pelo banco, não pelo texto."""
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.setenv("MOCK_DATABASE_URL", escrita)
    with pytest.raises(ValueError, match="banco da plataforma") as erro:
        url_padrao()
    mensagem = str(erro.value)
    assert "senha" not in mensagem and "servidor" not in mensagem and "stonelab" not in mensagem


def test_a_plataforma_escrita_de_outro_jeito_tambem_casa(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://alguem:x@SERVIDOR.exemplo:5432/stonelab/?sslmode=require")
    monkeypatch.setenv("MOCK_DATABASE_URL", POSTGRES)
    with pytest.raises(ValueError, match="banco da plataforma"):
        url_padrao()


@pytest.mark.parametrize(
    "outro",
    [
        "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab_mock",  # outro banco
        "postgresql+psycopg://alguem:senha-secreta@outro.exemplo/stonelab",  # outro servidor
        "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo:5433/stonelab",  # outra porta
        "mysql+pymysql://alguem:senha-secreta@servidor.exemplo/stonelab",  # outro tipo de banco
        "sqlite:////tmp/stonelab",
    ],
)
def test_banco_diferente_da_plataforma_passa(monkeypatch, outro):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.setenv("MOCK_DATABASE_URL", outro)
    assert url_padrao() == outro


def test_sqlite_relativo_e_absoluto_do_mesmo_arquivo_sao_o_mesmo_banco(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    absoluto = tmp_path / "dev.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///dev.db")
    for escrita in (f"sqlite:///{absoluto.as_posix()}", "sqlite:///./dev.db", "sqlite:///sub/../dev.db"):
        monkeypatch.setenv("MOCK_DATABASE_URL", escrita)
        with pytest.raises(ValueError, match="banco da plataforma"):
            url_padrao()
    monkeypatch.setenv("MOCK_DATABASE_URL", "sqlite:///outro.db")
    assert url_padrao() == "sqlite:///outro.db"


def test_url_ilegivel_nao_derruba_a_comparacao_nem_aparece_na_mensagem(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "senha-secreta isso nao e url")
    monkeypatch.setenv("MOCK_DATABASE_URL", "senha-secreta isso nao e url")
    with pytest.raises(ValueError, match="banco da plataforma") as erro:
        url_padrao()
    assert "senha-secreta" not in str(erro.value)
    monkeypatch.setenv("MOCK_DATABASE_URL", "sqlite:////tmp/outro.sqlite")
    assert url_padrao() == "sqlite:////tmp/outro.sqlite"


def test_gerador_com_plataforma_escrita_de_outro_jeito_sai_com_2_sem_repetir_a_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.setenv("MOCK_DATABASE_URL", "postgres://alguem:senha-secreta@SERVIDOR.exemplo:5432/stonelab/")
    assert principal(["--sim", "--permitir-banco-externo"]) == 2
    assert "senha-secreta" not in capsys.readouterr().err


def test_gerador_com_postgres_na_variavel_exige_a_flag(monkeypatch, capsys):
    pedidas = []
    monkeypatch.setattr("mock.gerar.criar_engine", lambda url: pedidas.append(url) or url)
    monkeypatch.setattr("mock.gerar.recriar", lambda engine, caminho=None: {"lojistas": 0})
    monkeypatch.setenv("MOCK_DATABASE_URL", POSTGRES)
    assert principal(["--sim"]) == 2
    assert pedidas == [] and "--permitir-banco-externo" in capsys.readouterr().err
    assert principal(["--sim", "--permitir-banco-externo"]) == 0
    assert pedidas == [POSTGRES]


def test_gerador_com_mock_igual_a_plataforma_sai_com_2_sem_repetir_a_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.setenv("MOCK_DATABASE_URL", POSTGRES)
    assert principal(["--sim", "--permitir-banco-externo"]) == 2
    assert "senha-secreta" not in capsys.readouterr().err


def test_fachada_le_o_banco_da_variavel(monkeypatch, tmp_path):
    arquivo = tmp_path / "mock_da_variavel.sqlite"
    engine = criar_engine(f"sqlite:///{arquivo.as_posix()}")
    recriar(engine)
    engine.dispose()
    monkeypatch.setenv("MOCK_DATABASE_URL", f"sqlite:///{arquivo.as_posix()}")
    assert dados_sinteticos.carteira_do_lojista("M00001")["carteira"] == "varejo"
    assert dados_sinteticos.buscar_funcionario("F0001")["cargo"] == "atendente_n1"
    assert dados_sinteticos.buscar_funcionario("F9999") is None


def test_fachada_com_url_invalida_da_conexao_fora_do_ar_sem_repetir_a_url(monkeypatch):
    monkeypatch.setenv("MOCK_DATABASE_URL", "senha-secreta isso nao e url")
    with pytest.raises(ConnectionError) as erro:
        dados_sinteticos.carteira_do_lojista("M00001")
    assert "senha-secreta" not in str(erro.value) and erro.value.__cause__ is None


def test_diretorio_fora_do_ar_na_fachada_vira_connection_error():
    dados_sinteticos.configurar(_mundo_em_memoria())
    ligar("diretorio")
    with pytest.raises(ConnectionError):
        dados_sinteticos.buscar_funcionario("F0001")


def _mundo_em_memoria():
    engine = criar_engine("sqlite://")
    criar_tabelas(engine)
    recriar(engine)
    return engine
