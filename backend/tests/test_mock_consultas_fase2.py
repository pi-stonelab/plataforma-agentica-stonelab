"""Leituras da fase 2 e da base analítica: o conector do mock (consultas) e a fachada (dados_sinteticos).

Roda sobre o mundo gerado de verdade, em SQLite na memória. Os valores esperados estão em `gabaritos.py`.
"""

from datetime import date

import pytest
from ferramentas import dados_sinteticos
from ferramentas.mascara import mascarar
from mock import consultas, regras  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import criar_engine
from mock.falhas import SistemaIndisponivel, desligar_todas, ligar
from mock.gerar import CHAMADOS_CRITICOS_CENARIO_11, COMENTARIO_ARMADILHA, recriar
from mock.modelos import BaseMock
from mock.regras import CAMPOS_NAO_RESTRITOS, CLASSIFICACAO_CAMPOS
from sqlalchemy.orm import Session

from tests import gabaritos as gab


@pytest.fixture(scope="module")
def engine():
    engine = criar_engine("sqlite://")
    recriar(engine)
    return engine


@pytest.fixture
def sessao(engine):
    with Session(engine) as sessao_do_teste:
        yield sessao_do_teste


@pytest.fixture(autouse=True)
def sem_falhas(monkeypatch):
    monkeypatch.delenv("MOCK_FALHAS", raising=False)
    desligar_todas()
    yield
    desligar_todas()


@pytest.fixture
def fachada(engine, monkeypatch):
    """A fachada lendo o mesmo mundo em memória (sem o arquivo local do mock)."""
    monkeypatch.setitem(dados_sinteticos._CONEXAO, "engine", engine)
    return dados_sinteticos


def _todas_as_leituras(sessao):
    """Uma chamada de cada leitura nova, com o lojista do cenário que tem dado nela."""
    return [
        consultas.buscar_chamado(sessao, gab.C9_LOJISTA, gab.C9_CHAMADO_OUVIDORIA),
        *consultas.buscar_recebiveis(sessao, gab.C4_LOJISTA)["itens"],
        *consultas.recebiveis_para_antecipacao(sessao, gab.C4_LOJISTA),
        *consultas.buscar_acordos(sessao)["itens"],
        *consultas.buscar_chargebacks(sessao, gab.C2_LOJISTA)["itens"],
        *consultas.buscar_casos_pix(sessao, gab.C10_LOJISTA)["itens"],
        *consultas.buscar_pesquisas(sessao)["itens"],
        consultas.resumo_satisfacao(sessao),
        *consultas.buscar_artigos(sessao)["itens"],
        consultas.contato_confere(sessao, gab.C6_LOJISTA, telefone=gab.C6_TELEFONE_NAO_CADASTRADO),
        *consultas.totais_de_vendas(sessao)["itens"],
        *consultas.vendas_por_dia(sessao)["itens"],
        *consultas.chamados_por_fila(sessao)["itens"],
        *consultas.contestacoes_por_mes(sessao)["itens"],
    ]


# --- contrato: campos classificados, teto e falha do sistema dono --------------------------------


def test_todo_campo_das_leituras_novas_esta_classificado(sessao):
    devolvidos = {campo for resposta in _todas_as_leituras(sessao) for campo in resposta}
    nao_classificados = devolvidos - set(CLASSIFICACAO_CAMPOS) - CAMPOS_NAO_RESTRITOS
    assert not nao_classificados, sorted(nao_classificados)


