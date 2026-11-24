"""Quem pode liberar campos da máscara (`campos_liberados` da ficha) e quais campos.

Liberar um campo tira dele a regra "negar por padrão": o texto passa pela máscara de CPF e cartão, mas
não vira "***". Por isso a lista abaixo é fechada. Ferramenta nova que precise liberar um campo exige
mudar este arquivo, e a mudança passa pela revisão do CODEOWNERS (QA e Produto).
"""

import pytest
from ferramentas import catalogo, mascara
from ferramentas.base import Ferramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from mock.regras import CAMPOS_NAO_RESTRITOS, CLASSIFICACAO_CAMPOS

# Ferramenta -> campos que ela pode liberar. Dois casos: a escrita em duas fases (texto escrito pelo modelo,
# a prévia) e a leitura ou o cálculo que devolve texto escrito pela PLATAFORMA (aviso, orientação, tendência),
# nunca texto de lojista: o que o lojista escreve (nome fantasia, resumo, comentário) continua sem liberação.
CONFIRMACAO = frozenset({"confirmacao_id", "expira_em", "aviso"})
LIBERACOES_PERMITIDAS = {
    "enviar_email": CONFIRMACAO | {"assunto", "corpo", "id_mensagem"},
    "abrir_chamado_jira": CONFIRMACAO | {"projeto"},
    "comentar_chamado_jira": CONFIRMACAO,
    "enviar_mensagem_slack": CONFIRMACAO,
    "enviar_aviso_telegram": CONFIRMACAO | {"chat"},
    # escritas sobre o mock (bloco D)
    "abrir_chamado": CONFIRMACAO | {"nivel_atendimento"},
    "adicionar_nota_chamado": CONFIRMACAO | {"tipo_da_nota"},
    "atualizar_situacao_chamado": CONFIRMACAO
    | {"situacao_atual", "nova_situacao", "encaminhar_para", "suspeita_fraude", "nivel_atendimento"},
    "registrar_pedido_antecipacao": CONFIRMACAO | {"nivel_atendimento", "valor_antecipado", "desconto", "data_credito"},
    "executar_antecipacao": CONFIRMACAO | {"valor_antecipado", "desconto", "data_credito", "taxa_mensal_percentual"},
    "reprocessar_liquidacao": CONFIRMACAO | {"nova_tentativa_em"},
    "registrar_acordo": CONFIRMACAO | {"encargos", "valor_da_parcela", "aprovacao"},
    "aprovar_acordo": CONFIRMACAO | {"id_acordo", "decisao"},
    "buscar_emails": frozenset({"data_inicio", "data_fim"}),
    "buscar_conjuntos_dados": frozenset({"nome_do_sistema"}),
    "conferir_liquidacoes": frozenset({"agenda", "diferenca", "explicacao", "pago"}),
    "consultar_linhagem_conjunto": frozenset({"derivados"}),
    "consultar_responsavel_conjunto": frozenset({"nome_do_sistema", "orientacao"}),
    "consultar_saldo_agenda": frozenset({"data_base"}),
    "consultar_taxa_contestacao_cliente": frozenset({"mes_fim", "mes_inicio", "meses_acima_do_limite"}),
    "consultar_taxa_contestacao_mensal": frozenset({"mes_fim", "mes_inicio", "tendencia"}),
    "resumir_receita_periodo": frozenset({"aviso", "data_fim", "data_inicio", "mdr"}),
    "resumir_volume_chamados": frozenset({"aviso", "data_fim", "data_inicio"}),
    "simular_antecipacao": frozenset({"aviso", "data_credito", "desconto", "valor_antecipado"}),
    "verificar_identidade_contato": frozenset({"orientacao"}),
}
COMO_LIBERAR = "Para liberar um campo novo, edite LIBERACOES_PERMITIDAS em test_ferramentas_campos_liberados.py."

FERRAMENTAS = sorted(catalogo.carregar().items())


