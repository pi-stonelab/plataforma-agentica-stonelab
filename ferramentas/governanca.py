"""Governança das ferramentas: permissão por cargo, escopo de lojista, janela de dias e registro.

Tudo aqui falha fechado: na dúvida, a ferramenta é bloqueada e o lojista fica fora do escopo.
Vocabulário do mock (mock/regras.py): `cargo` (10 cargos), `nivel` N1/N2 como texto, `area`
atendimento/financeiro, `carteiras` = nomes de carteira (varejo, pme, contas_chave) e lojista pelo
`codigo` M00001. As listas abaixo vêm do mock: não repita valores aqui.
"""

import logging
from datetime import timedelta

from mock import regras

NIVEIS = regras.NIVEIS_FERRAMENTA
AREAS_USUARIO = regras.AREAS
ACESSOS = ("leitura", "escrita", "calculo")
SENSIBILIDADES = ("publica", "interna", "pessoal", "sigilosa")
CATEGORIAS_DADOS = regras.CATEGORIAS_DADO + regras.CATEGORIAS_DE_FERRAMENTAS_PLANEJADAS
STATUS_FICHA = ("ativa", "inativa", "planejada")
TODAS_AS_AREAS = "todas"
PARAMETROS_RESERVADOS = (
    "usuario",
    "id_usuario",
    "nivel",
    "area",
    "carteira",
    "carteiras",
    "cargo",
    "credencial",
    "ferramentas_do_agente",
    "contexto",
)
ESCRITA_SEM_CONFIRMACAO = ("solicitar_ferramenta_ausente",)
LIMITE_LINHAS = regras.LIMITE_MAXIMO
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
logger = logging.getLogger(__name__)


class RegistroIndisponivel(Exception):
    """Algum destino não gravou o registro: sem rastro, sem resposta (O9)."""


class Usuario:
    """Funcionário autenticado. O `cargo` decide o que ele vê; nível e área vêm do cargo.

    `carteiras` são nomes de carteira do time dele (ex.: ("varejo",)). Provisório até a classe
    oficial (KAN-62).
    """

    def __init__(self, id_usuario, nivel, area, carteiras=(), cargo=None):
        self.id_usuario = id_usuario
        self.nivel = nivel
        self.area = area
        self.carteiras = carteiras
        self.cargo = cargo


def usuario_do_cargo(id_usuario, cargo, carteiras=()):
    """Monta o Usuario pelo cargo do diretório. Cargo desconhecido ou transversal: usuário inválido."""
    regra = regras.regra_do_cargo(cargo)
    nivel, area = (regra.nivel_ferramenta, regra.area) if regra else (None, None)
    return Usuario(id_usuario, nivel, area, carteiras, cargo)


def _regra(usuario):
    return regras.regra_do_cargo(getattr(usuario, "cargo", None))


def _usuario_valido(usuario):
    id_usuario = getattr(usuario, "id_usuario", None)
    regra = _regra(usuario)
    return (
        isinstance(id_usuario, str)
        and id_usuario.strip() != ""
        and regra is not None
        and getattr(usuario, "nivel", None) in NIVEIS
        and getattr(usuario, "area", None) in AREAS_USUARIO
        and (usuario.nivel, usuario.area) == (regra.nivel_ferramenta, regra.area)
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
        if not set(ferramenta.categorias_dados) <= _regra(usuario).categorias_dado:
            return "Categoria de dado não permitida para o cargo."  # O1: some do catalogo.ler
        return None
    except (AttributeError, TypeError, ValueError):
        return "Ficha ou usuário inválido."


def escopo_do_usuario(usuario):
    """Escopo de lojistas do cargo (carteiras_do_time, todas ou nenhum); None se usuário inválido."""
    return _regra(usuario).escopo_lojistas if _usuario_valido(usuario) else None


def lojista_no_escopo(usuario, lojista):
    """`lojista` é o dict de `carteira_do_lojista` (ou None se não existe). Sem banco aqui (O13)."""
    try:
        escopo = escopo_do_usuario(usuario)
        if escopo == regras.ESCOPO_CARTEIRAS_DO_TIME:
            carteiras = usuario.carteiras
            return isinstance(carteiras, (tuple, list)) and lojista["carteira"] in carteiras
        return escopo == regras.ESCOPO_TODAS and isinstance(lojista, dict)
    except (AttributeError, TypeError, KeyError):
        return False


def janela_dias(usuario):
    """Quantos dias para trás o cargo consulta vendas e agenda (KAN-69); None = sem janela.

    Usuário inválido levanta ValueError (nunca vira "sem janela" nem "janela de zero dias"): quem
    chama já passou por `motivo_bloqueio`, então isso só acontece por erro de programação.
    """
    if not _usuario_valido(usuario):
        raise ValueError("Usuário inválido.")
    return _regra(usuario).janela_dias


def inicio_da_janela(usuario):
    """Primeiro dia que o cargo pode consultar, contado de HOJE_DO_MOCK (nunca date.today())."""
    dias = janela_dias(usuario)
    return None if dias is None else regras.HOJE_DO_MOCK - timedelta(days=dias)


def adicionar_destino(funcao):
    """Liga um destino (back-end, monitoramento) que recebe cada registro como dict."""
    if callable(funcao):
        DESTINOS.append(funcao)


def registrar(registro):
    """Guarda só os campos de CAMPOS_REGISTRO e repassa aos destinos.

    Falha fechada (O9): se algum destino não gravar, o registro fica marcado como erro e a função
    levanta RegistroIndisponivel, para quem chamou negar a resposta.
    """
    if not isinstance(registro, dict):
        return
    limpo = {campo: registro.get(campo) for campo in CAMPOS_REGISTRO}
    falhou = False
    for destino in DESTINOS:
        try:
            destino(dict(limpo))
        except Exception:  # noqa: BLE001 (qualquer falha do destino nega a resposta)
            falhou = True
    if falhou:
        limpo["status"], limpo["tipo_erro"] = "erro", "integracao_indisponivel"
    REGISTROS.append(limpo)
    del REGISTROS[:-LIMITE_REGISTROS]
    if falhou:
        logger.error("registro de ferramenta não gravado: ferramenta=%s", limpo["ferramenta"])
        raise RegistroIndisponivel
