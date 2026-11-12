"""Engine e criação das tabelas do mock. Mexe só na metadata do mock (`BaseMock`)."""

import os
import threading
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from weakref import WeakKeyDictionary

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from . import modelos

VARIAVEL_DO_BANCO = "MOCK_DATABASE_URL"
VARIAVEL_DA_PLATAFORMA = "DATABASE_URL"

# Relativo à raiz do repositório (não ao diretório onde o comando roda).
RAIZ_DO_REPO = Path(__file__).resolve().parent.parent
PASTA_LOCAL = RAIZ_DO_REPO / "dados_locais"
CAMINHO_LOCAL_PADRAO = PASTA_LOCAL / "mock.sqlite"


def sqlite_em_memoria(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url in ("sqlite://", "sqlite:///"))


def criar_engine(url: str) -> Engine:
    """Cria o engine. `hide_parameters` impede que valores apareçam em mensagens de erro."""
    opcoes: dict = {"hide_parameters": True}
    if sqlite_em_memoria(url):
        # Um só banco em memória compartilhado entre threads (senão cada conexão vê um vazio).
        opcoes["poolclass"] = StaticPool
        opcoes["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **opcoes)


_TRAVAS_EM_MEMORIA: WeakKeyDictionary[Engine, threading.RLock] = WeakKeyDictionary()
_TRAVA_DO_CADASTRO = threading.Lock()


def trava_de_acesso(engine: Engine) -> AbstractContextManager:
    """Trava que serializa o uso de um banco SQLite em memória; os demais bancos não precisam.

    O banco em memória tem uma única conexão (StaticPool) dividida entre as threads. Duas threads
    usando essa conexão ao mesmo tempo corrompem o controle do pool (aviso "Double checkin") e
    podem devolver consulta vazia ou erro. Quem abre sessão sobre o engine segura esta trava.
    """
    if not isinstance(engine.pool, StaticPool):
        return nullcontext()
    with _TRAVA_DO_CADASTRO:
        return _TRAVAS_EM_MEMORIA.setdefault(engine, threading.RLock())


PORTA_PADRAO = {"postgresql": 5432, "mysql": 3306, "mariadb": 3306, "mssql": 1433, "oracle": 1521}
APELIDOS_DE_BANCO = {"postgres": "postgresql"}
HOSTS_LOCAIS = {"127.0.0.1", "::1", ""}


def _identidade_do_banco(url: str) -> tuple | None:
    """O que identifica o banco, sem o que muda de escrita (MED-3 da auditoria C).

    Ignora driver, usuário, senha, query string, caixa do host, porta padrão explícita e barra final.
    SQLite vale pelo caminho resolvido (relativo ao diretório atual); em memória não tem identidade.
    Devolve None se a URL não puder ser lida; quem chama cai na comparação de texto, sem repetir a URL.
    """
    try:
        lida = make_url(url)
    except ArgumentError:
        return None
    motor = APELIDOS_DE_BANCO.get(lida.get_backend_name(), lida.get_backend_name())
    if motor == "sqlite":
        caminho = lida.database or ":memory:"
        return None if ":memory:" in caminho else (motor, Path(caminho).resolve())
    host = (lida.host or "").lower()
    host = "localhost" if host in HOSTS_LOCAIS else host
    porta = lida.port or PORTA_PADRAO.get(motor)
    return motor, host, porta, (lida.database or "").strip("/")


def e_o_banco_da_plataforma(url: str, url_da_plataforma: str) -> bool:
    """True se as duas URLs apontam para o mesmo banco, mesmo escritas de jeitos diferentes."""
    if url.strip() == url_da_plataforma.strip():
        return True
    identidade = _identidade_do_banco(url)
    return identidade is not None and identidade == _identidade_do_banco(url_da_plataforma)


def url_padrao() -> str:
    """URL do banco do mock: a variável `MOCK_DATABASE_URL`, se declarada; senão o SQLite local.

    O SQLite local fica em dados_locais/ na raiz do repo (a pasta é criada). `DATABASE_URL` nunca é
    lida: ela aponta para o banco da plataforma, e recriar o mock apaga tabelas (ALTO-2 da auditoria
    A1-A3). Por isso a URL declarada não pode ser igual à da plataforma. Um banco que não é SQLite
    ainda exige `--permitir-banco-externo` no gerador (`mock.gerar`). Uma fonte só: o gerador, a
    fachada das ferramentas e o diretório de funcionários usam esta função.
    """
    declarada = os.environ.get(VARIAVEL_DO_BANCO, "").strip()
    if declarada:
        da_plataforma = os.environ.get(VARIAVEL_DA_PLATAFORMA, "").strip()
        if da_plataforma and e_o_banco_da_plataforma(declarada, da_plataforma):
            raise ValueError(f"{VARIAVEL_DO_BANCO} não pode ser o banco da plataforma.")
        return declarada
    PASTA_LOCAL.mkdir(exist_ok=True)
    return f"sqlite:///{CAMINHO_LOCAL_PADRAO.as_posix()}"


def eh_sqlite(url: str) -> bool:
    """True se a URL é de SQLite. URL malformada levanta `ValueError` sem repetir o texto dela."""
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except ArgumentError:  # a mensagem do SQLAlchemy pode trazer a URL (e a senha) inteira
        raise ValueError("URL de banco inválida.") from None


def criar_tabelas(engine: Engine) -> None:
    """Cria as tabelas do mock que ainda não existem."""
    modelos.BaseMock.metadata.create_all(engine)


def apagar_tabelas(engine: Engine) -> None:
    """Apaga só as tabelas do mock. Tabelas de outras bases ficam intactas."""
    modelos.BaseMock.metadata.drop_all(engine)
