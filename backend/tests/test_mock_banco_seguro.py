"""Trava do gerador do mock (ALTO-2 e MED-1 da auditoria A1-A3): nunca apaga o banco da plataforma."""

import shutil
import subprocess
from pathlib import Path

import pytest
from mock.banco import CAMINHO_LOCAL_PADRAO, url_padrao
from mock.falhas import SistemaIndisponivel
from mock.gerar import principal

RAIZ = Path(__file__).resolve().parents[2]
POSTGRES = "postgresql+psycopg://alguem:senha-secreta@servidor.exemplo/stonelab"


@pytest.fixture
def sem_banco_de_verdade(monkeypatch):
    """Troca criar_engine e recriar por falsos: o teste só olha para qual URL seria usada."""
    pedidas, recriadas = [], []
    monkeypatch.setattr("mock.gerar.criar_engine", lambda url: pedidas.append(url) or url)
    monkeypatch.setattr(
        "mock.gerar.recriar", lambda engine, caminho=None: recriadas.append(engine) or {"lojistas": 0}
    )
    return pedidas, recriadas


@pytest.fixture
def pasta_local_de_teste(tmp_path, monkeypatch):
    pasta = tmp_path / "dados_locais"
    monkeypatch.setattr("mock.banco.PASTA_LOCAL", pasta)
    monkeypatch.setattr("mock.banco.CAMINHO_LOCAL_PADRAO", pasta / "mock.sqlite")
    return pasta


def test_caminho_padrao_fica_na_raiz_do_repo_e_nao_no_diretorio_atual():
    assert CAMINHO_LOCAL_PADRAO == RAIZ / "dados_locais" / "mock.sqlite"
    assert CAMINHO_LOCAL_PADRAO.is_absolute()


def test_url_padrao_ignora_database_url_e_o_diretorio_atual(
    monkeypatch, tmp_path, pasta_local_de_teste
):
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    monkeypatch.chdir(tmp_path / "..")
    assert url_padrao() == f"sqlite:///{(pasta_local_de_teste / 'mock.sqlite').as_posix()}"


def test_url_padrao_cria_a_pasta_local(pasta_local_de_teste):
    assert not pasta_local_de_teste.exists()
    url_padrao()
    assert pasta_local_de_teste.is_dir()


def test_sem_url_usa_o_sqlite_local_mesmo_com_database_url(
    monkeypatch, sem_banco_de_verdade, pasta_local_de_teste
):
    pedidas, _ = sem_banco_de_verdade
    monkeypatch.setenv("DATABASE_URL", POSTGRES)
    assert principal(["--sim"]) == 0
    assert len(pedidas) == 1 and pedidas[0].startswith("sqlite:///")
    assert "postgresql" not in pedidas[0]


def test_banco_que_nao_e_sqlite_exige_flag_explicita(sem_banco_de_verdade, capsys):
    pedidas, recriadas = sem_banco_de_verdade
    assert principal(["--url", POSTGRES, "--sim"]) == 2
    assert pedidas == [] and recriadas == []
    erro = capsys.readouterr().err
    assert "--permitir-banco-externo" in erro
    assert "senha-secreta" not in erro


def test_banco_externo_com_a_flag_e_aceito(sem_banco_de_verdade):
    pedidas, recriadas = sem_banco_de_verdade
    argumentos = ["--url", POSTGRES, "--permitir-banco-externo", "--sim"]
    assert principal(argumentos) == 0
    assert pedidas == [POSTGRES] and recriadas == [POSTGRES]


def test_url_malformada_e_recusada_sem_repetir_o_texto(sem_banco_de_verdade, capsys):
    pedidas, _ = sem_banco_de_verdade
    assert principal(["--url", "senha-secreta isso nao e url", "--sim"]) == 2
    assert pedidas == []
    assert "senha-secreta" not in capsys.readouterr().err


def test_recriar_pergunta_antes_de_apagar(sem_banco_de_verdade, pasta_local_de_teste, capsys):
    _, recriadas = sem_banco_de_verdade
    perguntas = []

    def nao(texto):
        perguntas.append(texto)
        return "não"

    assert principal([], perguntar=nao) == 1
    assert recriadas == [] and len(perguntas) == 1
    assert "nada foi apagado" in capsys.readouterr().err
    assert principal([], perguntar=lambda texto: "SIM ") == 0
    assert len(recriadas) == 1


def test_sem_terminal_a_pergunta_vale_como_nao(sem_banco_de_verdade, pasta_local_de_teste):
    _, recriadas = sem_banco_de_verdade

    def sem_entrada(texto):
        raise EOFError

    assert principal([], perguntar=sem_entrada) == 1
    assert recriadas == []


def test_pergunta_de_banco_externo_nao_mostra_a_url(sem_banco_de_verdade):
    perguntas = []
    principal(
        ["--url", POSTGRES, "--permitir-banco-externo"],
        perguntar=lambda texto: perguntas.append(texto) or "nao",
    )
    assert perguntas and "senha-secreta" not in perguntas[0]


def test_memoria_nao_pergunta(sem_banco_de_verdade):
    def nao_deveria_perguntar(texto):
        raise AssertionError("não devia perguntar")

    assert principal(["--url", "sqlite://"], perguntar=nao_deveria_perguntar) == 0


def test_sistema_indisponivel_e_um_erro_de_conexao():
    erro = SistemaIndisponivel("core")
    assert isinstance(erro, ConnectionError)
    assert str(erro) == "sistema indisponível: core"
    assert erro.sistema == "core"


@pytest.mark.skipif(shutil.which("git") is None, reason="precisa do git")
@pytest.mark.parametrize(
    "caminho",
    ["pessoas_teste.csv", "pessoas_teste_colegas.csv", "pasta/pessoas_teste.csv", "mock.db",
     "dump.sql", "dados_locais/mock.sqlite", ".env"],
)
def test_gitignore_cobre_dados_locais_e_segredos(caminho):
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", caminho], cwd=RAIZ, capture_output=True, check=False
    )
    if resultado.returncode == 128:
        pytest.skip("fora de um repositório git")
    assert resultado.returncode == 0, f"{caminho} não está no .gitignore"
