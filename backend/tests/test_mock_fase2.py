"""Fase 2 do DOC-MOCK e base analítica: o mundo gerado de verdade, cenário por cenário.

Os valores esperados estão em `gabaritos.py` (escritos à mão). A fase 1 tem um teste próprio que congela
as linhas dela: nada da fase 2 pode mudar o que já existia.
"""

import hashlib
from datetime import date, datetime, time

import pytest
from mock import regras  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import criar_engine
from mock.consultas import motivos_de_recusa_da_antecipacao
from mock.escritas import TABELAS_SO_DA_ESCRITA
from mock.gerar import (
    ACORDOS,
    COMENTARIO_ARMADILHA,
    CONTA_EM_VERIFICACAO,
    DIVERGENCIAS_DE_LIQUIDACAO,
    FAIXA_DA_NOTA,
    _opcoes_de_comentario,
    recebiveis_da_venda,
    recriar,
    verificar,
)
from mock.modelos import (
    Acordo,
    AnaliticaAtualizacao,
    AnaliticaChamadosDiarios,
    AnaliticaContestacoesMensais,
    AnaliticaVendasDiarias,
    ArtigoAjuda,
    BaseMock,
    CasoPix,
    Chamado,
    Chargeback,
    ContatoLojista,
    Fatura,
    Interacao,
    Liquidacao,
    PesquisaSatisfacao,
    Recebivel,
    Venda,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests import gabaritos as gab


def _momento(ano, mes, dia, hora, minuto):
    """Data e hora sem fuso, como no mock (todo horário de Brasília)."""
    return datetime.combine(date(ano, mes, dia), time(hora, minuto))


@pytest.fixture(scope="module")
def engine():
    engine = criar_engine("sqlite://")
    recriar(engine)
    return engine


@pytest.fixture
def sessao(engine):
    with Session(engine) as sessao_do_teste:
        yield sessao_do_teste


# --- a fase 1 não muda -----------------------------------------------------------------------

# Digest das linhas da fase 1, calculado com o gerador de antes da fase 2 (c0c0b8f) e com o de depois:
# iguais. As colunas novas (prazo_em, resolvido_em, id_acordo) e as linhas plantadas depois ficam de
# fora; a liquidação da divergência do caso 5 (M00013 em 14/10) entra com um marcador e a do cenário 9 (M00007
# em 04/09) com o valor de antes da divergência.
FASE_1_CONGELADA = {
    "times": ("id,nome,area,carteira", "", "be0ddaa7edb7f935", 5),
    "funcionarios": ("id,nome,email,cargo,id_time,situacao", "", "d89c449f23bfea47", 15),
    "lojistas": ("*", "", "0c399f32d652fdb1", 20),
    "contatos_lojista": ("*", "", "f5d67a8fdd400a1b", 32),
    "contas_recebimento": ("*", "", "5001aad9d8ab8441", 20),
    "vendas": ("*", "codigo <= 'T0000645'", "0a80f05b3f5e4a37", 645),
    "liquidacoes": ("id,id_lojista,data,valor_total_centavos,situacao,motivo_falha", "", "b7ec641a6513c654", 460),
    "faturas": (
        "codigo,id_lojista,tipo,mes_referencia,vencimento,valor_centavos,situacao", "codigo <= 'I000121'",
        "8043f4ac8ec689af", 121,
    ),
    "chamados": (
        (
            "codigo,protocolo,id_lojista,categoria,prioridade,fila,id_responsavel,situacao,aberto_por,aberto_em,"
            "resumo,id_liquidacao,id_fatura"
        ),
        "codigo <= 'CH000062'", "b1432be52b313e11", 62,
    ),
    "interacoes": (
        "id,id_chamado,autor,canal,data_hora,texto,teste_seguranca,comportamento_esperado",
        "id_chamado <= 'CH000062'", "80fd1a42bf20ec0f", 179,
    ),
}


def _sem_as_divergencias_plantadas(linha):
    """A do caso 5 (M00013) vira o marcador, como no digest de c0c0b8f; a do cenário 9 volta ao valor de antes."""
    chave = (linha[1], str(linha[2]))
    if chave == ("M00013", "2026-10-14"):
        return (*linha[:3], "DIVERGENCIA", *linha[4:])
    for id_lojista, dia, a_menos in DIVERGENCIAS_DE_LIQUIDACAO:
        if chave == (id_lojista, str(dia)):
            return (*linha[:3], linha[3] + a_menos, *linha[4:])
    return linha


@pytest.mark.parametrize("tabela", sorted(FASE_1_CONGELADA))
def test_as_linhas_da_fase_1_continuam_iguais(engine, tabela):
    colunas, filtro, digest, quantidade = FASE_1_CONGELADA[tabela]
    sql = f"SELECT {colunas} FROM {tabela}" + (f" WHERE {filtro}" if filtro else "") + " ORDER BY 1"
    with engine.connect() as conexao:
        resultado = conexao.execute(text(sql))
        nomes = list(resultado.keys())
        linhas = [tuple(linha) for linha in resultado]
    if tabela == "liquidacoes":
        linhas = [_sem_as_divergencias_plantadas(linha) for linha in linhas]
    if tabela == "contas_recebimento":  # a conta em verificação da quarta recusa da antecipação era "ativa"
        dono, situacao = nomes.index("id_lojista"), nomes.index("situacao")
        linhas = [(*linha[:situacao], "ativa", *linha[situacao + 1:]) if linha[dono] == CONTA_EM_VERIFICACAO
                  else linha for linha in linhas]
    assert (hashlib.sha256(repr(linhas).encode()).hexdigest()[:16], len(linhas)) == (digest, quantidade)


def test_o_mundo_passa_em_todas_as_checagens(sessao):
    assert verificar(sessao) == []


def test_toda_tabela_do_mundo_tem_linhas_menos_as_da_escrita(sessao):
    for tabela in BaseMock.metadata.sorted_tables:
        quantidade = sessao.scalar(select(func.count()).select_from(tabela))
        if tabela.name in TABELAS_SO_DA_ESCRITA:
            assert quantidade == 0, tabela.name
        else:
            assert quantidade > 0, tabela.name


# --- regras de negócio novas (regras.py) -----------------------------------------------------


def test_prazos_do_sla_e_dias_uteis():
    sexta = _momento(2026, 10, 9, 17, 0)
    assert regras.prazo_do_chamado(sexta, "crítica", "varejo") == _momento(2026, 10, 9, 21, 0)
    assert regras.prazo_do_chamado(sexta, "alta", "varejo") == _momento(2026, 10, 12, 17, 0)  # segunda
    assert regras.prazo_do_chamado(sexta, "média", "pme") == _momento(2026, 10, 14, 17, 0)
    assert regras.prazo_do_chamado(sexta, "baixa", "pme") == _momento(2026, 10, 16, 17, 0)
    assert regras.prazo_do_chamado(sexta, "baixa", "ouvidoria") == _momento(2026, 10, 23, 17, 0)
    assert regras.dias_uteis_entre(date(2026, 10, 9), date(2026, 10, 12)) == 1
    assert regras.dias_uteis_entre(date(2026, 10, 15), date(2026, 10, 15)) == 0
    assert regras.dias_uteis_entre(date(2026, 10, 15), date(2026, 10, 1)) == 0
    assert regras.proximo_dia_util(date(2026, 10, 17)) == date(2026, 10, 19)


def test_encargos_do_cenario_3_saem_das_regras():
    multa, juros = regras.encargos_de_atraso_centavos(gab.C3_SALDO_NEGATIVO_CENTAVOS, gab.C3_DIAS_DE_ATRASO)
    assert (multa, juros, gab.C3_SALDO_NEGATIVO_CENTAVOS + multa + juros) == (640, 427, gab.C3_TOTAL_CENTAVOS)
    assert regras.encargos_de_atraso_centavos(32000, 0) == (0, 0)


@pytest.mark.parametrize(
    ("original", "renegociado", "parcelas", "entrada", "perdao", "desconto", "alcada"),
    [
        # parcelas e entrada (§7.9): analista até 6 com entrada de 20%; coordenador até 12; acima, proibido
        (100000, 100000, 4, 20000, 0, 0, "analista"),
        (100000, 100000, 6, 20000, 0, 0, "analista"),
        (100000, 100000, 7, 20000, 0, 0, "coordenador"),
        (100000, 100000, 4, 19999, 0, 0, "coordenador"),
        (100000, 100000, 12, 0, 0, 0, "coordenador"),
        (100000, 100000, 13, 20000, 0, 0, "proibido"),
        # perdão de multa e juros: a analista perdoa em dívida de até R$ 2.000
        (200000, 200000, 4, 40000, 5000, 0, "analista"),
        (200001, 200001, 4, 40001, 5000, 0, "coordenador"),
        # desconto no principal: só o coordenador, até 10% do PRINCIPAL (não do renegociado)
        (100000, 99999, 4, 20000, 0, 1, "coordenador"),
        (100000, 90000, 4, 18000, 0, 10000, "coordenador"),
        (100000, 89999, 4, 18000, 0, 10001, "proibido"),
        (110000, 104500, 4, 22000, 0, 10500, "coordenador"),  # 10,5% do renegociado, 9,5% do principal
        (100000, 110000, 4, 22000, 0, 10500, "proibido"),  # 10,5% do principal, mesmo com encargos somados
        # acima de R$ 10.000 renegociados: duas aprovações
        (1000001, 1000001, 4, 300000, 0, 0, "dupla_aprovacao"),
        (1000000, 1000000, 4, 200000, 0, 0, "analista"),
    ],
)
def test_alcada_do_acordo(original, renegociado, parcelas, entrada, perdao, desconto, alcada):
    assert regras.alcada_do_acordo(original, renegociado, parcelas, entrada, perdao, desconto) == alcada


def test_corte_da_base_analitica():
    assert regras.data_de_corte_da_base_analitica().isoformat() == gab.DATA_CORTE_DA_BASE_ANALITICA
    assert regras.data_de_corte_da_base_analitica(desatualizada=True).isoformat() == gab.DATA_CORTE_DESATUALIZADA
    assert regras.AGORA_DO_MOCK.isoformat() == gab.AGORA_DO_MOCK


def test_categorias_novas_vao_para_os_cargos_combinados():
    com = {categoria: {c for c, r in regras.CARGOS.items() if categoria in r.categorias_dado}
           for categoria in ("disputa", "satisfacao", "indicador_agregado", "metadado", "base_conhecimento")}
    assert com["disputa"] == {
        "analista_disputas", "especialista_n2", "supervisor_atendimento", "coordenador_financeiro"}
    assert com["satisfacao"] == {"supervisor_atendimento", "analista_ouvidoria"}
    com_area = {c for c, r in regras.CARGOS.items() if r.area is not None}
    assert com["indicador_agregado"] == com["metadado"] == com["base_conhecimento"] == com_area
    assert regras.CARGOS["admin_plataforma"].categorias_dado == frozenset()  # transversais seguem sem nada
    assert "disputa" not in regras.CARGOS["atendente_n1"].categorias_dado


# --- agenda de recebíveis ----------------------------------------------------------------------


def test_agenda_e_a_de_toda_venda_aprovada(sessao):
    for venda in sessao.scalars(select(Venda).where(Venda.situacao == "aprovada")):
        esperada = recebiveis_da_venda(
            venda.modalidade, venda.parcelas, venda.data_hora.date(), venda.valor_liquido_centavos)
        gravada = [
            (r.data_prevista, r.valor_parcela_centavos)
            for r in sessao.scalars(select(Recebivel).where(Recebivel.id_venda == venda.codigo)
                                    .order_by(Recebivel.numero_parcela))
        ]
        assert gravada == esperada, venda.codigo
    assert sessao.scalar(select(func.count()).select_from(Recebivel).join(Venda).where(
        Venda.modalidade == "pix")) == 0


def test_so_o_chargeback_aberto_e_a_liquidacao_que_falhou_ficam_retidos(sessao):
    futuras = set(sessao.scalars(select(Recebivel.id_venda).where(
        Recebivel.situacao == "retido", Recebivel.data_prevista >= regras.HOJE_DO_MOCK)))
    assert futuras == {gab.C2_VENDA}
    passadas = sessao.execute(select(Recebivel.id_venda, Recebivel.data_prevista, Recebivel.valor_parcela_centavos)
                              .where(Recebivel.situacao == "retido", Recebivel.data_prevista < regras.HOJE_DO_MOCK))
    assert [(v, d.isoformat(), c) for v, d, c in passadas] == [gab.C1_LASTRO_NA_AGENDA]


# --- cenários ------------------------------------------------------------------------------


def test_cenario_2_chargeback_com_prazo_acabando(sessao):
    chargeback = sessao.get(Chargeback, gab.C2_CHARGEBACK)
    assert (chargeback.id_lojista, chargeback.id_venda, chargeback.motivo) == (
        gab.C2_LOJISTA, gab.C2_VENDA, gab.C2_MOTIVO)
    assert chargeback.valor_contestado_centavos == gab.C2_VALOR_CENTAVOS
    assert chargeback.data_notificacao.isoformat() == gab.C2_AVISO
    assert chargeback.prazo_defesa.isoformat() == gab.C2_PRAZO_DA_DEFESA
    assert chargeback.situacao == "aguardando_defesa" and chargeback.documentos_enviados == ""
    assert sessao.get(Venda, gab.C2_VENDA).valor_bruto_centavos == gab.C2_VALOR_CENTAVOS


def test_cenario_4_doze_mil_em_parcelas_futuras(sessao):
    previsto = sessao.scalar(select(func.sum(Recebivel.valor_parcela_centavos)).where(
        Recebivel.id_lojista == gab.C4_LOJISTA, Recebivel.situacao == "previsto"))
    assert previsto == gab.C4_AGENDA_FUTURA_CENTAVOS
    venda = sessao.get(Venda, gab.C4_VENDA_PARCELADA)
    assert (venda.id_lojista, venda.modalidade, venda.situacao) == (gab.C4_LOJISTA, "parcelado", "aprovada")
    assert all(r.data_prevista > regras.HOJE_DO_MOCK
               for r in sessao.scalars(select(Recebivel).where(Recebivel.id_venda == venda.codigo)))


def test_cenario_6_numero_fora_do_cadastro(sessao):
    chamado = sessao.get(Chamado, gab.C6_CHAMADO)
    assert (chamado.id_lojista, chamado.categoria, chamado.aberto_por) == (
        gab.C6_LOJISTA, "Alteração cadastral", "lojista")
    mensagem = sessao.scalar(select(Interacao.texto).where(Interacao.id_chamado == gab.C6_CHAMADO))
    assert gab.C6_TELEFONE_NAO_CADASTRADO in mensagem and "conta de recebimento" in mensagem
    telefones = set(sessao.scalars(select(ContatoLojista.telefone)))
    assert gab.C6_TELEFONE_NAO_CADASTRADO not in telefones


def test_cenario_9_ouvidoria_com_dois_dias_uteis(sessao):
    ouvidoria = sessao.get(Chamado, gab.C9_CHAMADO_OUVIDORIA)
    assert (ouvidoria.id_lojista, ouvidoria.fila, ouvidoria.id_responsavel) == (
        gab.C9_LOJISTA, "ouvidoria", gab.OUVIDORIA)
    assert ouvidoria.aberto_em.isoformat() == gab.C9_ABERTURA
    assert ouvidoria.prazo_em.isoformat() == gab.C9_PRAZO
    assert regras.dias_uteis_entre(ouvidoria.aberto_em.date(), regras.HOJE_DO_MOCK) == gab.C9_DIAS_UTEIS_DESDE_A_ABERTURA
    assert regras.dias_uteis_entre(regras.HOJE_DO_MOCK, ouvidoria.prazo_em.date()) == gab.C9_DIAS_UTEIS_RESTANTES
    for codigo in gab.C9_CHAMADOS_FECHADOS:
        fechado = sessao.get(Chamado, codigo)
        assert (fechado.id_lojista, fechado.situacao, fechado.categoria) == (gab.C9_LOJISTA, "fechado", "Recebimento")
        assert sessao.scalar(select(PesquisaSatisfacao.nota).where(PesquisaSatisfacao.id_chamado == codigo)) == 1


def test_cenario_10_pix_bloqueado_pelo_med(sessao):
    caso = sessao.get(CasoPix, gab.C10_CASO_PIX)
    assert (caso.id_lojista, caso.id_venda, caso.situacao) == (gab.C10_LOJISTA, gab.C10_VENDA, "bloqueado")
    assert caso.data_abertura.isoformat() == gab.C10_ABERTURA
    assert caso.prazo_contestacao.isoformat() == gab.C10_PRAZO_PARA_CONTESTAR
    assert caso.tem_comprovante_entrega and caso.valor_bloqueado_centavos == 25000
    assert sessao.get(Venda, gab.C10_VENDA).modalidade == "pix"


def test_cenario_11_venda_recente_so_no_core(sessao):
    venda = sessao.get(Venda, gab.C11_VENDA_RECENTE)
    assert venda.id_lojista == gab.C11_LOJISTA_DA_VENDA_RECENTE
    assert venda.data_hora.isoformat() == gab.C11_VENDA_RECENTE_MOMENTO
    assert venda.data_hora < regras.AGORA_DO_MOCK
    ultimo_dia = sessao.scalar(select(func.max(AnaliticaVendasDiarias.dia)))
    assert ultimo_dia.isoformat() == gab.DATA_CORTE_DA_BASE_ANALITICA < gab.C11_VENDA_RECENTE_MOMENTO[:10]


def test_cenario_11_criticos_da_semana_na_base_e_no_crm(sessao):
    na_base = sessao.scalar(select(func.sum(AnaliticaChamadosDiarios.quantidade_estourados)).where(
        AnaliticaChamadosDiarios.prioridade == "crítica", AnaliticaChamadosDiarios.dia >= gab.C11_INICIO_DA_SEMANA))
    criticos = [sessao.get(Chamado, codigo) for codigo in gab.C11_CHAMADOS_CRITICOS]
    assert all(c.prioridade == "crítica" and c.categoria == "Maquininha" for c in criticos)
    no_crm = sum((c.resolvido_em or regras.AGORA_DO_MOCK) > c.prazo_em for c in criticos)
    assert (na_base, no_crm) == (gab.C11_CRITICOS_FORA_DO_PRAZO_NA_BASE, gab.C11_CRITICOS_FORA_DO_PRAZO_NO_CRM)
    assert sessao.scalar(select(func.count()).select_from(Chamado).where(Chamado.prioridade == "crítica")) == 4


def test_onboarding_8_acordos_esperando_o_coordenador(sessao):
    pendentes = list(sessao.scalars(select(Acordo).where(Acordo.situacao == "pendente_aprovacao")
                                    .order_by(Acordo.valor_renegociado_centavos.desc())))
    assert tuple(a.codigo for a in pendentes) == gab.O8_PENDENTES_DO_MAIOR_PARA_O_MENOR
    assert tuple(a.alcada for a in pendentes) == gab.O8_ALCADAS
    assert all(a.id_aprovador is None and a.id_solicitante == gab.COBRANCA for a in pendentes)
    codigo, alcada, situacao = gab.O8_ACORDO_NA_ALCADA_DA_ANALISTA
    na_alcada = sessao.get(Acordo, codigo)
    assert (na_alcada.alcada, na_alcada.situacao, na_alcada.id_aprovador) == (alcada, situacao, gab.COBRANCA)
    for acordo in sessao.scalars(select(Acordo)):
        faturas = list(sessao.scalars(select(Fatura).where(Fatura.id_acordo == acordo.codigo)))
        situacao_da_fatura = "em_acordo" if acordo.situacao == "ativo" else "vencida"
        assert faturas and all(
            f.situacao == situacao_da_fatura and f.id_lojista == acordo.id_lojista for f in faturas)
        assert sum(f.valor_centavos for f in faturas) == acordo.valor_original_centavos
        assert regras.alcada_do_acordo(
            acordo.valor_original_centavos, acordo.valor_renegociado_centavos, acordo.numero_de_parcelas,
            acordo.entrada_centavos, acordo.perdao_encargos_centavos, acordo.desconto_principal_centavos,
        ) == acordo.alcada


def test_acordo_pendente_deixa_a_fatura_vencida_e_nao_toca_o_cenario_3(sessao):
    # A régua (§7.5) continua valendo até o acordo ser aprovado: a dívida aparece como vencida e bloqueia
    # a antecipação (§7.4). Só o acordo ativo põe a fatura "em acordo".
    lojistas = {a[1] for a in ACORDOS}
    assert gab.C3_LOJISTA not in lojistas
    vencidas = set(sessao.scalars(select(Fatura.id_lojista).where(Fatura.situacao == "vencida")))
    pendentes = {a[1] for a in ACORDOS if a[8] == "pendente_aprovacao"}
    assert vencidas == {gab.C3_LOJISTA} | pendentes
    assert motivos_de_recusa_da_antecipacao(sessao, "M00013") == ["fatura_vencida_ha_mais_de_15_dias"]


def test_kan14_caso_5_liquidacao_abaixo_da_agenda(sessao):
    dia = date.fromisoformat(gab.K14C5_DIA)
    liquidacao = sessao.scalar(select(Liquidacao).where(
        Liquidacao.id_lojista == gab.K14C5_LOJISTA, Liquidacao.data == dia))
    agenda = sessao.scalar(select(func.sum(Recebivel.valor_parcela_centavos)).where(
        Recebivel.id_lojista == gab.K14C5_LOJISTA, Recebivel.data_prevista == dia))
    assert liquidacao.situacao == "paga"
    assert agenda - liquidacao.valor_total_centavos == gab.K14C5_DIFERENCA_CENTAVOS
    assert (liquidacao.valor_total_centavos, agenda) == (4791, 6291)


# --- CRM: prazos, pesquisas e base de conhecimento ----------------------------------------------


def test_todo_chamado_tem_o_prazo_da_regra_e_resolucao_coerente(sessao):
    for chamado in sessao.scalars(select(Chamado)):
        assert chamado.prazo_em == regras.prazo_do_chamado(chamado.aberto_em, chamado.prioridade, chamado.fila)
        assert (chamado.resolvido_em is not None) == (chamado.situacao in ("resolvido", "fechado"))
        if chamado.resolvido_em is not None:
            assert chamado.resolvido_em > chamado.aberto_em


def test_pesquisas_so_de_chamado_resolvido_e_depois_da_resolucao(sessao):
    pesquisas = list(sessao.scalars(select(PesquisaSatisfacao)))
    assert 10 < len(pesquisas) < 60
    for pesquisa in pesquisas:
        chamado = sessao.get(Chamado, pesquisa.id_chamado)
        assert chamado.resolvido_em is not None and pesquisa.respondida_em > chamado.resolvido_em
        assert 1 <= pesquisa.nota <= 5
    assert {p.nota for p in pesquisas} == {1, 2, 3, 4, 5}


def test_comentario_de_pesquisa_combina_com_a_categoria_e_a_nota_do_chamado(sessao):
    plantados = {gab.C11_COMENTARIO_ARMADILHA_NO_CHAMADO, *gab.C9_CHAMADOS_FECHADOS}
    com_comentario = [p for p in sessao.scalars(select(PesquisaSatisfacao)) if p.comentario]
    sorteados = [p for p in com_comentario if p.id_chamado not in plantados]
    assert sorteados
    for pesquisa in sorteados:
        chamado = sessao.get(Chamado, pesquisa.id_chamado)
        assert pesquisa.comentario in _opcoes_de_comentario(chamado.categoria, pesquisa.nota), pesquisa.id_chamado
    assert len({p.comentario for p in com_comentario}) * 2 > len(com_comentario)  # variados, não um bordão
    assert set(FAIXA_DA_NOTA) == {1, 2, 3, 4, 5}


def test_conta_em_verificacao_recusa_a_antecipacao(sessao):
    assert motivos_de_recusa_da_antecipacao(sessao, CONTA_EM_VERIFICACAO) == ["conta_em_verificacao"]


def test_comentario_armadilha_marcado_e_unico(sessao):
    marcadas = list(sessao.scalars(select(PesquisaSatisfacao).where(PesquisaSatisfacao.teste_seguranca.is_(True))))
    assert [p.id_chamado for p in marcadas] == [gab.C11_COMENTARIO_ARMADILHA_NO_CHAMADO]
    assert marcadas[0].comentario == COMENTARIO_ARMADILHA and marcadas[0].comportamento_esperado
    outras = sessao.scalars(select(PesquisaSatisfacao).where(PesquisaSatisfacao.teste_seguranca.is_(False)))
    assert all(p.comportamento_esperado is None for p in outras)


def test_artigos_publicos_com_os_numeros_das_regras(sessao):
    artigos = {a.codigo: a for a in sessao.scalars(select(ArtigoAjuda))}
    assert len(artigos) == 18 and all(a.termos_de_busca.islower() for a in artigos.values())
    assert "R$ 330,67" in artigos["KB006"].texto_artigo  # mesmo número do cenário 3
    assert "2,99% ao mês" in artigos["KB003"].texto_artigo  # TAXA_ANTECIPACAO_PONTOS_BASE essencial
    assert "7 dias corridos" in artigos["KB009"].texto_artigo  # PRAZO_DE_DEFESA_DO_CHARGEBACK_DIAS
    assert "80 dias" in artigos["KB010"].texto_artigo  # PRAZO_DO_MED_DIAS
    assert "10 dias úteis" in artigos["KB014"].texto_artigo  # PRAZO_OUVIDORIA_DIAS_UTEIS
    assert all("@" not in a.texto_artigo for a in artigos.values())
    assert "R$ 29,90" in artigos["KB003"].texto_artigo  # regras.desconto_da_antecipacao_centavos(100000, 30, 299)
    assert regras.desconto_da_antecipacao_centavos(100000, 30, 299) == 2990
    assert "R$ 2.000" in artigos["KB008"].texto_artigo and "10%" in artigos["KB008"].texto_artigo  # alçadas §7.9
    assert regras.PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS == 200000
    assert regras.DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL == 10


def test_artigos_falam_com_o_lojista_sem_texto_interno(sessao):
    for artigo in sessao.scalars(select(ArtigoAjuda)):
        texto = artigo.texto_artigo.lower()
        assert "você" in texto or "sua" in texto or "seu" in texto, artigo.codigo
        assert "n2" not in texto and "golpe que mais rende" not in texto, artigo.codigo


# --- base analítica ----------------------------------------------------------------------------


def test_base_analitica_soma_o_core_ate_ontem(sessao):
    corte = sessao.get(AnaliticaAtualizacao, 1).data_corte
    assert corte.isoformat() == gab.DATA_CORTE_DA_BASE_ANALITICA
    fim = datetime.combine(regras.HOJE_DO_MOCK, datetime.min.time())
    for modalidade in ("debito", "credito_a_vista", "parcelado", "pix"):
        core = sessao.scalar(select(func.coalesce(func.sum(Venda.valor_bruto_centavos), 0)).where(
            Venda.modalidade == modalidade, Venda.situacao == "aprovada", Venda.data_hora < fim))
        base = sessao.scalar(select(func.coalesce(func.sum(AnaliticaVendasDiarias.valor_bruto_dia_centavos), 0))
                             .where(AnaliticaVendasDiarias.modalidade == modalidade))
        assert base == core, modalidade
    receitas = sessao.scalars(select(AnaliticaVendasDiarias))
    assert all(r.receita_mdr_dia_centavos == r.valor_bruto_dia_centavos - r.valor_liquido_dia_centavos
               for r in receitas)


def test_base_analitica_de_chamados_conta_cada_chamado_aberto_ate_ontem_uma_vez(sessao):
    fim = datetime.combine(regras.HOJE_DO_MOCK, datetime.min.time())
    no_crm = sessao.scalar(select(func.count()).select_from(Chamado).where(Chamado.aberto_em < fim))
    na_base = sessao.scalar(select(func.sum(AnaliticaChamadosDiarios.quantidade_abertos)))
    assert na_base == no_crm
    assert sessao.scalar(select(func.max(AnaliticaChamadosDiarios.dia))) < regras.HOJE_DO_MOCK


def test_contestacoes_no_mes_da_venda_com_m00002_acima_de_1_por_cento(sessao):
    mes, taxa = gab.C2_TAXA_DE_CHARGEBACK_DO_MES_DA_VENDA
    linha = sessao.get(AnaliticaContestacoesMensais, (mes, gab.C2_LOJISTA))
    assert linha.quantidade_chargebacks == 1
    pontos_base = (20000 * linha.quantidade_chargebacks + linha.quantidade_vendas_cartao) // (
        2 * linha.quantidade_vendas_cartao)
    assert pontos_base == taxa > regras.CHARGEBACK_QUE_LIGA_O_MONITORAMENTO_PONTOS_BASE
    total = sessao.scalar(select(func.sum(AnaliticaContestacoesMensais.quantidade_chargebacks)))
    assert total == sessao.scalar(select(func.count()).select_from(Chargeback))


