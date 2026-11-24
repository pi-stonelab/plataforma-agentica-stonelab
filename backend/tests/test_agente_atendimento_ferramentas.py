"""Lista de ferramentas do agente de atendimento (decisão F1): cada ferramenta do catálogo entra ou fica de fora
por uma razão escrita aqui, e o que cada cargo alcança pelo agente bate com o DOC-MOCK §8.2 (gabaritos)."""

import pytest
from agentes.agente_atendimento import agente as atendimento
from agentes.agente_geral import agente as geral
from ferramentas import catalogo, governanca

from . import gabaritos as gab
from .apoio_agente import usuario_do_cargo

TODAS = tuple(catalogo.nomes())
LISTA = atendimento.FERRAMENTAS_DO_AGENTE

# O que o agente de atendimento NÃO usa, e por quê (o agente geral usa tudo).
INDICADORES_GERENCIAIS = {
    "resumir_satisfacao",
    "resumir_receita_periodo",
    "resumir_volume_chamados",
    "consultar_taxa_contestacao_mensal",
    "calcular_roi",
}
DICIONARIO_DE_DADOS = {
    "buscar_conjuntos_dados",
    "consultar_esquema_conjunto",
    "consultar_responsavel_conjunto",
    "consultar_linhagem_conjunto",
}
BASTIDOR_INTERNO = {  # pedidos a outros times e avisos a colegas: não são atendimento ao lojista
    "abrir_chamado_jira",
    "comentar_chamado_jira",
    "consultar_chamado_jira",
    "enviar_mensagem_slack",
    "enviar_aviso_telegram",
}
CONTA_PESSOAL_DO_FUNCIONARIO = {  # Google ou Microsoft de cada pessoa: fica com o agente geral
    "listar_eventos_agenda",
    "criar_evento_agenda",
    "buscar_arquivos",
    "ler_planilha",
    "adicionar_linha_planilha",
    "criar_planilha",
    "ler_documento",
}
DE_OUTRO_PAPEL = {  # segregação de funções, DOC-MOCK §8.1: quem pede não aprova; reprocessar é dos recebíveis
    "aprovar_acordo",
    "reprocessar_liquidacao",
    "retirar_acordo",  # é da cobrança: quem pediu o acordo o retira
}
FORA_DO_AGENTE = (
    INDICADORES_GERENCIAIS | DICIONARIO_DE_DADOS | BASTIDOR_INTERNO | CONTA_PESSOAL_DO_FUNCIONARIO | DE_OUTRO_PAPEL
)


def _tudo_ligado(monkeypatch):
    monkeypatch.setattr(catalogo, "_integracao_desligada", lambda ferramenta: None)


def test_lista_e_tupla_de_nomes_sem_repeticao_e_todos_existem_no_catalogo():
    assert isinstance(LISTA, tuple) and len(set(LISTA)) == len(LISTA)
    assert set(LISTA) <= set(TODAS)
    assert all(catalogo.carregar()[nome].esta_ativa() for nome in LISTA)


def test_toda_ferramenta_do_catalogo_entra_no_agente_ou_tem_motivo_para_ficar_de_fora():
    assert set(LISTA) & FORA_DO_AGENTE == set()
    assert set(LISTA) | FORA_DO_AGENTE == set(TODAS), "Ferramenta nova: decida se entra no agente de atendimento (F1)."


def test_agente_geral_continua_com_todas():
    assert set(geral.FERRAMENTAS_DO_AGENTE) == set(TODAS)


def test_nenhum_indicador_gerencial_nem_bastidor_no_agente():
    for nome in INDICADORES_GERENCIAIS | DICIONARIO_DE_DADOS | BASTIDOR_INTERNO:
        assert nome not in LISTA


def test_as_escritas_do_agente_sao_todas_em_duas_fases_ou_sem_efeito_fora_da_plataforma():
    escritas = {n for n in LISTA if catalogo.carregar()[n].acesso == "escrita"}
    sem_confirmacao = set(governanca.ESCRITA_SEM_CONFIRMACAO)  # `solicitar_ferramenta_ausente` e `entregar_arquivo`
    assert escritas <= set(governanca.ESCRITA_COM_CONFIRMACAO) | sem_confirmacao


@pytest.mark.parametrize("cargo", gab.CARGOS)
def test_cada_cargo_alcanca_pelo_agente_so_o_que_o_gabarito_do_cargo_diz_dentro_da_lista(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    esperado = (gab.FERRAMENTAS_DO_CARGO[cargo] | gab.EXTERNAS_DO_CARGO[cargo]) & set(LISTA)
    assert set(catalogo.ferramentas_liberadas(usuario_do_cargo(cargo), LISTA)) == esperado


def test_doc_mock_8_2_o_que_o_agente_deixa_cada_cargo_fazer(monkeypatch):
    _tudo_ligado(monkeypatch)

    def alcance(cargo):
        return set(catalogo.ferramentas_liberadas(usuario_do_cargo(cargo), LISTA))

    n1, n2 = alcance("atendente_n1"), alcance("especialista_n2")
    # Atendente N1: abre e atualiza chamados, simula antecipação, vê vendas, agenda e faturas; não executa antecipação.
    assert {"abrir_chamado", "atualizar_situacao_chamado", "simular_antecipacao", "consultar_transacoes_cliente",
            "consultar_agenda_recebiveis", "listar_faturas_em_atraso"} <= n1
    assert "executar_antecipacao" not in n1 and "registrar_acordo" not in n1
    # Especialista N2: tudo do N1 e executa a antecipação pedida pelo lojista.
    assert n1 <= n2 and "executar_antecipacao" in n2
    # Cobrança: faturas, acordos e só o saldo da agenda; sem vendas nem simulação de antecipação.
    cobranca = alcance("analista_cobranca")
    assert {"listar_faturas_em_atraso", "listar_acordos", "registrar_acordo", "consultar_saldo_agenda"} <= cobranca
    assert not cobranca & {"consultar_transacoes_cliente", "consultar_agenda_recebiveis", "simular_antecipacao"}
    # Disputas: vendas e contestações; sem agenda de recebíveis.
    disputas = alcance("analista_disputas")
    assert {"consultar_transacoes_cliente", "listar_contestacoes_cliente"} <= disputas
    assert "consultar_agenda_recebiveis" not in disputas
    # Auditor e administrador: nenhuma ferramenta de dado.
    assert alcance("auditor_compliance") == alcance("admin_plataforma") == set()


@pytest.mark.parametrize("cargo", gab.CARGOS)
def test_o_indice_do_agente_nao_mostra_ferramenta_de_fora_da_lista(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    texto = catalogo.ler("", usuario_do_cargo(cargo), LISTA)
    for nome in FORA_DO_AGENTE:
        assert f"/{nome}`" not in texto
