"""Ajustes da etapa F1: LIMITE_MAXIMO no mock, chamado do lojista por consulta, `preparar` e janela."""

import ast
from datetime import datetime
from pathlib import Path

import pytest
from ferramentas import dados_sinteticos, governanca, lojista
from ferramentas.base import ErroFerramenta
from mock.consultas import LIMITE_MAXIMO as LIMITE_DAS_CONSULTAS
from mock.modelos import Chamado
from mock.regras import LIMITE_MAXIMO
from sqlalchemy.orm import Session

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    executar,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def engine():
    engine = mundo_do_mock()
    limpar_estado()
    yield engine
    limpar_estado()


def usuario(engine, cargo):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])


# --- I3 ------------------------------------------------------------------------------------------


def test_limite_maximo_mora_em_regras_e_a_governanca_nao_importa_consultas():
    assert LIMITE_MAXIMO == LIMITE_DAS_CONSULTAS == governanca.LIMITE_LINHAS == 50
    arvore = ast.parse((RAIZ / "ferramentas" / "governanca.py").read_text(encoding="utf-8"))
    importados = {
        alias.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
        for alias in no.names
    }
    assert "consultas" not in importados


# --- I8 ------------------------------------------------------------------------------------------


def _abrir_chamados(engine, quantidade, lojista_codigo="M00001"):
    with Session(engine) as sessao:
        for i in range(quantidade):
            sessao.add(
                Chamado(
                    codigo=f"CH9{i:05d}", protocolo=f"20260101-9{i:05d}", id_lojista=lojista_codigo,
                    categoria="Recebimento", prioridade="baixa", fila="atendimento",
                    id_responsavel=None, situacao="aberto", aberto_por="lojista",
                    aberto_em=datetime(2026, 1, 1, 9, 0),  # noqa: DTZ001 (o mock usa datas sem fuso)
                    resumo="teste",
                )
            )
        sessao.commit()


def test_chamado_antigo_de_lojista_com_mais_de_50_chamados_ainda_e_encontrado(engine):
    _abrir_chamados(engine, 60)
    mais_antigo = "CH900059"
    primeiros, total = dados_sinteticos.buscar_chamados("M00001", None)
    assert total > 50 and mais_antigo not in {c["codigo"] for c in primeiros}  # fora dos 50
    assert dados_sinteticos.chamado_e_do_lojista("M00001", mais_antigo) is True


def test_chamado_de_outro_lojista_e_inexistente_dao_false(engine):
    assert dados_sinteticos.chamado_e_do_lojista("M00009", "CH000013") is False
    assert dados_sinteticos.chamado_e_do_lojista("M00009", "CH999999") is False
    assert dados_sinteticos.chamado_e_do_lojista("M00009", "CH000062") is True


def test_historico_de_chamado_sem_mensagens_do_lojista_certo_nao_vira_erro(engine):
    _abrir_chamados(engine, 60)
    ana = usuario(engine, "atendente_n1")
    resposta = executar(
        "consultar_historico_contato", {"id_cliente": "M00001", "id_chamado": "CH900059"}, ana,
        ("consultar_historico_contato",),
    )
    assert resposta["status"] == "ok" and resposta["dados"]["conteudo_de_terceiros"]["interacoes"] == []


# --- I7 ------------------------------------------------------------------------------------------


def test_preparar_devolve_o_pedido_validado_e_com_a_janela_aplicada(engine):
    ana = usuario(engine, "atendente_n1")
    pedido = lojista.preparar(ana, {"id_cliente": "M00001"}, com_periodo=True)
    assert pedido.codigo == "M00001" and pedido.limite == lojista.LIMITE_PADRAO
    assert pedido.data_inicio == governanca.inicio_da_janela(ana) and pedido.data_fim is None


def test_preparar_sem_periodo_ignora_datas_e_nao_aplica_janela(engine):
    ana = usuario(engine, "atendente_n1")
    pedido = lojista.preparar(ana, {"id_cliente": "M00001", "limite": 5})
    assert (pedido.data_inicio, pedido.data_fim, pedido.limite) == (None, None, 5)


def test_preparar_confere_parametro_antes_do_acesso_e_acesso_antes_da_janela(engine):
    ana = usuario(engine, "atendente_n1")
    # limite inválido vence mesmo com lojista fora da carteira
    with pytest.raises(ErroFerramenta) as erro:
        lojista.preparar(ana, {"id_cliente": "M00005", "limite": 0})
    assert erro.value.tipo_erro == "parametro_invalido"
    # lojista fora da carteira vence a janela
    with pytest.raises(ErroFerramenta) as erro:
        data = governanca.inicio_da_janela(ana).replace(year=2025)
        lojista.preparar(ana, {"id_cliente": "M00005", "data_inicio": data}, com_periodo=True)
    assert erro.value.tipo_erro == "permissao_negada" and "carteira" in erro.value.mensagem
    # dentro da carteira, fora da janela
    with pytest.raises(ErroFerramenta) as erro:
        data = governanca.inicio_da_janela(ana).replace(year=2025)
        lojista.preparar(ana, {"id_cliente": "M00001", "data_inicio": data}, com_periodo=True)
    assert "90 dias" in erro.value.mensagem


def test_preparar_formato_de_codigo_invalido(engine):
    with pytest.raises(ErroFerramenta) as erro:
        lojista.preparar(usuario(engine, "atendente_n1"), {"id_cliente": "M1"})
    assert erro.value.tipo_erro == "parametro_invalido"


# --- janela_dias ---------------------------------------------------------------------------------


def test_janela_dias_none_e_sem_janela_e_usuario_invalido_levanta(engine):
    assert governanca.janela_dias(usuario(engine, "atendente_n1")) == 90
    assert governanca.janela_dias(usuario(engine, "coordenador_financeiro")) is None
    for invalido in (None, governanca.Usuario("x", "N1", "atendimento", (), "cargo_que_nao_existe")):
        with pytest.raises(ValueError, match="inválido"):
            governanca.janela_dias(invalido)
        with pytest.raises(ValueError, match="inválido"):
            governanca.inicio_da_janela(invalido)
