"""Apoio dos testes de ferramentas: mundo do mock em memória e usuários montados pelo diretório."""

import os

from ferramentas import catalogo, dados_sinteticos, governanca
from mock.banco import criar_engine
from mock.consultas import buscar_funcionario
from mock.falhas import desligar_todas
from mock.gerar import recriar
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

VARIAVEL_POSTGRES_DE_TESTE = "MOCK_TESTE_POSTGRES_URL"

TODAS_ATIVAS = (
    "consultar_cliente",
    "consultar_transacoes_cliente",
    "calcular_multa_atraso",
    "consultar_endereco_cep",
    "solicitar_ferramenta_ausente",
)
CARGOS_COM_FERRAMENTA = (
    "atendente_n1",
    "especialista_n2",
    "supervisor_atendimento",
    "analista_ouvidoria",
    "analista_cobranca",
    "analista_disputas",
    "analista_recebiveis",
    "coordenador_financeiro",
)
CARGOS_TRANSVERSAIS = ("auditor_compliance", "admin_plataforma")
FUNCIONARIO_DO_CARGO = {
    "atendente_n1": "F0001",
    "especialista_n2": "F0002",
    "supervisor_atendimento": "F0006",
    "analista_ouvidoria": "F0007",
    "analista_cobranca": "F0008",
    "analista_disputas": "F0009",
    "analista_recebiveis": "F0010",
    "coordenador_financeiro": "F0011",
    "auditor_compliance": "F0012",
    "admin_plataforma": "F0013",
}
NEGADO_PELO_CATALOGO = {
    "status": "erro",
    "dados": None,
    "mensagem": "Ferramenta não encontrada.",
    "tipo_erro": "ferramenta_inexistente",
}


def url_do_postgres_de_teste() -> str | None:
    """URL do Postgres de teste, se declarada. Recusa banco cujo nome não indique que é do mock.

    Cada mundo novo APAGA as tabelas do mock nesse banco, então ele precisa ser um banco só
    do mock (o nome tem de conter "mock" ou "teste"), nunca o da plataforma.
    """
    url = os.environ.get(VARIAVEL_POSTGRES_DE_TESTE, "").strip()
    if not url:
        return None
    nome = (make_url(url).database or "").lower()
    if not ("mock" in nome or "teste" in nome):
        raise RuntimeError(f"{VARIAVEL_POSTGRES_DE_TESTE}: o nome do banco precisa conter 'mock' ou 'teste'.")
    return url


def novo_engine_do_mock() -> Engine:
    """Engine do mock dos testes: SQLite em memória, ou o Postgres de teste se ele foi declarado."""
    return criar_engine(url_do_postgres_de_teste() or "sqlite://")


def mundo_do_mock():
    """Cria o mock e liga as ferramentas a ele. Devolve o engine."""
    engine = novo_engine_do_mock()
    recriar(engine)
    dados_sinteticos.configurar(engine)
    return engine


def limpar_estado():
    """Zera o que as ferramentas guardam em memória e as falhas ligadas."""
    del governanca.REGISTROS[:]
    del governanca.DESTINOS[:]
    desligar_todas()
    pedidos = catalogo.carregar()["solicitar_ferramenta_ausente"]
    pedidos_em_memoria = __import__(type(pedidos).__module__, fromlist=["PEDIDOS"]).PEDIDOS
    pedidos_em_memoria.clear()


def usuario_do_diretorio(engine, id_funcionario):
    """Monta o Usuario como o back-end fará: cargo e carteiras vêm do diretório do mock."""
    funcionario = buscar_funcionario(engine, id_funcionario)
    return governanca.usuario_do_cargo(
        funcionario["id"], funcionario["cargo"], tuple(funcionario["carteiras"])
    )


def executar(nome, argumentos, usuario, ferramentas_do_agente=TODAS_ATIVAS):
    return catalogo.executar(nome, argumentos, usuario, ferramentas_do_agente)
