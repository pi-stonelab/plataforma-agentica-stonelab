"""Escrita em duas fases: o agente monta a prévia e quem pediu confirma (KAN-52, passo 7).

1. O agente usa a ferramenta (USAR). `FerramentaComConfirmacao` valida, monta o conteúdo e guarda um
   pedido aqui, aguardando confirmação. Nada sai da plataforma nesta fase.
2. A pessoa revisa a prévia fora do agente (interface ou terminal) e chama `confirmar` ou `cancelar`.

O modelo nunca confirma: não existe ferramenta para isso, e `confirmar` exige o mesmo funcionário que
pediu, revalidado pela governança na hora. O conteúdo é dado de lojista (LGPD): só existe enquanto o
pedido espera e é apagado ao confirmar, cancelar ou expirar. Registro e logs recebem só metadados.

A prévia só fica visível depois que a resposta chega ao agente (`concluir`): se o registro final da fase 1 falha,
ela sai da fila e o agente pode pedir de novo sem duplicar.

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
from zoneinfo import ZoneInfo

from ferramentas import governanca, mascara
from ferramentas.base import (
    MENSAGEM_REGISTRO,
    MENSAGEM_REGISTRO_FINAL,
    EfeitoIncerto,
    ErroFerramenta,
    Ferramenta,
    montar_registro,
    resposta,
)

AGUARDANDO = "aguardando_confirmacao"
# Situações do objeto `Confirmacao` do contrato do front (frontend/CONTRATO_API.md §4.9).
PENDENTE = "pendente"
APROVADA = "aprovada"
CANCELADA = "cancelada"
VALIDADE = timedelta(minutes=15)
# Quanto tempo a decisão (aprovada ou cancelada) fica lembrada, para o back-end responder 409 em vez de 404.
LEMBRAR_DECISAO = timedelta(hours=1)
FUSO_DA_INTERFACE = ZoneInfo("America/Sao_Paulo")  # `expira_em` sai no horário de Brasília (ISO com -03:00)
LIMITE_POR_USUARIO = 5
LIMITE_PEDIDOS = 1000
TAMANHO_DO_ID = 10
LETRAS_DO_ID = string.ascii_uppercase  # sem dígitos: a máscara de texto livre não confunde com CPF
CAMPOS_DO_CONTEXTO = ("execucao_id", "passo", "agente_id")
MENSAGEM_NAO_ENCONTRADO = "Prévia não encontrada, expirada ou já usada."
MENSAGEM_PREVIAS_DA_PESSOA = (
    f"Você já tem {LIMITE_POR_USUARIO} prévias abertas. Confirme ou descarte uma antes de pedir outra."
)
MENSAGEM_JA_DECIDIDA = {APROVADA: "Esta prévia já foi confirmada.", CANCELADA: "Esta prévia já foi descartada."}
MENSAGEM_FORA_DO_AR = "Integração fora do ar. Nada foi enviado; peça uma nova prévia."
MENSAGEM_EFEITO_INCERTO = (
    "O servidor de destino não confirmou: a ação pode ter sido feita. Confira antes de pedir uma nova prévia."
)

# [A FAZER (Marcelo e Isabel, back-end, KAN-60): guardar os pedidos numa tabela (sem o conteúdo
# depois de resolvidos) e criar as rotas de listar, confirmar e cancelar, chamando `pendentes`,
# `confirmar` e `cancelar` com o usuário do login]
PEDIDOS = {}
# confirmacao_id -> (id_usuario, situação, quando). Só isso: nada do conteúdo nem da prévia.
DECIDIDAS = {}
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
    liberado: bool = False  # só vira True quando a resposta com o `confirmacao_id` chega ao agente


class FerramentaComConfirmacao(Ferramenta):
    """Ferramenta de escrita que nunca age na chamada do agente. A subclasse escreve dois métodos:

    - `montar(argumentos, usuario)`: valida, busca o que precisa e devolve `(conteudo, previa)`.
      Não age.
    - `efetivar(conteudo, usuario)`: o efeito de verdade. Só `confirmar` chama. Devolve um dict curto.
    """

    acesso = "escrita"
    age_ao_executar = False  # a fase 1 só guarda a prévia; o efeito é do `confirmar`
    campos_liberados = ("confirmacao_id", "expira_em")  # a subclasse soma os campos da sua prévia
    titulo = ""  # como a interface chama a ação ("Enviar e-mail")
    mensagem_feito = "Enviado."  # a frase da confirmação que deu certo ("Chamado aberto.")
    rotulos_da_previa = {}  # campo da prévia -> rótulo, na ordem em que a interface mostra

    def texto_do_campo(self, campo, valor):
        """O valor de um campo da prévia (já mascarada) como texto para a interface."""
        if isinstance(valor, dict):
            return " · ".join(str(item) for item in valor.values() if item not in (None, ""))
        if isinstance(valor, (list, tuple)):
            return ", ".join(str(item) for item in valor)
        return "" if valor is None else str(valor)

    def montar(self, argumentos, usuario):
        raise ErroFerramenta("ferramenta_inativa", "Ferramenta ainda sem lógica.")

    def efetivar(self, conteudo, usuario):
        raise ErroFerramenta("ferramenta_inativa", "Ferramenta ainda sem lógica.")

    def rodar_com_contexto(self, argumentos, usuario, contexto):
        conteudo, previa = self.montar(argumentos, usuario)
        return _como_mostrar(_guardar(self, usuario, contexto, conteudo, previa))

    def concluir(self, dados, entregue):
        """Fim da fase 1. Entregue: a prévia fica visível e confirmável. Não entregue (a resposta não
        chegou ao agente): ela sai da fila, para ninguém confirmar o que o agente achou que falhou e para
        uma nova tentativa não duplicar."""
        confirmacao_id = dados.get("confirmacao_id") if isinstance(dados, dict) else None
        if entregue:
            _liberar(confirmacao_id)
        else:
            _tirar_da_fila(confirmacao_id)


def _como_mostrar(pedido):
    return {
        "confirmacao_id": pedido.confirmacao_id,
        "situacao": AGUARDANDO,
        "expira_em": pedido.expira_em.astimezone(FUSO_DA_INTERFACE).isoformat(timespec="minutes"),
        **pedido.previa,
    }


def _novo_id():
    while True:
        confirmacao_id = "CONF-" + "".join(secrets.choice(LETRAS_DO_ID) for _ in range(TAMANHO_DO_ID))
        if confirmacao_id not in PEDIDOS:
            return confirmacao_id


def _guardar(ferramenta, usuario, contexto, conteudo, previa):
    contexto = contexto if isinstance(contexto, dict) else {}
    vencidos = []
    try:
        with TRAVA_DOS_PEDIDOS:
            vencidos = _recolher_vencidos()
            do_usuario = sum(p.id_usuario == usuario.id_usuario for p in PEDIDOS.values())
            if do_usuario >= LIMITE_POR_USUARIO:
                raise ErroFerramenta("integracao_indisponivel", MENSAGEM_PREVIAS_DA_PESSOA)
            if len(PEDIDOS) >= LIMITE_PEDIDOS:
                raise ErroFerramenta("integracao_indisponivel", "Há prévias demais esperando confirmação na plataforma.")
            pedido = Pedido(
                confirmacao_id=_novo_id(),
                ferramenta=ferramenta,
                id_usuario=usuario.id_usuario,
                contexto={campo: contexto.get(campo) for campo in CAMPOS_DO_CONTEXTO},
                conteudo=conteudo,
                previa=mascara.mascarar(previa, ferramenta.categorias_dados, ferramenta.campos_liberados),
                expira_em=agora() + VALIDADE,
            )
            PEDIDOS[pedido.confirmacao_id] = pedido
    finally:
        _registrar_expirados(vencidos)
    return pedido


def _registrar(pedido, usuario, resultado, camada, inicio):
    registro = montar_registro(pedido.ferramenta, usuario, pedido.contexto, resultado, camada, inicio)
    governanca.registrar(registro)


def _recolher_vencidos():
    """Tira da fila os pedidos vencidos e apaga o conteúdo. Chamada com a trava tomada.

    Devolve os pedidos tirados: o registro deles é gravado depois, fora da trava, por `_registrar_expirados`.
    """
    vencidos = [p for p in PEDIDOS.values() if p.expira_em <= agora()]
    for pedido in vencidos:
        del PEDIDOS[pedido.confirmacao_id]
        pedido.conteudo.clear()
    return vencidos


def _registrar_expirados(vencidos):
    """Grava o "expirada" de cada pedido, sem a trava da fila: o destino pode ser lento ou voltar à fila."""
    for pedido in vencidos:
        dono = SimpleNamespace(id_usuario=pedido.id_usuario)
        with suppress(governanca.RegistroIndisponivel):  # o pedido expira mesmo sem rastro: nada age
            _registrar(pedido, dono, resposta("expirada"), None, time.monotonic())


def _retirar(confirmacao_id, usuario):
    """Tira o pedido da fila se ele é do `usuario` (uso único). Pedido de outra pessoa fica onde está."""
    vencidos, de_outra_pessoa, retirado = [], None, None
    try:
        with TRAVA_DOS_PEDIDOS:
            vencidos = _recolher_vencidos()
            pedido = PEDIDOS.get(confirmacao_id) if isinstance(confirmacao_id, str) else None
            if pedido is not None and pedido.liberado:  # prévia ainda não entregue ao agente não existe
                if pedido.id_usuario == getattr(usuario, "id_usuario", None):
                    retirado = PEDIDOS.pop(confirmacao_id)
                else:
                    de_outra_pessoa = pedido
    finally:
        _registrar_expirados(vencidos)
    if de_outra_pessoa is not None:  # a tentativa fica no rastro
        negado = resposta("erro", tipo_erro="nao_encontrado")
        with suppress(governanca.RegistroIndisponivel):
            _registrar(de_outra_pessoa, usuario, negado, "usuario", time.monotonic())
    return retirado


def _tirar_da_fila(confirmacao_id):
    """Descarta a prévia sem registrar (a fase 1 não chegou a ser entregue) e apaga o conteúdo."""
    with TRAVA_DOS_PEDIDOS:
        pedido = PEDIDOS.pop(confirmacao_id, None) if isinstance(confirmacao_id, str) else None
    if pedido is not None:
        pedido.conteudo.clear()


def _liberar(confirmacao_id):
    with TRAVA_DOS_PEDIDOS:
        pedido = PEDIDOS.get(confirmacao_id) if isinstance(confirmacao_id, str) else None
        if pedido is not None:
            pedido.liberado = True


def _devolver(pedido):
    with TRAVA_DOS_PEDIDOS:
        PEDIDOS[pedido.confirmacao_id] = pedido


def _para_interface(pedido, situacao=PENDENTE):
    """O pedido no formato `Confirmacao` do contrato do front (§4.9). Só a prévia mascarada; o conteúdo fica aqui."""
    ferramenta = pedido.ferramenta
    campos = [
        {"rotulo": rotulo, "valor": ferramenta.texto_do_campo(campo, pedido.previa[campo])}
        for campo, rotulo in ferramenta.rotulos_da_previa.items()
        if campo in pedido.previa
    ]
    return {
        "id": pedido.confirmacao_id,
        "ferramenta": ferramenta.nome,
        "titulo": ferramenta.titulo or ferramenta.nome,
        "campos": campos,
        "situacao": situacao,
    }


def confirmacoes_da_execucao(execucao_id, usuario):
    """Todas as prévias que esta execução do agente deixou esperando o `usuario`, no formato `Confirmacao` (§4.9),
    na ordem em que foram montadas. Para a resposta do turno, use `confirmacao_da_execucao` (uma só)."""
    if execucao_id is None:
        return []
    with TRAVA_DOS_PEDIDOS:
        vencidos = _recolher_vencidos()
        lista = [
            _para_interface(p)
            for p in PEDIDOS.values()
            if p.liberado
            and p.id_usuario == getattr(usuario, "id_usuario", None)
            and p.contexto.get("execucao_id") == execucao_id
        ]
    _registrar_expirados(vencidos)
    return lista


def confirmacao_da_execucao(execucao_id, usuario):
    """A prévia mais recente que esta execução deixou esperando o `usuario` (`Confirmacao`, §4.9), ou None.

    O contrato tem uma `confirmacao` por resposta (`RespostaAgente`, §4.6). Se o agente montou mais de uma no
    mesmo turno, a interface mostra a última; as anteriores continuam valendo e aparecem em `pendentes`.
    [A FAZER (Marcelo e Isabel, back-end, KAN-60): depois de `rodar_turno`, o orquestrador chama esta função
    com o mesmo `execucao_id` do contexto e põe o resultado em `RespostaAgente.confirmacao` (tipo "confirmacao")]
    """
    lista = confirmacoes_da_execucao(execucao_id, usuario)
    return lista[-1] if lista else None


def _lembrar_decisao(pedido, situacao):
    with TRAVA_DOS_PEDIDOS:
        limite = agora() - LEMBRAR_DECISAO
        for antiga in [c for c, (_, _, quando) in DECIDIDAS.items() if quando <= limite]:
            del DECIDIDAS[antiga]
        while len(DECIDIDAS) >= LIMITE_PEDIDOS:
            del DECIDIDAS[next(iter(DECIDIDAS))]
        DECIDIDAS[pedido.confirmacao_id] = (pedido.id_usuario, situacao, agora())


def situacao_da_decisao(confirmacao_id, usuario):
    """`aprovada` ou `cancelada` se o `usuario` já decidiu esta prévia há pouco (`LEMBRAR_DECISAO`); senão None.

    [A FAZER (Marcelo e Isabel, back-end, KAN-60): a rota de confirmação responde 409 quando esta função diz que
    a prévia já foi decidida e 404 quando `confirmacao_para_interface` e esta função devolvem None]
    """
    with TRAVA_DOS_PEDIDOS:
        decisao = DECIDIDAS.get(confirmacao_id) if isinstance(confirmacao_id, str) else None
    if decisao is None or decisao[0] != getattr(usuario, "id_usuario", None):
        return None
    _, situacao, quando = decisao
    return situacao if agora() - quando < LEMBRAR_DECISAO else None


def _sem_pedido(confirmacao_id, usuario):
    """Resposta de `confirmar` e `cancelar` quando a prévia não está na fila: já decidida ou não existe."""
    situacao = situacao_da_decisao(confirmacao_id, usuario)
    mensagem = MENSAGEM_JA_DECIDIDA.get(situacao, MENSAGEM_NAO_ENCONTRADO)
    return resposta("erro", None, mensagem, "nao_encontrado")


def confirmacao_para_interface(confirmacao_id, usuario):
    """Uma prévia que espera o `usuario`, no formato `Confirmacao` (§4.9), ou None (não existe ou é de outra pessoa).

    [A FAZER (Marcelo e Isabel, back-end, KAN-60): a rota POST /conversas/{id}/confirmacoes/{confirmacao_id} confere
    com esta função que a prévia ainda espera; depois chama `confirmar` ou `cancelar` e grava `decidida(...)`]
    """
    with TRAVA_DOS_PEDIDOS:
        vencidos = _recolher_vencidos()
        pedido = PEDIDOS.get(confirmacao_id) if isinstance(confirmacao_id, str) else None
        dono = pedido is not None and pedido.id_usuario == getattr(usuario, "id_usuario", None)
        confirmacao = _para_interface(pedido) if dono and pedido.liberado else None
    _registrar_expirados(vencidos)
    return confirmacao


def decidida(confirmacao, aprovada):
    """A `Confirmacao` depois da decisão, para o histórico da conversa mostrar "Confirmado" ou "Cancelado"."""
    return {**confirmacao, "situacao": APROVADA if aprovada else CANCELADA}


def pendentes(usuario):
    """Prévias que esperam a confirmação do `usuario`, para a interface ou o terminal mostrarem."""
    with TRAVA_DOS_PEDIDOS:
        vencidos = _recolher_vencidos()
        do_usuario = [
            p for p in PEDIDOS.values() if p.liberado and p.id_usuario == getattr(usuario, "id_usuario", None)
        ]
        lista = [{"ferramenta": p.ferramenta.nome, **_como_mostrar(p)} for p in do_usuario]
    _registrar_expirados(vencidos)
    return lista


def confirmar(confirmacao_id, usuario):
    """Roda o efeito do pedido, se ele é de quem confirma e o acesso continua valendo. Uso único."""
    inicio = time.monotonic()
    pedido = _retirar(confirmacao_id, usuario)
    if pedido is None:
        return _sem_pedido(confirmacao_id, usuario)
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
    pode_ter_saido = True  # só "nada saiu" (recusa ou falha antes do envio) muda isto
    try:
        dados = mascara.mascarar(
            ferramenta.efetivar(pedido.conteudo, usuario), ferramenta.categorias_dados, ferramenta.campos_liberados
        )
        resultado = resposta("ok", dados, ferramenta.mensagem_feito)
    except ErroFerramenta as erro:
        pode_ter_saido = False
        resultado = resposta("erro", None, erro.mensagem, erro.tipo_erro)
    except EfeitoIncerto:  # saiu, mas sem confirmação: dizer "nada foi enviado" seria mentir
        resultado = resposta("erro", None, MENSAGEM_EFEITO_INCERTO, "integracao_indisponivel")
    except (ConnectionError, TimeoutError):
        pode_ter_saido = False
        resultado = resposta("erro", None, MENSAGEM_FORA_DO_AR, "integracao_indisponivel")
    except Exception as erro:  # noqa: BLE001 (só o tipo vai ao log: a mensagem pode ter o e-mail)
        logger.error("confirmação falhou: ferramenta=%s tipo=%s", ferramenta.nome, type(erro).__name__)
        resultado = resposta("erro", None, "Erro interno.", "erro_interno")
    finally:
        pedido.conteudo.clear()
    if pode_ter_saido:  # a prévia não se confirma de novo; quem tentar ouve "já foi confirmada" (409)
        _lembrar_decisao(pedido, APROVADA)
    try:
        _registrar(pedido, usuario, resultado, None, inicio)
    except governanca.RegistroIndisponivel:
        return resposta("erro", None, MENSAGEM_REGISTRO_FINAL, "integracao_indisponivel")
    return resultado


def cancelar(confirmacao_id, usuario):
    """Descarta a prévia sem agir. Só quem pediu descarta."""
    pedido = _retirar(confirmacao_id, usuario)
    if pedido is None:
        return _sem_pedido(confirmacao_id, usuario)
    pedido.conteudo.clear()
    _lembrar_decisao(pedido, CANCELADA)
    with suppress(governanca.RegistroIndisponivel):  # descartar não age: vale mesmo sem rastro
        _registrar(pedido, usuario, resposta("cancelada"), None, time.monotonic())
    return resposta("ok", {"confirmacao_id": pedido.confirmacao_id, "situacao": "cancelada"}, "Descartado.")


def limpar():
    """Esvazia a fila sem registrar (testes e reinício da demo)."""
    with TRAVA_DOS_PEDIDOS:
        for pedido in PEDIDOS.values():
            pedido.conteudo.clear()
        PEDIDOS.clear()
        DECIDIDAS.clear()
