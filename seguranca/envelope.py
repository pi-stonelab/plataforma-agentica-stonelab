"""
Decorator de permissão para qualquer função que age sobre um agente.

Uso (quem implementa agentes e ferramentas):

    from seguranca.envelope import exige_permissao
    from seguranca.permissoes import Acao

    @exige_permissao(Acao.EXECUTAR)
    def rodar_agente(usuario, agente, pergunta):
        ...

No back-end, cada pedido tem a sua Plataforma (montada com o perfil lido do banco).
Declare um parâmetro `plataforma` e o decorator usa o que chegou na chamada:

    @exige_permissao(Acao.EXECUTAR)
    def executar_agente(plataforma, usuario, agente, pergunta):
        ...

Regras:
- A função decorada precisa ter parâmetros chamados `usuario` e `agente`
  (posicionais ou nomeados). Se não tiver, o erro aparece já ao importar.
- Qual Plataforma confere a permissão (resolvido a cada chamada):
    1. se a função declara um parâmetro `plataforma`, vale o argumento recebido;
       se ele não for uma Plataforma (ou faltar), a chamada é negada;
    2. senão, vale a Plataforma fixada em `exige_permissao(acao, plataforma=...)`;
    3. senão, a global `PLATAFORMA` (só para a demo e testes simples).
- Se a função declara um parâmetro `execucao_id`, ele vai junto para o evento de auditoria
  (só letras, números, "_" e "-", até 64 caracteres; outro valor nega a chamada).
- Antes de rodar, confere a permissão na Plataforma, que registra a tentativa
  na auditoria, permitida ou negada.
- Se negar, levanta AcessoNegado e a função nem começa.
- Qualquer erro inesperado na checagem também vira AcessoNegado (falha fechada).
- A função decorada ganha o atributo `acao_exigida`, para os testes conferirem
  qual ação ela exige.
"""

from __future__ import annotations

import contextlib
import functools
import inspect

from seguranca.permissoes import Acao, AcessoNegado, Plataforma

# Instância única, usada só pela demo e por testes simples. No back-end, cada pedido monta a
# sua própria Plataforma e a passa no parâmetro `plataforma`; esta global nunca recebe pessoas
# de pedidos reais.
PLATAFORMA = Plataforma()


def _registrar_negacao(plataforma: Plataforma, usuario, acao: Acao, agente) -> None:
    """Melhor esforço: a negação já está decidida, então um erro aqui não muda o resultado."""
    with contextlib.suppress(Exception):
        plataforma._log(usuario, acao.name, getattr(agente, "id", "desconhecido"), False)


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
        recebe_plataforma = "plataforma" in assinatura.parameters

        @functools.wraps(funcao)
        def envelope(*args, **kwargs):
            try:
                chamada = assinatura.bind(*args, **kwargs)
                chamada.apply_defaults()
                usuario = chamada.arguments["usuario"]
                agente = chamada.arguments["agente"]
                execucao_id = chamada.arguments.get("execucao_id")  # opcional; inválido nega
                if recebe_plataforma:
                    p = chamada.arguments["plataforma"]
                else:
                    p = plataforma if plataforma is not None else PLATAFORMA
            except (TypeError, KeyError):
                raise AcessoNegado(f"{funcao.__name__}: chamada sem usuario/agente") from None
            if not isinstance(p, Plataforma):
                raise AcessoNegado(f"{funcao.__name__}: sem plataforma válida para checar")
            try:
                registrado = p.autorizar(usuario, acao, agente, execucao_id)  # registra na auditoria
            except AcessoNegado:
                raise
            except Exception:  # noqa: BLE001 (falha fechada de propósito)
                _registrar_negacao(p, usuario, acao, agente)
                raise AcessoNegado(f"{funcao.__name__}: checagem falhou") from None
            # a função recebe o agente do cadastro, nunca a cópia que o chamador passou
            chamada.arguments["agente"] = registrado
            return funcao(*chamada.args, **chamada.kwargs)

        envelope.acao_exigida = acao  # permite conferir em testes qual ação a função exige
        return envelope

    return decorator
