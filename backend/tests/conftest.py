import os

# Os testes usam SQLite em memória: não precisam do Postgres nem do Docker.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
# O .env de quem desenvolve não pode mudar o resultado dos testes: a variável vazia vence o .env,
# porque o dotenv não sobrescreve variável já declarada. Cada teste que precisa dela a define.
os.environ["MOCK_DATABASE_URL"] = ""
# A API sobe com o modelo em modo mock: nenhum teste chama o servidor do professor.
os.environ["LLM_MODO"] = "mock"
# Segredo do token só para os testes (o da máquina de quem desenvolve fica no .env).
os.environ["JWT_SEGREDO"] = "segredo-dos-testes-nao-usar-fora-daqui"

import ipaddress
import socket
from datetime import datetime, time

import pytest

# Proxy do sistema fica de fora: com HTTPS_PROXY no loopback, um pedido para fora passaria pela trava abaixo.
for _variavel in [v for v in os.environ if v.lower() in ("http_proxy", "https_proxy", "all_proxy")]:
    del os.environ[_variavel]

from . import apoio_http, apoio_smtp

# O envio de e-mail vai para um servidor SMTP de teste local, nunca para fora (e o .env não muda isso).
os.environ.update(apoio_smtp.ambiente_da_suite())
# As APIs públicas (ViaCEP e PTAX) vão para um servidor HTTP de teste local, no formato das APIs reais.
os.environ.update(apoio_http.ambiente_da_suite())
# Jira, Slack, Telegram e a leitura de e-mail começam desligados (variável vazia vence o .env de quem roda).
# Cada teste que usa uma delas liga com o servidor de teste local dela (`apoio_integracoes_externas.py`).
os.environ.update(
    dict.fromkeys(
        (
            "JIRA_MODO", "JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJETOS", "JIRA_TIPOS",
            "SLACK_MODO", "SLACK_TOKEN", "SLACK_CANAIS", "SLACK_URL",
            "TELEGRAM_MODO", "TELEGRAM_TOKEN", "TELEGRAM_CHATS", "TELEGRAM_URL",
            "EMAIL_LEITURA_MODO", "EMAIL_IMAP_HOST", "EMAIL_IMAP_PORTA", "EMAIL_IMAP_SEGURANCA",
            "EMAIL_IMAP_USUARIO", "EMAIL_IMAP_SENHA", "EMAIL_IMAP_PASTA",
            "GOOGLE_MODO", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "GOOGLE_URL",
            "MICROSOFT_MODO", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_REDIRECT_URI",
            "MICROSOFT_TENANT", "MICROSOFT_URL", "ESCRITORIO_DOMINIOS", "ANEXOS_MODO", "ANEXOS_DIRETORIO",
        ),
        "",
    )
)

from ferramentas import governanca
from ferramentas.dados_sinteticos import HOJE_DO_MOCK
from ferramentas.integracoes.apis_publicas.conector import CONECTOR as _APIS_PUBLICAS
from ferramentas.integracoes.apis_publicas.conector import FUSO_DA_COTACAO
from ferramentas.integracoes.email_leitura.conector import CONECTOR as _EMAIL_LEITURA
from ferramentas.integracoes.google_workspace.conector import CONECTOR as _GOOGLE
from ferramentas.integracoes.microsoft_365.conector import CONECTOR as _MICROSOFT

# No modo real, a cotação usa o dia de verdade. Na suíte, esse relógio fica parado no HOJE_DO_MOCK: o servidor
# de teste só tem boletins até esse dia, e o resultado não pode depender do dia em que alguém roda os testes.
_APIS_PUBLICAS.agora_real = lambda: datetime.combine(HOJE_DO_MOCK, time(12), FUSO_DA_COTACAO)
# O mesmo para a caixa de e-mail real: o período padrão conta do dia de verdade.
_EMAIL_LEITURA.agora_real = lambda: datetime.combine(HOJE_DO_MOCK, time(12), FUSO_DA_COTACAO)
# E a agenda das contas Google e Microsoft: o período padrão e a data mínima de um evento contam do HOJE_DO_MOCK.
_GOOGLE.agora_real = _MICROSOFT.agora_real = lambda: datetime.combine(HOJE_DO_MOCK, time(12), FUSO_DA_COTACAO)

_CONECTAR = socket.socket.connect
_CONECTAR_EX = socket.socket.connect_ex


def _endereco_local(sock, endereco):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return True
    try:
        return ipaddress.ip_address(endereco[0]).is_loopback
    except ValueError:
        return endereco[0] == "localhost"


def _so_local(sock, endereco):
    if not _endereco_local(sock, endereco):
        raise ConnectionRefusedError("a suíte de testes não sai do computador")
    return _CONECTAR(sock, endereco)


def _so_local_ex(sock, endereco):
    if not _endereco_local(sock, endereco):
        raise ConnectionRefusedError("a suíte de testes não sai do computador")
    return _CONECTAR_EX(sock, endereco)


# Trava de segurança: nenhum teste conecta fora do 127.0.0.1 (nem por engano, nem pelo .env de quem roda).
socket.socket.connect = _so_local
socket.socket.connect_ex = _so_local_ex


@pytest.fixture(autouse=True)
def _destinos_de_registro_limpos():
    governanca.DESTINOS.clear()
    yield
    governanca.DESTINOS.clear()