def test_a_ficha_padrao_nao_libera_nada():
    assert Ferramenta.campos_liberados == ()


@pytest.mark.parametrize(("nome", "ferramenta"), FERRAMENTAS, ids=[nome for nome, _ in FERRAMENTAS])
def test_ferramenta_so_libera_os_campos_da_lista_fechada(nome, ferramenta):
    liberados = set(ferramenta.campos_liberados)
    permitidos = LIBERACOES_PERMITIDAS.get(nome, frozenset())
    assert liberados <= permitidos, f"{nome} libera {sorted(liberados - permitidos)}. {COMO_LIBERAR}"


@pytest.mark.parametrize(("nome", "ferramenta"), FERRAMENTAS, ids=[nome for nome, _ in FERRAMENTAS])
def test_escrita_que_libera_campos_e_em_duas_fases(nome, ferramenta):
    if ferramenta.campos_liberados and ferramenta.acesso == "escrita":
        assert isinstance(ferramenta, FerramentaComConfirmacao), f"{nome} não é escrita em duas fases. {COMO_LIBERAR}"


@pytest.mark.parametrize(("nome", "ferramenta"), FERRAMENTAS, ids=[nome for nome, _ in FERRAMENTAS])
def test_escrita_em_duas_fases_libera_pelo_menos_os_campos_da_confirmacao(nome, ferramenta):
    if isinstance(ferramenta, FerramentaComConfirmacao):
        assert set(FerramentaComConfirmacao.campos_liberados) <= set(ferramenta.campos_liberados)


def test_campo_liberado_nunca_e_campo_restrito_nem_repete_a_lista_global():
    for nome, campos in LIBERACOES_PERMITIDAS.items():
        assert not campos & set(CLASSIFICACAO_CAMPOS), f"{nome} liberaria um campo restrito"
        assert not campos & CAMPOS_NAO_RESTRITOS, f"{nome} repete a lista global: tire daqui ou de lá"


def test_a_lista_fechada_so_cita_ferramentas_e_campos_que_existem():
    catalogo_atual = catalogo.carregar()
    for nome, campos in LIBERACOES_PERMITIDAS.items():
        assert nome in catalogo_atual, f"{nome} saiu do catálogo: tire da lista"
        assert set(catalogo_atual[nome].campos_liberados) == campos, f"{nome}: a ficha e a lista divergem"


def test_nomes_de_campos_liberados_sao_texto_simples():
    for nome, ferramenta in FERRAMENTAS:
        assert all(isinstance(campo, str) and campo.isidentifier() for campo in ferramenta.campos_liberados), nome


# Campos genéricos que antes valiam para toda ferramenta (aviso, orientacao, pago...) agora só valem na ficha de
# quem os usa (docs/decisoes.md, C14). Numa ferramenta que lê dado de lojista, o resto continua sendo "***".
CAMPOS_QUE_ERAM_GLOBAIS = (
    "orientacao", "aviso", "explicacao", "agenda", "pago", "diferenca", "desconto", "valor_antecipado", "mdr",
    "data_inicio", "data_fim", "mes_inicio", "mes_fim", "nome_do_sistema", "derivados",
)


@pytest.mark.parametrize("campo", CAMPOS_QUE_ERAM_GLOBAIS)
def test_campo_generico_nao_vale_mais_para_toda_ferramenta(campo):
    assert campo not in CAMPOS_NAO_RESTRITOS
    assert mascara.mascarar({campo: "texto qualquer"}, ("venda",)) == {campo: "***"}
    assert mascara.mascarar({campo: "texto qualquer"}, ("venda",), (campo,)) == {campo: "texto qualquer"}


def test_todo_campo_que_era_global_esta_na_ficha_de_alguma_ferramenta():
    liberados = set().union(*(set(f.campos_liberados) for _, f in FERRAMENTAS))
    assert set(CAMPOS_QUE_ERAM_GLOBAIS) <= liberados