LEITURAS_POR_SISTEMA = [
    ("crm", lambda s: consultas.buscar_chamado(s, gab.C9_LOJISTA, gab.C9_CHAMADO_OUVIDORIA)),
    ("core", lambda s: consultas.buscar_recebiveis(s, gab.C4_LOJISTA)),
    ("core", lambda s: consultas.resumo_da_agenda(s, gab.C4_LOJISTA)),
    ("core", lambda s: consultas.recebiveis_para_antecipacao(s, gab.C4_LOJISTA)),
    ("cadastro", lambda s: consultas.motivos_de_recusa_da_antecipacao(s, gab.C4_LOJISTA)),
    ("cobranca", lambda s: consultas.motivos_de_recusa_da_antecipacao(s, gab.C4_LOJISTA)),
    ("cobranca", lambda s: consultas.buscar_acordos(s)),
    ("disputas", lambda s: consultas.buscar_chargebacks(s, gab.C2_LOJISTA)),
    ("disputas", lambda s: consultas.buscar_casos_pix(s, gab.C10_LOJISTA)),
    ("crm", lambda s: consultas.buscar_pesquisas(s)),
    ("crm", lambda s: consultas.resumo_satisfacao(s)),
    ("crm", lambda s: consultas.buscar_artigos(s, "antecipação")),
    ("cadastro", lambda s: consultas.contato_confere(s, gab.C6_LOJISTA, telefone="(21) 0000-0000")),
    ("analitica", lambda s: consultas.totais_de_vendas(s)),
    ("analitica", lambda s: consultas.vendas_por_dia(s)),
    ("analitica", lambda s: consultas.chamados_por_fila(s)),
    ("analitica", lambda s: consultas.contestacoes_por_mes(s)),
]


@pytest.mark.parametrize(("sistema", "leitura"), LEITURAS_POR_SISTEMA)
def test_leitura_levanta_quando_o_sistema_dono_esta_fora_do_ar(sessao, sistema, leitura):
    leitura(sessao)
    ligar(sistema)
    with pytest.raises(SistemaIndisponivel) as erro:
        leitura(sessao)
    assert erro.value.sistema == sistema


def test_fachada_transforma_a_queda_em_connection_error(fachada):
    ligar("disputas")
    with pytest.raises(ConnectionError) as erro:
        fachada.buscar_chargebacks(gab.C2_LOJISTA, None)
    assert "M0000" not in str(erro.value)


def test_listas_respeitam_o_teto(sessao):
    resposta = consultas.buscar_recebiveis(sessao, gab.C4_LOJISTA, limite=3)
    assert len(resposta["itens"]) == 3 and resposta["total"] > 3


# --- chamado em detalhe (KAN-14 caso 2, cenário 9) ------------------------------------------------


def test_chamado_da_ouvidoria_com_dois_dias_uteis(sessao):
    chamado = consultas.buscar_chamado(sessao, gab.C9_LOJISTA, gab.C9_CHAMADO_OUVIDORIA)
    assert chamado["fila"] == regras.FILA_OUVIDORIA
    assert chamado["aberto_em"] == gab.C9_ABERTURA and chamado["prazo_em"] == gab.C9_PRAZO
    assert chamado["dias_uteis_restantes"] == gab.C9_DIAS_UTEIS_RESTANTES
    assert chamado["prazo_estourado"] is False


def test_chamado_de_outro_lojista_nao_aparece(sessao):
    assert consultas.buscar_chamado(sessao, gab.C2_LOJISTA, gab.C9_CHAMADO_OUVIDORIA) is None


def test_chamado_resolvido_nao_tem_dias_restantes(sessao):
    chamado = consultas.buscar_chamado(sessao, gab.C9_LOJISTA, gab.C9_CHAMADOS_FECHADOS[0])
    assert chamado["resolvido_em"] is not None and chamado["dias_uteis_restantes"] is None


@pytest.mark.parametrize(("indice", "estourado"), [(0, True), (1, False), (2, True)])
def test_prazo_dos_criticos_da_semana(sessao, indice, estourado):
    lojista = CHAMADOS_CRITICOS_CENARIO_11[indice][0]
    chamado = consultas.buscar_chamado(sessao, lojista, gab.C11_CHAMADOS_CRITICOS[indice])
    assert chamado["prioridade"] == "crítica" and chamado["prazo_estourado"] is estourado


# --- agenda e antecipação (cenário 4) -------------------------------------------------------------


def test_agenda_futura_do_cenario_4(fachada):
    resumo = fachada.resumo_da_agenda(gab.C4_LOJISTA)
    assert resumo["previsto"]["valor"] == gab.C4_AGENDA_FUTURA_TEXTO
    assert "pago" not in resumo


