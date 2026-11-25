"""Servidor IMAP de teste mínimo (IMAP4rev1, RFC 3501), em socket de verdade, sem TLS (só em 127.0.0.1).

Atende o que o `imaplib` da biblioteca padrão manda para a plataforma: CAPABILITY, LOGIN, EXAMINE/SELECT,
SEARCH (FROM, OR, SINCE e BEFORE), FETCH (RFC822.SIZE, BODY.PEEK[HEADER] e BODY.PEEK[]), NOOP e LOGOUT.
`servidor.comandos` guarda cada comando recebido (sem a senha do LOGIN), para o teste conferir que a pasta foi
aberta só para leitura e que nenhum texto do modelo foi parar no comando.
"""

import re
import socketserver
import threading
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import format_datetime

USUARIO = "caixa@stonelab.example"
SENHA = "senha-de-app-de-teste"
MESES = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def mensagem(remetente, assunto, quando, texto=None, html=None, tamanho_extra=0):
    """Uma mensagem de e-mail em bytes, como o servidor guarda."""
    item = EmailMessage()
    item["From"] = remetente
    item["To"] = USUARIO
    item["Subject"] = assunto
    item["Date"] = format_datetime(quando)
    if texto is not None:
        item.set_content(texto + "x" * tamanho_extra)
    if html is not None:
        if texto is None:
            item.set_content(html, subtype="html")
        else:
            item.add_alternative(html, subtype="html")
    return item.as_bytes()


def _data(texto):
    dia, mes, ano = texto.split("-")
    return date(int(ano), MESES[mes], int(dia))


def _palavras(linha):
    return re.findall(r'"[^"]*"|\S+', linha)


class _Atendimento(socketserver.StreamRequestHandler):
    def _escrever(self, texto):
        self.wfile.write(texto if isinstance(texto, bytes) else texto.encode())

    def handle(self):
        servidor = self.server
        self._escrever("* OK [CAPABILITY IMAP4rev1] servidor de teste pronto\r\n")
        aberta = False
        while True:
            linha = self.rfile.readline()
            if not linha:
                return
            texto = linha.decode().rstrip("\r\n")
            etiqueta, _, resto = texto.partition(" ")
            comando, _, argumentos = resto.partition(" ")
            comando = comando.upper()
            servidor.comandos.append(f"{comando} {argumentos}" if comando != "LOGIN" else "LOGIN")
            if comando == "CAPABILITY":
                self._escrever(f"* CAPABILITY IMAP4rev1\r\n{etiqueta} OK CAPABILITY completed\r\n")
            elif comando == "LOGIN":
                usuario, senha = (p.strip('"') for p in _palavras(argumentos))
                if (usuario, senha) != (USUARIO, SENHA):
                    self._escrever(f"{etiqueta} NO [AUTHENTICATIONFAILED] Invalid credentials\r\n")
                else:
                    self._escrever(f"{etiqueta} OK LOGIN completed\r\n")
            elif comando in ("EXAMINE", "SELECT"):
                pasta = argumentos.strip('"')
                if pasta != servidor.pasta:
                    self._escrever(f"{etiqueta} NO [NONEXISTENT] Unknown Mailbox\r\n")
                else:
                    aberta = True
                    self._escrever(
                        f"* {len(servidor.mensagens)} EXISTS\r\n* 0 RECENT\r\n* FLAGS (\\Seen)\r\n"
                        f"{etiqueta} OK [READ-ONLY] {comando} completed\r\n"
                    )
            elif comando == "SEARCH" and aberta:
                achadas = " ".join(str(n) for n in self._buscar(argumentos))
                self._escrever(f"* SEARCH {achadas}\r\n{etiqueta} OK SEARCH completed\r\n".replace("SEARCH \r", "SEARCH\r"))
            elif comando == "FETCH" and aberta:
                self._buscar_partes(etiqueta, argumentos)
            elif comando == "NOOP":
                self._escrever(f"{etiqueta} OK NOOP completed\r\n")
            elif comando == "LOGOUT":
                self._escrever(f"* BYE saindo\r\n{etiqueta} OK LOGOUT completed\r\n")
                return
            else:
                self._escrever(f"{etiqueta} BAD comando desconhecido\r\n")

    def _buscar(self, argumentos):
        palavras = _palavras(argumentos)
        remetentes, desde, antes = set(), None, None
        for indice, palavra in enumerate(palavras):
            if palavra.upper() == "FROM":
                remetentes.add(palavras[indice + 1].strip('"').lower())
            elif palavra.upper() == "SINCE":
                desde = _data(palavras[indice + 1])
            elif palavra.upper() == "BEFORE":
                antes = _data(palavras[indice + 1])
        achadas = []
        for numero, (remetente, quando, _) in enumerate(self.server.mensagens, 1):
            if remetentes and remetente not in remetentes:
                continue
            if desde and quando.date() < desde or antes and quando.date() >= antes:
                continue
            achadas.append(numero)
        return achadas

    def _buscar_partes(self, etiqueta, argumentos):
        numero, _, partes = argumentos.partition(" ")
        _, _, bruto = self.server.mensagens[int(numero) - 1]
        if "RFC822.SIZE" in partes:
            self._escrever(f"* {numero} FETCH (RFC822.SIZE {len(bruto)})\r\n")
        elif "BODY.PEEK[HEADER]" in partes:
            cabecalho = bruto.split(b"\n\n", 1)[0] + b"\n\n"
            self._escrever(f"* {numero} FETCH (BODY[HEADER] {{{len(cabecalho)}}}\r\n".encode() + cabecalho + b")\r\n")
        elif "BODY.PEEK[]" in partes:
            self._escrever(f"* {numero} FETCH (BODY[] {{{len(bruto)}}}\r\n".encode() + bruto + b")\r\n")
        self._escrever(f"{etiqueta} OK FETCH completed\r\n")


class ServidorImap(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, mensagens=(), pasta="INBOX"):
        """`mensagens`: [(remetente, datetime, bytes)] na ordem de chegada (número 1 é a mais antiga)."""
        super().__init__(("127.0.0.1", 0), _Atendimento)
        self.mensagens = list(mensagens)
        self.pasta = pasta
        self.comandos = []
        self._linha = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    @property
    def porta(self):
        return self.server_address[1]

    def __enter__(self):
        self._linha.start()
        return self

    def __exit__(self, *erro):
        self.shutdown()
        self.server_close()


def ambiente_do_imap(servidor, **extra):
    return {
        "EMAIL_IMAP_HOST": "127.0.0.1",
        "EMAIL_IMAP_PORTA": str(servidor.porta),
        "EMAIL_IMAP_SEGURANCA": "nenhuma",
        "EMAIL_IMAP_USUARIO": USUARIO,
        "EMAIL_IMAP_SENHA": SENHA,
        **extra,
    }


def entrada(remetente, assunto, quando, **corpo):
    """Um item de `ServidorImap(mensagens=...)`: (remetente, momento, bytes)."""
    if isinstance(quando, str):
        quando = datetime.fromisoformat(quando)
    return remetente.lower(), quando, mensagem(remetente, assunto, quando, **corpo)
