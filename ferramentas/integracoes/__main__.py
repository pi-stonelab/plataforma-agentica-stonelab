"""Estado e teste das integrações pelo terminal, na raiz do repositório:

    python -m ferramentas.integracoes estado              # uma linha por integração, sem segredo
    MODO_TERMINAL=1 python -m ferramentas.integracoes testar apis_publicas

`testar` chama o serviço de verdade (com as credenciais do .env), sem dado de lojista, e diz se respondeu.
As mensagens dizem como corrigir; nenhuma mostra valor do .env.
"""

import argparse
import os
import sys

if not __package__:  # rodado como arquivo: a pasta `integracoes/email/` esconderia o módulo `email` do Python
    sys.exit("Rode da raiz do repositório: python -m ferramentas.integracoes estado")

from ferramentas import email_smtp
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import conector, estado_integracoes, nomes
from ferramentas.integracoes.cliente_http import CredencialRecusada
from ferramentas.integracoes.conector import ConfiguracaoInvalida, IntegracaoDesligada

SAUDES_EM_PORTUGUES = {
    "ok": "funcionando",
    "sem_chamadas": "sem chamadas ainda",
    "pausada": "pausada por falhas (tenta de novo em 1 min)",
    "indisponivel": "indisponível",
    "configuracao_invalida": "configuração inválida",
    "desligada": "desligada",
}
MODOS_EM_PORTUGUES = {"real": "real", "simulado": "simulado (dados fixos)", "desligado": "desligado"}
MODO_DO_INTERNO = "mock (Stone simulada)"
CABECALHO = f"{'integração':<17} {'tipo':<8} {'modo':<23} saúde"


def _linhas(item, ambiente):
    saude = SAUDES_EM_PORTUGUES[item["saude"]]
    modo = MODO_DO_INTERNO if item["tipo"] == "interno" else MODOS_EM_PORTUGUES[item["modo"]]
    linhas = [f"{item['nome']:<17} {item['tipo']:<8} {modo:<23} {saude}"]
    linhas += [f"{'':<17} {'':<8} {'- ' + s['nome']:<23} {SAUDES_EM_PORTUGUES[s['saude']]}" for s in item["servicos"]]
    problema = conector(item["nome"]).problema_de_configuracao(ambiente)
    if problema and item["tipo"] == "externo":
        linhas.append(f"{'':<17} {problema}")
    return linhas


def _sem_resposta(alvo, erro):
    if isinstance(erro, CredencialRecusada):
        return f"{alvo.rotulo}: o serviço recusou a credencial do .env (token ou senha errados ou vencidos)."
    if isinstance(erro, email_smtp.EnvioIndisponivel):
        return f"{alvo.rotulo}: {email_smtp.explicar_falha(erro)}"
    dica = getattr(alvo, "dica_sem_rede", "") or "Confira a internet e o endereço no .env."
    return f"Não consegui falar com {alvo.rotulo}. {dica}"


def principal(argumentos=None, ambiente=os.environ, escrever=print):
    analisador = argparse.ArgumentParser(description="Estado e teste das integrações.")
    comandos = analisador.add_subparsers(dest="comando", required=True)
    comandos.add_parser("estado", help="lista as integrações, o modo e a saúde")
    teste = comandos.add_parser("testar", help="chama o serviço de verdade, sem dado de lojista")
    teste.add_argument("integracao", choices=nomes())
    pedido = analisador.parse_args(argumentos)
    if pedido.comando == "estado":
        escrever(CABECALHO)
        for item in estado_integracoes(ambiente):
            for linha in _linhas(item, ambiente):
                escrever(linha)
        return
    if ambiente.get("MODO_TERMINAL") != "1":  # O12: ferramenta de desenvolvimento, só local
        raise SystemExit("Modo terminal desligado. Defina MODO_TERMINAL=1 para usar.")
    alvo = conector(pedido.integracao)
    problema = alvo.problema_de_configuracao(ambiente)
    if problema:
        raise SystemExit(f"{alvo.rotulo}: {problema}")
    try:
        escrever(f"{alvo.rotulo} (modo {alvo.modo(ambiente)}): {alvo.testar(ambiente)}")
    except (ConfiguracaoInvalida, email_smtp.ConfiguracaoInvalida, IntegracaoDesligada) as erro:
        raise SystemExit(f"{alvo.rotulo}: {erro}") from None
    except ErroFerramenta as erro:
        raise SystemExit(f"{alvo.rotulo}: {erro.mensagem}") from None
    except (ConnectionError, TimeoutError) as erro:
        raise SystemExit(_sem_resposta(alvo, erro)) from None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    principal()
