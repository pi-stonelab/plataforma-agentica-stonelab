"""O SQLite local do mock nasce sozinho na primeira vez em que alguém o usa."""

import hashlib
import sqlite3

import pytest
from ferramentas import dados_sinteticos
from mock.banco import criar_engine
from mock.gerar import garantir_mundo_local
from mock.modelos import Lojista
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _url(caminho) -> str:
    return f"sqlite:///{caminho.as_posix()}"


def _total_de_lojistas(caminho) -> int:
    engine = criar_engine(_url(caminho))
    try:
        with Session(engine) as sessao:
            return sessao.scalar(select(func.count()).select_from(Lojista))
    finally:
        engine.dispose()


def _sha(caminho) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_gera_o_mundo_quando_o_arquivo_nao_existe(tmp_path):
    caminho = tmp_path / "mock.sqlite"
    assert garantir_mundo_local(_url(caminho)) is True
    assert _total_de_lojistas(caminho) == 20
    assert list(tmp_path.glob("*.tmp")) == []  # o arquivo temporário não sobra


def test_segunda_chamada_nao_mexe_no_arquivo(tmp_path):
    caminho = tmp_path / "mock.sqlite"
    garantir_mundo_local(_url(caminho))
    antes = _sha(caminho)
    assert garantir_mundo_local(_url(caminho)) is False
    assert _sha(caminho) == antes


def test_arquivo_vazio_sem_tabelas_e_preenchido(tmp_path):
    caminho = tmp_path / "mock.sqlite"
    caminho.touch()
    assert garantir_mundo_local(_url(caminho)) is True
    assert _total_de_lojistas(caminho) == 20


def test_nunca_mexe_em_arquivo_que_ja_tem_outras_tabelas(tmp_path):
    caminho = tmp_path / "outro.sqlite"
    with sqlite3.connect(caminho) as conexao:
        conexao.execute("CREATE TABLE anotacoes (texto TEXT)")
    antes = _sha(caminho)
    assert garantir_mundo_local(_url(caminho)) is False
    assert _sha(caminho) == antes


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_banco_em_memoria_nao_gera_arquivo(url, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert garantir_mundo_local(url) is False
    assert list(tmp_path.iterdir()) == []


def test_banco_externo_nunca_e_tocado():
    # Se tentasse conectar, o teste falharia ou travaria: o endereço não existe.
    assert garantir_mundo_local("postgresql+psycopg://usuario:x@servidor.exemplo/mock") is False


def test_a_fachada_gera_o_mundo_na_primeira_consulta(tmp_path, monkeypatch):
    caminho = tmp_path / "primeira_vez.sqlite"
    monkeypatch.setenv("MOCK_DATABASE_URL", _url(caminho))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    anterior = dados_sinteticos._CONEXAO["engine"]
    dados_sinteticos._CONEXAO["engine"] = None
    try:
        funcionario = dados_sinteticos.buscar_funcionario("F0001")
    finally:
        dados_sinteticos._CONEXAO["engine"].dispose()
        dados_sinteticos._CONEXAO["engine"] = anterior
    assert funcionario["cargo"] == "atendente_n1"
    assert caminho.exists()
