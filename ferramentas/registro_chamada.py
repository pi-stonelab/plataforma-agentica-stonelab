"""Registro de cada chamada de ferramenta.

Guarda quem chamou o quê e como terminou. Nunca guarda o conteúdo: nem os
argumentos recebidos, nem os dados devolvidos.
"""
import json
import logging
import re
from datetime import datetime, timezone

CAMPOS_DO_REGISTRO = (
    "execucao_id",
    "passo",
    "agente_id",
    "ferramenta",
    "usuario_id",
    "integracao",
    "tipo_acesso",
    "status",
    "tipo_erro",
    "duracao_ms",
    "custo_estimado",
    "categorias_dados",
    "momento",
)
TAMANHO_MAXIMO_DO_TEXTO = 64
PADRAO_DO_NOME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
NOME_DESCONHECIDO = "desconhecida"

registrador = logging.getLogger("ferramentas.chamadas")
destinos = []


def adicionar_destino(destino):
    """O back-end entrega aqui a função que grava o registro no banco."""
    destinos.append(destino)


def texto_curto(valor):
    if valor is None:
        return None
    return str(valor)[:TAMANHO_MAXIMO_DO_TEXTO]


def nome_para_registro(ferramenta, nome_pedido):
    """O nome pedido vem do modelo, então só entra no registro se tiver cara de nome."""
    if ferramenta is not None:
        return ferramenta.nome
    if isinstance(nome_pedido, str) and PADRAO_DO_NOME.match(nome_pedido):
        return nome_pedido
    return NOME_DESCONHECIDO


def montar_registro(retorno, duracao_ms, ferramenta=None, nome_pedido=None, usuario=None, contexto=None):
    if not isinstance(contexto, dict):
        contexto = {}
    integracao = None
    tipo_acesso = None
    categorias_dados = []
    custo_estimado = 0.0
    if ferramenta is not None:
        integracao = ",".join(ferramenta.integracoes) or "nenhuma"
        tipo_acesso = ferramenta.tipo_acesso
        categorias_dados = list(ferramenta.categorias_dados)
        custo_estimado = ferramenta.custo_estimado
    return {
        "execucao_id": texto_curto(contexto.get("execucao_id")),
        "passo": texto_curto(contexto.get("passo")),
        "agente_id": texto_curto(contexto.get("agente_id")),
        "ferramenta": nome_para_registro(ferramenta, nome_pedido),
        "usuario_id": texto_curto(getattr(usuario, "id", None)),
        "integracao": integracao,
        "tipo_acesso": tipo_acesso,
        "status": retorno["status"],
        "tipo_erro": retorno["tipo_erro"],
        "duracao_ms": duracao_ms,
        "custo_estimado": custo_estimado,
        "categorias_dados": categorias_dados,
        "momento": datetime.now(timezone.utc).isoformat(),
    }


def registrar(registro):
    registrador.info("chamada_ferramenta %s", json.dumps(registro, ensure_ascii=False))
    for destino in destinos:
        try:
            destino(dict(registro))
        except Exception as erro:  # noqa: BLE001
            registrador.error("Falha ao gravar o registro da chamada: %s", type(erro).__name__)


def registrar_chamada(retorno, duracao_ms, ferramenta=None, nome_pedido=None, usuario=None, contexto=None):
    registro = montar_registro(retorno, duracao_ms, ferramenta, nome_pedido, usuario, contexto)
    registrar(registro)
    return registro
