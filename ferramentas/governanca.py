"""Governança provisória: permissão por nível e área, escopo de carteira e registro de chamadas.

Tudo aqui falha fechado: na dúvida, a ferramenta é bloqueada e o cliente fica fora do escopo.
"""

from contextlib import suppress

# [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62]
NIVEIS = ("N1", "N2")
AREAS_USUARIO = ("atendimento", "financeiro", "dados", "tecnologia")
ACESSOS = ("leitura", "escrita", "calculo")
SENSIBILIDADES = ("publica", "interna", "pessoal", "sigilosa")
CATEGORIAS_DADOS = (
    "cadastral",
    "atendimento",
    "financeiro",
    "indicador_agregado",
    "metadado",
    "comunicacao",
    "documento",
    "agenda",
    "chamado_interno",
    "endereco_publico",
    "cambio",
    "pedido_plataforma",
)
STATUS_FICHA = ("ativa", "inativa", "planejada")
TODAS_AS_AREAS = "todas"
PARAMETROS_RESERVADOS = (
    "usuario",
    "id_usuario",
    "nivel",
    "area",
    "carteira",
    "credencial",
    "ferramentas_do_agente",
    "contexto",
)
ESCRITA_SEM_CONFIRMACAO = ("solicitar_ferramenta_ausente",)
LIMITE_LINHAS = 50
CAMPOS_REGISTRO = (
    "momento",
    "execucao_id",
    "passo",
    "agente_id",
    "ferramenta",
    "id_usuario",
    "integracoes",
    "acesso",
    "categorias_dados",
    "status",
    "tipo_erro",
    "camada_bloqueio",
    "duracao_ms",
)
LIMITE_REGISTROS = 1000

# [preencher: prazo de retenção de REGISTROS, definir com Brenno e o monitoramento]
REGISTROS = []
DESTINOS = []


class Usuario:
    """Funcionário autenticado. Provisório até a classe oficial (KAN-62)."""

    def __init__(self, id_usuario, nivel, area, carteira=()):
        self.id_usuario = id_usuario
        self.nivel = nivel
        self.area = area
        self.carteira = carteira


def _usuario_valido(usuario):
    id_usuario = getattr(usuario, "id_usuario", None)
    return (
        isinstance(id_usuario, str)
        and id_usuario.strip() != ""
        and getattr(usuario, "nivel", None) in NIVEIS
        and getattr(usuario, "area", None) in AREAS_USUARIO
    )


def _ficha_valida(ferramenta):
    areas = ferramenta.areas_permitidas
    categorias = ferramenta.categorias_dados
    return (
        ferramenta.nivel_minimo in NIVEIS
        and ferramenta.sensibilidade in SENSIBILIDADES
        and ferramenta.acesso in ACESSOS
        and ferramenta.status in STATUS_FICHA
        and isinstance(areas, (tuple, list))
        and isinstance(categorias, (tuple, list))
        and all(categoria in CATEGORIAS_DADOS for categoria in categorias)
    )


def motivo_bloqueio(ferramenta, usuario):
    """Devolve None se o funcionário pode usar a ferramenta, ou uma frase curta com o motivo."""
    try:
        if not _usuario_valido(usuario):
            return "Usuário inválido."
        if not _ficha_valida(ferramenta):
            return "Ficha inválida."
        if NIVEIS.index(usuario.nivel) < NIVEIS.index(ferramenta.nivel_minimo):
            return "Nível insuficiente."
        areas = ferramenta.areas_permitidas
        if TODAS_AS_AREAS not in areas and usuario.area not in areas:
            return "Área não permitida."
        return None
    except (AttributeError, TypeError, ValueError):
        return "Ficha ou usuário inválido."


def cliente_no_escopo(usuario, id_cliente):
    """Nível mais alto vê qualquer cliente; os demais só os da própria carteira (KAN-69)."""
    try:
        if not _usuario_valido(usuario):
            return False
        if usuario.nivel == NIVEIS[-1]:
            return True
        # [aqui conectamos com Brenno: escopo de carteira oficial, KAN-69]
        return isinstance(usuario.carteira, (tuple, list)) and id_cliente in usuario.carteira
    except (AttributeError, TypeError):
        return False


def adicionar_destino(funcao):
    """Liga um destino (back-end, monitoramento) que recebe cada registro como dict."""
    if callable(funcao):
        DESTINOS.append(funcao)


def registrar(registro):
    """Guarda só os campos de CAMPOS_REGISTRO e repassa aos destinos, sem nunca levantar erro."""
    if not isinstance(registro, dict):
        return
    limpo = {campo: registro.get(campo) for campo in CAMPOS_REGISTRO}
    REGISTROS.append(limpo)
    del REGISTROS[:-LIMITE_REGISTROS]
    for destino in DESTINOS:
        with suppress(Exception):
            destino(dict(limpo))
