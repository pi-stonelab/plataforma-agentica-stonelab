"""Envio de e-mail por SMTP (`ferramentas/email_smtp.py`), visto como integração.

O modo vem da configuração: com `EMAIL_SMTP_HOST`, `real`; sem, `desligado` (não há caixa simulada). O `testar`
conecta, cifra e faz o login, sem mandar e-mail. O envio continua inteiro em `email_smtp.enviar`.
"""

import os

from mock import falhas

from ferramentas import email_smtp
from ferramentas.integracoes.conector import Conector, IntegracaoDesligada
from ferramentas.integracoes.registro import registrar


class ConectorEmail(Conector):
    nome = "email"
    rotulo = "E-mail (SMTP)"
    variaveis = (
        "EMAIL_SMTP_HOST",
        "EMAIL_SMTP_PORTA",
        "EMAIL_SMTP_SEGURANCA",
        "EMAIL_SMTP_USUARIO",
        "EMAIL_SMTP_SENHA",
        "EMAIL_REMETENTE",
        "EMAIL_DESTINO_TESTE",
    )

    mensagem_desligada = "O envio de e-mail não está ligado nesta plataforma."
    como_ligar = "defina EMAIL_SMTP_HOST no .env (veja o .env.example)"

    def modo(self, ambiente=os.environ):
        return "real" if ambiente.get("EMAIL_SMTP_HOST", "").strip() else "desligado"

    def conferir_configuracao(self, ambiente=os.environ):
        email_smtp.configuracao(ambiente)  # levanta email_smtp.ConfiguracaoInvalida com o nome da variável

    def fora_do_ar(self):
        return falhas.fora_do_ar("email")

    def testar(self, ambiente=os.environ):
        config = email_smtp.configuracao(ambiente)
        if config is None:
            raise IntegracaoDesligada(email_smtp.MENSAGEM_DESLIGADO_NO_TERMINAL)
        email_smtp.verificar_conexao(config)
        return "O servidor SMTP respondeu e aceitou o login. Nenhum e-mail foi enviado."


CONECTOR = registrar(ConectorEmail())
