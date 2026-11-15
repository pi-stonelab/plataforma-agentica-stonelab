"""Escrita em duas fases: o agente monta a prévia e quem pediu confirma (KAN-52, passo 7).

1. O agente usa a ferramenta (USAR). `FerramentaComConfirmacao` valida, monta o conteúdo e guarda um
   pedido aqui, aguardando confirmação. Nada sai da plataforma nesta fase.
2. A pessoa revisa a prévia fora do agente (interface ou terminal) e chama `confirmar` ou `cancelar`.

O modelo nunca confirma: não existe ferramenta para isso, e `confirmar` exige o mesmo funcionário que
pediu, revalidado pela governança na hora. O conteúdo é dado de lojista (LGPD): só existe enquanto o
pedido espera e é apagado ao confirmar, cancelar ou expirar. Registro e logs recebem só metadados.

`status` no registro de chamadas: "iniciada" e "ok" ao montar a prévia (pela `Ferramenta.executar`),
"iniciada" e "ok" (ou "erro") ao confirmar, "cancelada" e "expirada".
[A FAZER (Enrico, QA, KAN-38): contar pedidos aguardando, confirmados, cancelados e expirados a partir
do registro e avisar quando um expirar sem resposta]
"""

import logging
import secrets
import string
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ferramentas import governanca, mascara
from ferramentas.base import (
    MENSAGEM_REGISTRO,
    MENSAGEM_REGISTRO_FINAL,
    ErroFerramenta,
    Ferramenta,
    montar_registro,
    resposta,
)

AGUARDANDO = "aguardando_confirmacao"
VALIDADE = timedelta(minutes=15)
LIMITE_POR_USUARIO = 5
LIMITE_PEDIDOS = 1000
TAMANHO_DO_ID = 10
LETRAS_DO_ID = string.ascii_uppercase  # sem dígitos: a máscara de texto livre não confunde com CPF
CAMPOS_DO_CONTEXTO = ("execucao_id", "passo", "agente_id")
MENSAGEM_NAO_ENCONTRADO = "Prévia não encontrada, expirada ou já usada."
MENSAGEM_FORA_DO_AR = "Integração fora do ar. Nada foi enviado; peça uma nova prévia."

# [A FAZER (Marcelo e Isabel, back-end, KAN-60): guardar os pedidos numa tabela (sem o conteúdo
# depois de resolvidos) e criar as rotas de listar, confirmar e cancelar, chamando `pendentes`,
# `confirmar` e `cancelar` com o usuário do login]
PEDIDOS = {}
TRAVA_DOS_PEDIDOS = threading.Lock()
logger = logging.getLogger(__name__)


def agora():
    """Relógio dos pedidos, em UTC. Os testes trocam esta função para o tempo passar."""
    return datetime.now(UTC)


@dataclass
class Pedido:
    confirmacao_id: str
    ferramenta: Ferramenta
    id_usuario: str
    contexto: dict
    conteudo: dict  # o que `efetivar` precisa (dado de lojista em claro); apagado ao resolver
    previa: dict  # o que a pessoa revisa, já mascarado
    expira_em: datetime


class FerramentaComConfirmacao(Ferramenta):
    """Ferramenta de escrita que nunca age na chamada do agente. A subclasse escreve dois métodos:

    - `montar(argumentos, usuario)`: valida, busca o que precisa e devolve `(conteudo, previa)`.
      Não age.
    - `efetivar(conteudo, usuario)`: o efeito de verdade. Só `confirmar` chama. Devolve um dict curto.
    """

    acesso = "escrita"

    def montar(self, argumentos, usuario):
        raise ErroFerramenta("ferramenta_inativa", "Ferramenta ainda sem lógica.")

    def efetivar(self, conteudo, usuario):
        raise ErroFerramenta("ferramenta_inativa", "Ferramenta ainda sem lógica.")

    def rodar_com_contexto(self, argumentos, usuario, contexto):
        conteudo, previa = self.montar(argumentos, usuario)
        return _como_mostrar(_guardar(self, usuario, contexto, conteudo, previa))


def _como_mostrar(pedido):
    return {
        "confirmacao_id": pedido.confirmacao_id,
        "situacao": AGUARDANDO,
        "expira_em": pedido.expira_em.isoformat(timespec="minutes"),
        **pedido.previa,
    }


def _novo_id():
    while True:
        confirmacao_id = "CONF-" + "".join(secrets.choice(LETRAS_DO_ID) for _ in range(TAMANHO_DO_ID))
        if confirmacao_id not in PEDIDOS:
            return confirmacao_id


def _guardar(ferramenta, usuario, contexto, conteudo, previa):
    contexto = contexto if isinstance(contexto, dict) else {}
    with TRAVA_DOS_PEDIDOS:
        _expirar_vencidos()
        do_usuario = sum(p.id_usuario == usuario.id_usuario for p in PEDIDOS.values())
        if do_usuario >= LIMITE_POR_USUARIO or len(PEDIDOS) >= LIMITE_PEDIDOS:
            raise ErroFerramenta("integracao_indisponivel", "Há prévias demais esperando confirmação.")
        pedido = Pedido(
            confirmacao_id=_novo_id(),
            ferramenta=ferramenta,
            id_usuario=usuario.id_usuario,
            contexto={campo: contexto.get(campo) for campo in CAMPOS_DO_CONTEXTO},
            conteudo=conteudo,
            previa=mascara.mascarar(previa, ferramenta.categorias_dados),
            expira_em=agora() + VALIDADE,
        )
        PEDIDOS[pedido.confirmacao_id] = pedido
    return pedido