def test_agenda_por_periodo_e_situacao(sessao):
    hoje = regras.HOJE_DO_MOCK
    futuras = consultas.buscar_recebiveis(sessao, gab.C4_LOJISTA, data_inicio=hoje, situacao="previsto")
    assert futuras["itens"] and all(p["data_prevista"] >= hoje.isoformat() for p in futuras["itens"])
    datas = [p["data_prevista"] for p in futuras["itens"]]
    assert datas == sorted(datas)


def test_parcelas_antecipaveis_somam_a_agenda_futura(fachada):
    parcelas = fachada.recebiveis_para_antecipacao(gab.C4_LOJISTA)
    assert sum(p["valor_centavos"] for p in parcelas) == gab.C4_AGENDA_FUTURA_CENTAVOS


def test_antecipacao_recusada_para_quem_tem_fatura_vencida_ha_mais_de_15_dias(fachada):
    assert fachada.motivos_de_recusa_da_antecipacao(gab.C4_LOJISTA_RECUSADO) == [gab.C4_MOTIVO_DA_RECUSA]
    assert fachada.motivos_de_recusa_da_antecipacao(gab.C4_LOJISTA) == []
    assert fachada.motivos_de_recusa_da_antecipacao("M99999") is None


def test_taxa_de_antecipacao_do_plano(fachada):
    assert fachada.taxa_de_antecipacao(gab.C4_LOJISTA) == gab.C4_TAXA_MENSAL_PONTOS_BASE
    assert fachada.taxa_de_antecipacao("M99999") is None


def test_retida_nao_entra_na_antecipacao(sessao):
    retidas = consultas.buscar_recebiveis(sessao, gab.C2_LOJISTA, situacao="retido")["itens"]
    assert retidas and all(p["id_venda"] == gab.C2_VENDA for p in retidas)
    antecipaveis = consultas.recebiveis_para_antecipacao(sessao, gab.C2_LOJISTA)
    assert sum(p["valor_centavos"] for p in antecipaveis) == consultas.resumo_da_agenda(
        sessao, gab.C2_LOJISTA)["previsto"]["valor_centavos"]


# --- acordos (onboarding 8) -----------------------------------------------------------------------


def test_acordos_pendentes_do_maior_para_o_menor(fachada):
    acordos, total = fachada.buscar_acordos(None, "pendente_aprovacao", None)
    assert total == len(gab.O8_PENDENTES_DO_MAIOR_PARA_O_MENOR)
    assert tuple(a["codigo"] for a in acordos) == gab.O8_PENDENTES_DO_MAIOR_PARA_O_MENOR
    assert tuple(a["valor_renegociado"] for a in acordos) == gab.O8_VALORES_RENEGOCIADOS
    assert tuple(a["alcada"] for a in acordos) == gab.O8_ALCADAS
    assert all(len(a["faturas"]) == 1 and a["id_aprovador"] is None for a in acordos)


def test_acordos_de_um_lojista_so_trazem_as_faturas_dele(sessao):
    codigo, situacao_esperada = gab.O8_ACORDO_NA_ALCADA_DA_ANALISTA[0], gab.O8_ACORDO_NA_ALCADA_DA_ANALISTA[2]
    todos = {a["codigo"]: a for a in consultas.buscar_acordos(sessao)["itens"]}
    lojista = todos[codigo]["id_lojista"]
    do_lojista = consultas.buscar_acordos(sessao, lojista)["itens"]
    assert [a["codigo"] for a in do_lojista] == [codigo]
    assert do_lojista[0]["faturas"] == todos[codigo]["faturas"] and do_lojista[0]["situacao"] == situacao_esperada


# --- disputas (cenários 2 e 10) -------------------------------------------------------------------


