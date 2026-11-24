"""Quem pode liberar campos da máscara (`campos_liberados` da ficha) e quais campos.

Liberar um campo tira dele a regra "negar por padrão": o texto passa pela máscara de CPF e cartão, mas
não vira "***". Por isso a lista abaixo é fechada. Ferramenta nova que precise liberar um campo exige
mudar este arquivo, e a mudança passa pela revisão do CODEOWNERS (QA e Produto).
"""

import pytest
from ferramentas import catalogo
from ferramentas.base import Ferramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from mock.regras import CAMPOS_NAO_RESTRITOS, CLASSIFICACAO_CAMPOS

# Ferramenta -> campos que ela pode liberar. Só a escrita em duas fases devolve texto escrito pelo modelo
# (a prévia), então só ela entra aqui. Leitura nunca libera: o texto dela é de lojista.
CONFIRMACAO = frozenset({"confirmacao_id", "expira_em", "aviso"})
LIBERACOES_PERMITIDAS = {
    "enviar_email": CONFIRMACAO | {"assunto", "corpo", "id_mensagem"},
    "abrir_chamado_jira": CONFIRMACAO | {"projeto"},
    "comentar_chamado_jira": CONFIRMACAO,
    "enviar_mensagem_slack": CONFIRMACAO,
    "enviar_aviso_telegram": CONFIRMACAO | {"chat"},
    # Agenda e planilhas da conta Google ou Microsoft (bloco E2): a prévia mostra o que vai ser criado ou gravado.
    "criar_evento_agenda": CONFIRMACAO | {"servico", "quando", "convidados"},
    "adicionar_linha_planilha": CONFIRMACAO | {"servico", "planilha", "valores", "linhas_adicionadas"},
    "criar_planilha": CONFIRMACAO | {"servico"},
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
def test_so_a_escrita_em_duas_fases_pode_liberar_campos(nome, ferramenta):
    if ferramenta.campos_liberados:
        assert isinstance(ferramenta, FerramentaComConfirmacao), f"{nome} não é escrita em duas fases. {COMO_LIBERAR}"
        assert ferramenta.acesso == "escrita"


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
