"""
Decorator de permissão para qualquer função que age sobre um agente.

Uso (quem implementa agentes e ferramentas):

    from seguranca.envelope import exige_permissao
    from seguranca.permissoes import Acao

    @exige_permissao(Acao.EXECUTAR)
    def rodar_agente(usuario, agente, pergunta):
        ...

    @exige_permissao(Acao.EXECUTAR)
    def chamar_ferramenta(usuario, agente, nome_ferramenta, argumentos):
        ...

Regras:
- A função decorada precisa ter parâmetros chamados `usuario` e `agente`
  (posicionais ou nomeados). Se não tiver, o erro aparece já ao importar.
- Antes de rodar, confere a permissão na Plataforma, que registra a tentativa
  na auditoria, permitida ou negada.
- Se negar, levanta AcessoNegado e a função nem começa.
- Qualquer erro inesperado na checagem também vira AcessoNegado (falha fechado).
"""

from __future__ import annotations

import functools
import inspect

from seguranca.permissoes import Acao, AcessoNegado, Plataforma

# Instância única, compartilhada por todo o projeto. Cadastre usuários e agentes
# nela (seguranca.envelope.PLATAFORMA) para que o decorator os encontre.
PLATAFORMA = Plataforma()


def exige_permissao(acao: Acao, plataforma: Plataforma | None = None):
    """Decorator: só deixa a função rodar se `usuario` pode fazer `acao` em `agente`."""
    if not isinstance(acao, Acao):
        raise TypeError("exige_permissao precisa de uma Acao, ex.: Acao.EXECUTAR")

    def decorator(funcao):
        assinatura = inspect.signature(funcao)
        faltando = {"usuario", "agente"} - set(assinatura.parameters)
        if faltando:
            raise TypeError(
                f"{funcao.__name__} precisa dos parâmetros: {', '.join(sorted(faltando))}"
            )

        @functools.wraps(funcao)
        def envelope(*args, **kwargs):
            p = plataforma or PLATAFORMA
            try:
                chamada = assinatura.bind(*args, **kwargs)
                usuario = chamada.arguments["usuario"]
                agente = chamada.arguments["agente"]
            except (TypeError, KeyError):
                raise AcessoNegado(f"{funcao.__name__}: chamada sem usuario/agente") from None
            try:
                p.autorizar(usuario, acao, agente)  # registra na auditoria
            except AcessoNegado:
                raise
            except Exception:  # noqa: BLE001 (falha fechado de propósito)
                p._log(usuario, acao.name, getattr(agente, "id", agente), False)
                raise AcessoNegado(f"{funcao.__name__}: checagem falhou") from None
            return funcao(*args, **kwargs)

        envelope.acao_exigida = acao  # permite conferir em testes qual ação a função exige
        return envelope

    return decorator
