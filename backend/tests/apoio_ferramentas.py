"""Apoio dos testes de ferramentas: mundo do mock em memória e usuários montados pelo diretório."""

from ferramentas import catalogo, dados_sinteticos, governanca
from mock.banco import criar_engine
from mock.consultas import buscar_funcionario
from mock.falhas import desligar_todas
from mock.gerar import recriar

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


def mundo_do_mock():
    """Cria o mock em memória e liga as ferramentas a ele. Devolve o engine."""
    engine = criar_engine("sqlite://")
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