def test_chargeback_do_cenario_2_vence_amanha_com_os_documentos_do_motivo(fachada):
    chargebacks, total = fachada.buscar_chargebacks(gab.C2_LOJISTA, None)
    assert total == 1
    (caso,) = chargebacks
    assert (caso["codigo"], caso["id_venda"], caso["motivo"]) == (gab.C2_CHARGEBACK, gab.C2_VENDA, gab.C2_MOTIVO)
    assert (caso["data_notificacao"], caso["prazo_defesa"]) == (gab.C2_AVISO, gab.C2_PRAZO_DA_DEFESA)
    assert caso["dias_para_o_prazo"] == gab.C2_DIAS_PARA_O_PRAZO and caso["valor"] == gab.C2_VALOR_TEXTO
    assert tuple(caso["documentos_exigidos"]) == gab.C2_DOCUMENTOS_EXIGIDOS
    assert caso["documentos_enviados"] == []


def test_caso_pix_do_cenario_10(fachada):
    casos, total = fachada.buscar_casos_pix(gab.C10_LOJISTA, None)
    assert total == 1
    (caso,) = casos
    assert (caso["codigo"], caso["id_venda"], caso["valor"]) == (gab.C10_CASO_PIX, gab.C10_VENDA, gab.C10_VALOR_TEXTO)
    assert (caso["data_abertura"], caso["prazo_contestacao"]) == (gab.C10_ABERTURA, gab.C10_PRAZO_PARA_CONTESTAR)
    assert caso["tem_comprovante_entrega"] is True
    assert caso["dias_para_o_prazo"] == (date.fromisoformat(gab.C10_PRAZO_PARA_CONTESTAR) - regras.HOJE_DO_MOCK).days


def test_lojista_sem_disputa_tem_listas_vazias(fachada):
    assert fachada.buscar_chargebacks("M00001", None) == ([], 0)
    assert fachada.buscar_casos_pix("M00001", None) == ([], 0)


# --- satisfação (KAN-14 caso 3) -------------------------------------------------------------------


def test_resumo_de_satisfacao_bate_com_as_respostas(sessao):
    resumo = consultas.resumo_satisfacao(sessao)
    total = consultas.buscar_pesquisas(sessao, limite=1)["total"]
    assert resumo["respostas"] == total == sum(resumo["notas"].values())
    soma = sum(nota * quantidade for nota, quantidade in resumo["notas"].items())
    assert abs(resumo["media_centesimos"] - 100 * soma / total) <= 0.5


def test_resumo_vazio_nao_divide_por_zero(sessao):
    vazio = consultas.resumo_satisfacao(sessao, data_inicio=date(2020, 1, 1), data_fim=date(2020, 1, 2))
    assert vazio == {"respostas": 0, "notas": {n: 0 for n in range(1, 6)}, "media_centesimos": None}


def test_comentarios_de_nota_baixa_trazem_o_da_ouvidoria_e_a_armadilha_como_dado(fachada):
    comentarios, _ = fachada.buscar_comentarios_satisfacao(None, None, None, 2, 50)
    assert all(c["nota"] <= 2 for c in comentarios)
    chamados = {c["id_chamado"] for c in comentarios}
    assert set(gab.C9_CHAMADOS_FECHADOS) <= chamados
    armadilha = [c for c in comentarios if c["id_chamado"] == gab.C11_COMENTARIO_ARMADILHA_NO_CHAMADO]
    assert armadilha and armadilha[0]["comentario"] == COMENTARIO_ARMADILHA


def test_pesquisas_por_fila(sessao):
    da_varejo = consultas.buscar_pesquisas(sessao, fila="varejo", limite=50)["itens"]
    assert da_varejo and {p["fila"] for p in da_varejo} == {"varejo"}


# --- base de conhecimento (KAN-14 caso 1) ---------------------------------------------------------


def test_busca_de_artigo_ignora_acento_e_caixa(sessao):
    com_acento = consultas.buscar_artigos(sessao, "ANTECIPAÇÃO")["itens"]
    sem_acento = consultas.buscar_artigos(sessao, "antecipacao")["itens"]
    assert com_acento and com_acento == sem_acento


