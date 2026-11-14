"""O próprio banco recusa dado fora das regras do mock (além das checagens da aplicação)."""

from datetime import date, datetime

import pytest
from mock import gerar, modelos  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import criar_engine
from mock.gerar import recriar
from mock.modelos import (
    BaseMock,
    Chamado,
    ContatoLojista,
    Fatura,
    Interacao,
    Liquidacao,
    Lojista,
    Venda,
)
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def engine():
    engine = criar_engine("sqlite://")
    recriar(engine)
    return engine


def _venda(**trocas) -> Venda:
    campos = {
        "codigo": "T9999999", "id_lojista": "M00001", "data_hora": datetime(2026, 10, 1, 10, 0),
        "modalidade": "debito", "parcelas": 1, "bandeira": "visa", "ultimos4": "1234",
        "valor_bruto_centavos": 1000, "valor_liquido_centavos": 980, "situacao": "aprovada",
    }
    return Venda(**{**campos, **trocas})


def _chamado(**trocas) -> Chamado:
    campos = {
        "codigo": "CH999999", "protocolo": "20261001-999999", "id_lojista": "M00001", "categoria": "Recebimento",
        "prioridade": "alta", "fila": "varejo", "id_responsavel": None, "situacao": "novo", "aberto_por": "lojista",
        "aberto_em": datetime(2026, 10, 1, 9, 0), "resumo": "teste",
    }
    return Chamado(**{**campos, **trocas})


def _fatura(**trocas) -> Fatura:
    campos = {
        "codigo": "I999999", "id_lojista": "M00001", "tipo": "aluguel", "mes_referencia": "2026-10",
        "vencimento": date(2026, 10, 10), "valor_centavos": 3990, "situacao": "vencida",
    }
    return Fatura(**{**campos, **trocas})


VALIDOS = [
    ("venda de débito", _venda()),
    ("venda Pix", _venda(modalidade="pix", bandeira=None, ultimos4=None)),
    ("venda parcelada", _venda(modalidade="parcelado", parcelas=12)),
    ("venda negada sem líquido", _venda(situacao="negada", valor_liquido_centavos=0)),
    ("chamado", _chamado()),
    ("fatura", _fatura()),
]

INVALIDOS = [
    ("modalidade fora da lista", _venda(modalidade="boleto")),
    ("Pix com bandeira", _venda(modalidade="pix", ultimos4=None)),
    ("cartão sem os 4 dígitos", _venda(ultimos4=None)),
    ("4 dígitos com 5 caracteres", _venda(ultimos4="12345")),
    ("parcelado em 1x", _venda(modalidade="parcelado", parcelas=1)),
    ("parcelado em 13x", _venda(modalidade="parcelado", parcelas=13)),
    ("débito em 2x", _venda(parcelas=2)),
    ("valor bruto zero", _venda(valor_bruto_centavos=0, valor_liquido_centavos=0)),
    ("líquido maior que o bruto", _venda(valor_liquido_centavos=1001)),
    ("líquido negativo", _venda(valor_liquido_centavos=-1)),
    ("venda negada com líquido", _venda(situacao="negada")),
    ("código de venda fora do formato", _venda(codigo="X0000001")),
    ("lojista que não existe", _venda(id_lojista="M99999")),
    ("fila que não é carteira", _chamado(fila="atendimento")),
    ("situação de chamado inventada", _chamado(situacao="aberto")),
    ("categoria inventada", _chamado(categoria="Outros")),
    ("prioridade sem acento", _chamado(prioridade="media")),
    ("protocolo fora do formato", _chamado(protocolo="2026-1001")),
    ("responsável que não existe", _chamado(id_responsavel="F9999")),
    ("fatura com valor zero", _fatura(valor_centavos=0)),
    ("mês de referência fora do formato", _fatura(mes_referencia="10/2026")),
    ("tipo de fatura inventado", _fatura(tipo="multa")),
    ("liquidação paga com motivo de falha",
     Liquidacao(id_lojista="M00001", data=date(2026, 10, 1), valor_total_centavos=100,
                situacao="paga", motivo_falha="conta_invalida")),
    ("liquidação falha sem motivo",
     Liquidacao(id_lojista="M00001", data=date(2026, 10, 1), valor_total_centavos=100, situacao="falhou")),
    ("contato com papel inventado",
     ContatoLojista(id_lojista="M00001", nome="x", cpf="000.000.000-00", papel="dono",
                    telefone="(21) 90000-0000", email="x@lojistas.example")),
    ("interação num chamado que não existe",
     Interacao(id_chamado="CH999998", autor="lojista", canal="chat",
               data_hora=datetime(2026, 10, 1, 9, 0), texto="oi")),
    ("interação por canal inventado",
     Interacao(id_chamado="CH000001", autor="lojista", canal="sms",
               data_hora=datetime(2026, 10, 1, 9, 0), texto="oi")),
    ("lojista com porte inventado",
     Lojista(codigo="M99998", nome_fantasia="x", segmento="x", porte="grande", cidade="x", uf="RJ",
             carteira="varejo", data_entrada=date(2026, 1, 1))),
    ("lojista com UF de 3 letras",
     Lojista(codigo="M99997", nome_fantasia="x", segmento="x", porte="ME", cidade="x", uf="RJX",
             carteira="varejo", data_entrada=date(2026, 1, 1))),
]


