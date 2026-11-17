"""Servidor SMTP de teste, em socket de verdade, para os testes do `ferramentas/email_smtp.py`.

Fala o mínimo do protocolo (EHLO, AUTH PLAIN, MAIL, RCPT, DATA, RSET, NOOP, QUIT) e guarda os comandos e as
mensagens recebidas. Não oferece STARTTLS, de propósito: serve para provar que o cliente não segue sem TLS.
O `modo` escolhe uma falha: "recusar_destino" (550 no RCPT), "cair_no_data" (fecha a conexão depois de receber
o texto, sem responder) e "lento_no_data" (demora `atraso` segundos para responder ao fim do texto).
"""

import base64
import socket
import socketserver
import threading
import time
from email import message_from_bytes, policy

USUARIO = "plataforma"
SENHA = "senha-de-teste"  # sintética, só deste servidor local
REMETENTE_DA_SUITE = "plataforma@stonelab.example"
_DA_SUITE = []


class _Atendimento(socketserver.StreamRequestHandler):
    def responder(self, linha):
        self.wfile.write(f"{linha}\r\n".encode())

    def handle(self):
        servidor = self.server
        self.responder("220 teste ESMTP")
        while True:
            linha = self.rfile.readline()
            if not linha:
                return
            comando = linha.decode(errors="replace").strip()
            servidor.comandos.append(comando.split(" ", 1)[0].upper())
            if not self.tratar(servidor, comando):
                return

    def tratar(self, servidor, comando):
        verbo = comando.split(" ", 1)[0].upper()
        if verbo in ("EHLO", "HELO"):
            self.wfile.write(b"250-teste\r\n250-AUTH PLAIN\r\n250 8BITMIME\r\n")
        elif verbo == "AUTH":
            esperado = base64.b64encode(f"\0{USUARIO}\0{SENHA}".encode()).decode()
            self.responder("235 ok" if comando.endswith(esperado) else "535 recusado")
        elif verbo == "RCPT" and servidor.modo == "recusar_destino":
            self.responder("550 destino recusado")
        elif verbo in ("MAIL", "RCPT", "RSET", "NOOP"):
            self.responder("250 ok")
        elif verbo == "DATA":
            return self.receber_texto(servidor)
        elif verbo == "QUIT":
            self.responder("221 tchau")
            return False
        else:
            self.responder("502 comando desconhecido")
        return True

    def receber_texto(self, servidor):
        self.responder("354 manda")
        linhas = []
        while (linha := self.rfile.readline()) not in (b".\r\n", b""):
            linhas.append(linha)
        if servidor.modo == "cair_no_data":
            self.connection.shutdown(socket.SHUT_RDWR)
            return False
        if servidor.modo == "lento_no_data":
            time.sleep(servidor.atraso)
        servidor.mensagens.append(message_from_bytes(b"".join(linhas), policy=policy.default))
        self.responder("250 recebido")
        return True


class ServidorSmtp(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, modo="", atraso=0.0):
        super().__init__(("127.0.0.1", 0), _Atendimento)
        self.modo = modo
        self.atraso = atraso
        self.comandos = []
        self.mensagens = []

    @property
    def porta(self):
        return self.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return self

    def __exit__(self, *_):
        self.shutdown()
        self.server_close()


def porta_fechada():
    """Uma porta local em que ninguém escuta."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def servidor_da_suite():
    """O servidor que a suíte inteira usa por padrão (o `conftest` aponta o .env para ele). Sobe uma vez."""
    if not _DA_SUITE:
        _DA_SUITE.append(ServidorSmtp().__enter__())
    return _DA_SUITE[0]


def ambiente_da_suite():
    return {
        "EMAIL_SMTP_HOST": "127.0.0.1",
        "EMAIL_SMTP_PORTA": str(servidor_da_suite().porta),
        "EMAIL_SMTP_SEGURANCA": "nenhuma",
        "EMAIL_SMTP_USUARIO": "",
        "EMAIL_SMTP_SENHA": "",
        "EMAIL_REMETENTE": REMETENTE_DA_SUITE,
        "EMAIL_DESTINO_TESTE": "",
    }


def enviadas():
    """O que chegou ao servidor da suíte, como dicts curtos."""
    return [
        {"de": m["From"], "para": m["To"], "assunto": m["Subject"], "corpo": m.get_content().replace("\r\n", "\n").rstrip("\n")}
        for m in servidor_da_suite().mensagens
    ]


def limpar_enviadas():
    servidor_da_suite().mensagens.clear()
