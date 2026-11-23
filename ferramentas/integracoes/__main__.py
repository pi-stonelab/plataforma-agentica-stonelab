"""Estado e teste das integrações pelo terminal, na raiz do repositório:

    python -m ferramentas.integracoes estado              # uma linha por integração, sem segredo
    MODO_TERMINAL=1 python -m ferramentas.integracoes testar apis_publicas

`testar` chama o serviço de verdade (com as credenciais do .env), sem dado de lojista, e diz se respondeu.
"""

import argparse
import os

from ferramentas import email_smtp
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import conector, estado_integracoes, nomes
from ferramentas.integracoes.conector import ConfiguracaoInvalida, IntegracaoDesligada


def _linha(item):
    configurado = "configurada" if item["configurado"] else "sem configuração"
    return f"{item['nome']:<17} {item['tipo']:<8} {item['modo']:<10} {item['saude']:<13} {configurado}"


def principal(argumentos=None, ambiente=os.environ, escrever=print):
    analisador = argparse.ArgumentParser(description="Estado e teste das integrações.")
    comandos = analisador.add_subparsers(dest="comando", required=True)
    comandos.add_parser("estado", help="lista as integrações, o modo e a saúde")
    teste = comandos.add_parser("testar", help="chama o serviço de verdade, sem dado de lojista")
    teste.add_argument("integracao", choices=nomes())
    pedido = analisador.parse_args(argumentos)
    if pedido.comando == "estado":
        for item in estado_integracoes(ambiente):
            escrever(_linha(item))
        return
    if ambiente.get("MODO_TERMINAL") != "1":  # O12: ferramenta de desenvolvimento, só local
        raise SystemExit("Modo terminal desligado. Defina MODO_TERMINAL=1 para usar.")
    alvo = conector(pedido.integracao)
    try:
        escrever(f"{alvo.rotulo} (modo {alvo.modo(ambiente)}): {alvo.testar(ambiente)}")
    except (ConfiguracaoInvalida, email_smtp.ConfiguracaoInvalida, IntegracaoDesligada) as erro:
        raise SystemExit(f"{alvo.rotulo}: {erro}") from None
    except ErroFerramenta as erro:
        raise SystemExit(f"{alvo.rotulo}: {erro.mensagem}") from None
    except (ConnectionError, TimeoutError) as erro:
        raise SystemExit(f"{alvo.rotulo} não respondeu ({type(erro).__name__}).") from None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    principal()
