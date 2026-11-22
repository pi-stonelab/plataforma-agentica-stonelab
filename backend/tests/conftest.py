import os

# Os testes usam SQLite em memória: não precisam do Postgres nem do Docker.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
# O .env de quem desenvolve não pode mudar o resultado dos testes: a variável vazia vence o .env,
# porque o dotenv não sobrescreve variável já declarada. Cada teste que precisa dela a define.
os.environ["MOCK_DATABASE_URL"] = ""

import ipaddress
import socket

from . import apoio_http, apoio_smtp

# O envio de e-mail vai para um servidor SMTP de teste local, nunca para fora (e o .env não muda isso).
os.environ.update(apoio_smtp.ambiente_da_suite())
# As APIs públicas (ViaCEP e PTAX) vão para um servidor HTTP de teste local, no formato das APIs reais.
os.environ.update(apoio_http.ambiente_da_suite())

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