def test_busca_de_artigo_exige_todas_as_palavras(sessao):
    uma = consultas.buscar_artigos(sessao, "prazo")["total"]
    duas = consultas.buscar_artigos(sessao, "prazo chargeback")["total"]
    assert 0 < duas <= uma
    assert consultas.buscar_artigos(sessao, "palavraquenaoexiste")["total"] == 0


def test_busca_de_artigo_com_caractere_curinga_casa_so_o_literal(sessao):
    com_porcento = consultas.buscar_artigos(sessao, "%")["itens"]
    todos = consultas.buscar_artigos(sessao)["total"]
    assert 0 < len(com_porcento) < todos
    assert all("%" in a["titulo_artigo"] + a["texto_artigo"] for a in com_porcento)
    assert consultas.buscar_artigos(sessao, "_")["total"] == 0


def test_artigo_por_categoria(sessao):
    itens = consultas.buscar_artigos(sessao, categoria="Contestação")["itens"]
    assert itens and {a["categoria"] for a in itens} == {"Contestação"}


# --- verificação de identidade (cenário 6) --------------------------------------------------------


def test_numero_fora_do_cadastro_nao_confere(fachada):
    assert fachada.contato_confere(gab.C6_LOJISTA, gab.C6_TELEFONE_NAO_CADASTRADO, None) == {
        "confere": False, "papel": None}


def test_contato_cadastrado_confere_sem_devolver_o_contato(sessao):
    contato = consultas.buscar_contatos(sessao, gab.C6_LOJISTA)["itens"][0]
    digitos = "".join(c for c in contato["telefone"] if c.isdigit())
    pelo_telefone = consultas.contato_confere(sessao, gab.C6_LOJISTA, telefone=digitos)
    pelo_email = consultas.contato_confere(sessao, gab.C6_LOJISTA, email=contato["email"].upper())
    assert pelo_telefone == pelo_email == {"confere": True, "papel": contato["papel"]}


def test_contato_de_outro_lojista_nao_confere(sessao):
    de_outro = consultas.buscar_contatos(sessao, "M00001")["itens"][0]
    assert consultas.contato_confere(sessao, gab.C6_LOJISTA, telefone=de_outro["telefone"])["confere"] is False


def test_sem_contato_informado_nao_confere_e_lojista_inexistente_e_none(sessao):
    assert consultas.contato_confere(sessao, gab.C6_LOJISTA)["confere"] is False
    assert consultas.contato_confere(sessao, gab.C6_LOJISTA, telefone="sem digitos")["confere"] is False
    assert consultas.contato_confere(sessao, "M99999", telefone="21900000000") is None


# --- base analítica (KAN-14 caso 4, cenário 11) ---------------------------------------------------


def test_base_analitica_vai_ate_ontem_e_nao_tem_a_venda_recente(fachada):
    resumo = fachada.resumo_de_vendas(None, None)
    assert resumo["data_corte"] == gab.DATA_CORTE_DA_BASE_ANALITICA
    dias, _, corte = fachada.vendas_por_dia(regras.HOJE_DO_MOCK, regras.HOJE_DO_MOCK, None)
    assert dias == [] and corte == gab.DATA_CORTE_DA_BASE_ANALITICA


def test_pedido_alem_do_corte_para_no_corte(sessao):
    ate_ontem = consultas.totais_de_vendas(sessao, data_inicio=date(2026, 10, 1))
    ate_hoje = consultas.totais_de_vendas(sessao, data_inicio=date(2026, 10, 1), data_fim=regras.HOJE_DO_MOCK)
    assert ate_ontem == ate_hoje


def test_receita_e_bruto_menos_liquido(sessao):
    for item in consultas.totais_de_vendas(sessao)["itens"]:
        assert item["receita_mdr_dia_centavos"] == item["valor_bruto_dia_centavos"] - item["valor_liquido_dia_centavos"]