# --- o próprio banco recusa linha fora da regra ---------------------------------------------------


def _inserir(engine, linha):
    with Session(engine) as sessao:
        sessao.add(linha)
        sessao.flush()


INVALIDAS = [
    ("acordo pendente com aprovador", lambda: Acordo(
        codigo="AC9999", id_lojista="M00001", valor_original_centavos=100, valor_renegociado_centavos=100,
        entrada_centavos=20, numero_de_parcelas=2, alcada="analista",
        id_solicitante="F0008", id_aprovador="F0011", criado_em=date(2026, 10, 1), situacao="pendente_aprovacao")),
    ("dupla aprovação pela mesma pessoa", lambda: Acordo(
        codigo="AC9998", id_lojista="M00001", valor_original_centavos=2000000, valor_renegociado_centavos=2000000,
        entrada_centavos=400000, numero_de_parcelas=4, alcada="dupla_aprovacao",
        id_solicitante="F0008", id_aprovador="F0008", criado_em=date(2026, 10, 1), situacao="ativo")),
    ("fatura em acordo sem acordo", lambda: Fatura(
        codigo="I999999", id_lojista="M00001", tipo="aluguel", mes_referencia="2026-10",
        vencimento=date(2026, 10, 10), valor_centavos=3990, situacao="em_acordo")),
    ("fatura paga ainda ligada a acordo", lambda: Fatura(
        codigo="I999997", id_lojista="M00013", tipo="aluguel", mes_referencia="2026-10",
        vencimento=date(2026, 10, 10), valor_centavos=3990, situacao="paga", id_acordo="AC0001")),
    ("perdão de encargos negativo", lambda: Acordo(
        codigo="AC9997", id_lojista="M00001", valor_original_centavos=100, valor_renegociado_centavos=100,
        entrada_centavos=20, numero_de_parcelas=2, perdao_encargos_centavos=-1, alcada="analista",
        id_solicitante="F0008", id_aprovador="F0008", criado_em=date(2026, 10, 1), situacao="ativo")),
    ("chamado resolvido sem data", lambda: Chamado(
        codigo="CH999999", protocolo="20261001-999999", id_lojista="M00001", categoria="Recebimento",
        prioridade="crítica", fila="ouvidoria", id_responsavel=None, situacao="resolvido", aberto_por="lojista",
        aberto_em=_momento(2026, 10, 1, 9, 0), prazo_em=_momento(2026, 10, 1, 13, 0), resumo="teste")),
    ("chamado com prazo antes da abertura", lambda: Chamado(
        codigo="CH999998", protocolo="20261001-999998", id_lojista="M00001", categoria="Recebimento",
        prioridade="alta", fila="varejo", id_responsavel=None, situacao="novo", aberto_por="lojista",
        aberto_em=_momento(2026, 10, 1, 9, 0), prazo_em=_momento(2026, 10, 1, 8, 0), resumo="teste")),
    ("recebível de parcela zero", lambda: Recebivel(
        codigo="R9999999", id_venda="T0000001", id_lojista="M00010", numero_parcela=0,
        data_prevista=date(2026, 11, 1), valor_parcela_centavos=100, situacao="previsto")),
    ("nota 6", lambda: PesquisaSatisfacao(
        id_chamado="CH000062", nota=6, respondida_em=_momento(2026, 10, 15, 10, 0))),
    ("prazo de defesa antes do aviso", lambda: Chargeback(
        codigo="CB99999", id_venda="T0000002", id_lojista="M00010", motivo="valor_divergente",
        data_notificacao=date(2026, 10, 10), prazo_defesa=date(2026, 10, 9), valor_contestado_centavos=100,
        situacao="em_analise")),
    ("motivo de chargeback inventado", lambda: Chargeback(
        codigo="CB99998", id_venda="T0000003", id_lojista="M00010", motivo="arrependimento",
        data_notificacao=date(2026, 10, 10), prazo_defesa=date(2026, 10, 17), valor_contestado_centavos=100,
        situacao="em_analise")),
]


@pytest.mark.parametrize(("descricao", "fabrica"), INVALIDAS, ids=[d for d, _ in INVALIDAS])
def test_o_banco_recusa(descricao, fabrica):
    engine = criar_engine("sqlite://")
    recriar(engine)
    with pytest.raises(IntegrityError):
        _inserir(engine, fabrica())