def _registrar(pedido, usuario, resultado, camada, inicio):
    registro = montar_registro(pedido.ferramenta, usuario, pedido.contexto, resultado, camada, inicio)
    governanca.registrar(registro)


def _expirar_vencidos():
    """Tira os pedidos vencidos e apaga o conteúdo. Chamada com a trava já tomada."""
    vencidos = [p for p in PEDIDOS.values() if p.expira_em <= agora()]
    for pedido in vencidos:
        del PEDIDOS[pedido.confirmacao_id]
        pedido.conteudo.clear()
        dono = SimpleNamespace(id_usuario=pedido.id_usuario)
        with suppress(governanca.RegistroIndisponivel):  # o pedido expira mesmo sem rastro: nada age
            _registrar(pedido, dono, resposta("expirada"), None, time.monotonic())


def _retirar(confirmacao_id, usuario):
    """Tira o pedido da fila se ele é do `usuario` (uso único). Pedido de outra pessoa fica onde está."""
    with TRAVA_DOS_PEDIDOS:
        _expirar_vencidos()
        pedido = PEDIDOS.get(confirmacao_id) if isinstance(confirmacao_id, str) else None
        if pedido is None:
            return None
        if pedido.id_usuario != getattr(usuario, "id_usuario", None):
            negado = resposta("erro", tipo_erro="nao_encontrado")
            with suppress(governanca.RegistroIndisponivel):  # tentativa de outra pessoa fica no rastro
                _registrar(pedido, usuario, negado, "usuario", time.monotonic())
            return None
        return PEDIDOS.pop(confirmacao_id)


def _devolver(pedido):
    with TRAVA_DOS_PEDIDOS:
        PEDIDOS[pedido.confirmacao_id] = pedido


def pendentes(usuario):
    """Prévias que esperam a confirmação do `usuario`, para a interface ou o terminal mostrarem."""
    with TRAVA_DOS_PEDIDOS:
        _expirar_vencidos()
        do_usuario = [p for p in PEDIDOS.values() if p.id_usuario == getattr(usuario, "id_usuario", None)]
        return [{"ferramenta": p.ferramenta.nome, **_como_mostrar(p)} for p in do_usuario]


def confirmar(confirmacao_id, usuario):
    """Roda o efeito do pedido, se ele é de quem confirma e o acesso continua valendo. Uso único."""
    inicio = time.monotonic()
    pedido = _retirar(confirmacao_id, usuario)
    if pedido is None:
        return resposta("erro", None, MENSAGEM_NAO_ENCONTRADO, "nao_encontrado")
    ferramenta = pedido.ferramenta
    if governanca.motivo_bloqueio(ferramenta, usuario) is not None or not ferramenta.esta_ativa():
        pedido.conteudo.clear()
        negado = resposta("erro", None, "Acesso não permitido.", "permissao_negada")
        with suppress(governanca.RegistroIndisponivel):
            _registrar(pedido, usuario, negado, "usuario", inicio)
        return negado
    try:
        _registrar(pedido, usuario, resposta("iniciada"), None, inicio)
    except governanca.RegistroIndisponivel:  # O9: sem rastro da intenção, nada é enviado
        _devolver(pedido)
        return resposta("erro", None, MENSAGEM_REGISTRO, "integracao_indisponivel")
    try:
        dados = mascara.mascarar(ferramenta.efetivar(pedido.conteudo, usuario), ferramenta.categorias_dados)
        resultado = resposta("ok", dados, "Enviado.")
    except ErroFerramenta as erro:
        resultado = resposta("erro", None, erro.mensagem, erro.tipo_erro)
    except (ConnectionError, TimeoutError):
        resultado = resposta("erro", None, MENSAGEM_FORA_DO_AR, "integracao_indisponivel")
    except Exception as erro:  # noqa: BLE001 (só o tipo vai ao log: a mensagem pode ter o e-mail)
        logger.error("confirmação falhou: ferramenta=%s tipo=%s", ferramenta.nome, type(erro).__name__)
        resultado = resposta("erro", None, "Erro interno.", "erro_interno")
    finally:
        pedido.conteudo.clear()
    try:
        _registrar(pedido, usuario, resultado, None, inicio)
    except governanca.RegistroIndisponivel:
        return resposta("erro", None, MENSAGEM_REGISTRO_FINAL, "integracao_indisponivel")
    return resultado


def cancelar(confirmacao_id, usuario):
    """Descarta a prévia sem agir. Só quem pediu descarta."""
    pedido = _retirar(confirmacao_id, usuario)
    if pedido is None:
        return resposta("erro", None, MENSAGEM_NAO_ENCONTRADO, "nao_encontrado")
    pedido.conteudo.clear()
    with suppress(governanca.RegistroIndisponivel):  # descartar não age: vale mesmo sem rastro
        _registrar(pedido, usuario, resposta("cancelada"), None, time.monotonic())
    return resposta("ok", {"confirmacao_id": pedido.confirmacao_id, "situacao": "cancelada"}, "Descartado.")


def limpar():
    """Esvazia a fila sem registrar (testes e reinício da demo)."""
    with TRAVA_DOS_PEDIDOS:
        for pedido in PEDIDOS.values():
            pedido.conteudo.clear()
        PEDIDOS.clear()
