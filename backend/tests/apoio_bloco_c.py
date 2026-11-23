"""Apoio dos testes das ferramentas de leitura e cálculo do bloco C (mundo do mock de verdade, em memória)."""

from ferramentas import catalogo

from .apoio_ferramentas import FUNCIONARIO_DO_CARGO, usuario_do_diretorio

FERRAMENTAS_DO_BLOCO_C = (
    "consultar_base_conhecimento",
    "consultar_chamado",
    "verificar_identidade_contato",
    "buscar_clientes",
    "resumir_satisfacao",
    "consultar_agenda_recebiveis",
    "simular_antecipacao",
    "conferir_liquidacoes",
    "listar_contestacoes_cliente",
    "listar_acordos",
    "resumir_receita_periodo",
    "resumir_volume_chamados",
    "consultar_taxa_contestacao_mensal",
    "calcular_roi",
    "buscar_conjuntos_dados",
    "consultar_esquema_conjunto",
    "consultar_responsavel_conjunto",
    "consultar_linhagem_conjunto",
)
AGENTE = tuple(catalogo.nomes())  # o agente geral: o que limita é o cargo


def usuario(engine, cargo):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])


def chamar(nome, argumentos, pessoa):
    return catalogo.executar(nome, argumentos, pessoa, AGENTE)


def resultado(resposta):
    return resposta["status"], resposta["tipo_erro"]


def dados_de(resposta):
    """`dados` sem o envelope de conteúdo de terceiros."""
    dados = resposta["dados"]
    return dados.get("conteudo_de_terceiros", dados) if isinstance(dados, dict) else dados