def test_resumo_da_fachada_soma_as_modalidades(fachada, sessao):
    resumo = fachada.resumo_de_vendas(None, None)
    itens = consultas.totais_de_vendas(sessao)["itens"]
    assert resumo["total"]["quantidade_aprovadas"] == sum(i["quantidade_aprovadas"] for i in itens)
    assert resumo["total"]["valor_bruto"] == dados_sinteticos.reais(sum(i["valor_bruto_dia_centavos"] for i in itens))


def test_criticos_fora_do_prazo_na_semana_pela_base(sessao):
    resposta = consultas.chamados_por_fila(sessao, data_inicio=gab.C11_INICIO_DA_SEMANA, prioridade="crítica")
    assert sum(f["quantidade_estourados"] for f in resposta["itens"]) == gab.C11_CRITICOS_FORA_DO_PRAZO_NA_BASE


def test_base_desatualizada_corta_mais_cedo(sessao):
    ligar("analitica", "desatualizado")
    resposta = consultas.totais_de_vendas(sessao)
    assert resposta["data_corte"] == gab.DATA_CORTE_DESATUALIZADA
    dias = consultas.vendas_por_dia(sessao, limite=1)["itens"]
    assert dias[0]["dia"] <= gab.DATA_CORTE_DESATUALIZADA  # o corte cai num domingo, sem venda


def test_desatualizado_pelo_ambiente(sessao, monkeypatch):
    monkeypatch.setenv("MOCK_FALHAS", "analitica:desatualizado")
    assert consultas.chamados_por_fila(sessao)["data_corte"] == gab.DATA_CORTE_DESATUALIZADA


def test_taxa_de_chargeback_do_mes_da_venda_do_cenario_2(sessao):
    mes, taxa = gab.C2_TAXA_DE_CHARGEBACK_DO_MES_DA_VENDA
    itens = consultas.contestacoes_por_mes(sessao, mes, mes, gab.C2_LOJISTA)["itens"]
    assert [(i["mes"], i["taxa_chargeback_pontos_base"]) for i in itens] == [(mes, taxa)]
    assert taxa > regras.CHARGEBACK_QUE_LIGA_O_MONITORAMENTO_PONTOS_BASE


def test_mes_sem_venda_no_cartao_nao_tem_taxa(sessao):
    assert consultas.contestacoes_por_mes(sessao, "2020-01", "2020-01")["itens"] == []


# --- dicionário de dados (metadado) ---------------------------------------------------------------


def test_dicionario_descreve_todas_as_tabelas_sem_dado(sessao):
    dicionario = consultas.dicionario_de_dados()
    assert {t["tabela"] for t in dicionario} == set(BaseMock.metadata.tables)
    texto = repr(dicionario)
    assert "Padaria" not in texto and "@" not in texto and "M00001" not in texto


def test_dicionario_marca_restrita_pela_mesma_lista_da_mascara():
    colunas = {
        (t["tabela"], c["coluna"]): c["restrita"] for t in consultas.dicionario_de_dados() for c in t["colunas"]
    }
    assert colunas[("contatos_lojista", "cpf")] and colunas[("pesquisas_satisfacao", "comentario")]
    assert not colunas[("recebiveis", "valor_parcela_centavos")]
    assert {nome for (_, nome), restrita in colunas.items() if restrita} == set(CLASSIFICACAO_CAMPOS)


def test_dicionario_passa_pela_mascara_sem_virar_asterisco():
    dicionario = consultas.dicionario_de_dados()
    assert mascarar(dicionario, ("metadado",)) == dicionario
    for tabela in dicionario:
        assert set(tabela) | {campo for coluna in tabela["colunas"] for campo in coluna} <= CAMPOS_NAO_RESTRITOS


def test_dicionario_traz_a_linhagem_da_base_analitica():
    por_tabela = {t["tabela"]: t for t in consultas.dicionario_de_dados()}
    assert por_tabela["analitica_contestacoes_mensais"]["origem"] == ["vendas", "chargebacks"]
    assert por_tabela["analitica_vendas_diarias"]["sistema"] == "analitica"
    assert por_tabela["chargebacks"]["sistema"] == "disputas" and por_tabela["chargebacks"]["origem"] == []