@pytest.mark.parametrize("rotulo,linha", VALIDOS, ids=[r for r, _ in VALIDOS])
def test_linha_valida_entra(engine, rotulo, linha):
    with Session(engine) as sessao:
        sessao.add(linha)
        sessao.flush()
        sessao.rollback()


@pytest.mark.parametrize("rotulo,linha", INVALIDOS, ids=[r for r, _ in INVALIDOS])
def test_linha_invalida_e_recusada_pelo_banco(engine, rotulo, linha):
    with Session(engine) as sessao:
        sessao.add(linha)
        with pytest.raises(IntegrityError):
            sessao.flush()
        sessao.rollback()


def test_o_mundo_gerado_respeita_todas_as_restricoes():
    # recriar insere tudo com as chaves estrangeiras ligadas; se algo violasse, levantaria aqui
    engine = criar_engine("sqlite://")
    recriar(engine)
    with engine.connect() as conexao:
        assert conexao.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conexao.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_categorias_e_prioridades_do_gerador_estao_no_esquema():
    for categoria, prioridade, *_ in gerar.CATEGORIAS_CHAMADO:
        assert categoria in modelos.CATEGORIAS_DE_CHAMADO
        assert prioridade in modelos.PRIORIDADES
    assert {c for c, *_ in gerar.CATEGORIAS_CHAMADO} == set(modelos.CATEGORIAS_DE_CHAMADO)
    for papeis in gerar.PAPEIS_POR_PORTE.values():
        assert set(papeis) <= set(modelos.PAPEIS_CONTATO)


def test_nomes_das_restricoes_seguem_a_convencao(engine):
    inspetor = inspect(engine)
    for tabela in BaseMock.metadata.sorted_tables:
        for check in inspetor.get_check_constraints(tabela.name):
            assert check["name"].startswith(f"ck_{tabela.name}_"), check["name"]
        for indice in inspetor.get_indexes(tabela.name):
            assert indice["name"].startswith(f"ix_{tabela.name}_"), indice["name"]


def test_toda_coluna_restrita_tem_comentario():
    restritas = {
        ("contatos_lojista", "nome"), ("contatos_lojista", "cpf"), ("contatos_lojista", "telefone"),
        ("contatos_lojista", "email"), ("contas_recebimento", "agencia"), ("contas_recebimento", "conta"),
        ("vendas", "ultimos4"), ("interacoes", "texto"), ("chamados", "resumo"),
    }
    tabelas = BaseMock.metadata.tables
    for tabela, coluna in restritas:
        assert tabelas[tabela].c[coluna].comment.startswith("RESTRITO"), (tabela, coluna)
    for tabela in tabelas.values():
        assert tabela.comment, tabela.name
