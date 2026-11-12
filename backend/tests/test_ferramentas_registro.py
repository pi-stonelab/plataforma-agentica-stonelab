"""Registro sem conteúdo que falha fechado (O9) e banco ou sistema do mock fora do ar."""

import json

import pytest
from ferramentas import catalogo, dados_sinteticos, governanca
from mock.banco import criar_engine
from mock.falhas import SISTEMAS, desligar, ligar

from .apoio_ferramentas import (
    executar,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

# Valores que não podem aparecer em nenhum registro: o código do lojista, o nome da loja, o CPF.
CANARIOS = ("M00001", "Padaria", "Pão da Vila", "123.456.789", "456.789")


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    dados_sinteticos.configurar(engine)
    limpar_estado()
    yield
    limpar_estado()
    dados_sinteticos.configurar(engine)


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, "F0001")


# --- registro sem conteúdo --------------------------------------------------------------------


def test_registro_so_tem_ids_ferramenta_e_status_sem_conteudo(ana):
    contexto = {"execucao_id": "EXE-1", "passo": 2, "agente_id": "AGE-1"}
    for nome, argumentos in (
        ("consultar_cliente", {"id_cliente": "M00001"}),
        ("consultar_transacoes_cliente", {"id_cliente": "M00001", "limite": 3}),
        ("consultar_cliente", {"id_cliente": "M00005"}),  # negada pelo escopo
        ("consultar_cliente", {"id_cliente": "M99999"}),
    ):
        catalogo.executar(nome, argumentos, ana, ("consultar_cliente", "consultar_transacoes_cliente"), contexto)
    assert len(governanca.REGISTROS) == 4
    for registro in governanca.REGISTROS:
        assert set(registro) == set(governanca.CAMPOS_REGISTRO)
        assert registro["id_usuario"] == "F0001"
    texto = json.dumps(governanca.REGISTROS, ensure_ascii=False)
    for canario in (*CANARIOS, "M00005", "M99999", "Clínica"):
        assert canario not in texto
    assert [r["tipo_erro"] for r in governanca.REGISTROS] == [None, None, "permissao_negada", "permissao_negada"]


# --- registro que falha fecha a resposta (O9) --------------------------------------------------


def destino_que_falha(registro):
    raise RuntimeError("banco de auditoria fora do ar com o dado M00001")


def test_se_o_registro_nao_grava_a_resposta_sai_sem_dado(ana, caplog):
    governanca.adicionar_destino(destino_que_falha)
    with caplog.at_level("ERROR", logger=governanca.logger.name):
        resposta = executar("consultar_cliente", {"id_cliente": "M00001"}, ana)
    assert resposta == {
        "status": "erro",
        "dados": None,
        "mensagem": "Registro indisponível.",
        "tipo_erro": "integracao_indisponivel",
    }
    # o log diz qual ferramenta falhou, nunca o dado nem o texto do erro do destino
    assert "consultar_cliente" in caplog.text
    assert "M00001" not in caplog.text and "fora do ar" not in caplog.text
    # o buffer em memória não deixa um "ok" para quem nunca recebeu a resposta
    assert governanca.REGISTROS[-1]["status"] == "erro"
    assert governanca.REGISTROS[-1]["tipo_erro"] == "integracao_indisponivel"


def test_os_outros_destinos_ainda_recebem_o_registro_quando_um_falha(ana):
    recebidos = []
    governanca.adicionar_destino(destino_que_falha)
    governanca.adicionar_destino(recebidos.append)
    executar("calcular_multa_atraso", {"valor_fatura": 100, "dias_atraso": 1}, ana)
    assert len(recebidos) == 1 and set(recebidos[0]) == set(governanca.CAMPOS_REGISTRO)


def test_destino_saudavel_nao_atrapalha(ana):
    recebidos = []
    governanca.adicionar_destino(recebidos.append)
    resposta = executar("consultar_cliente", {"id_cliente": "M00001"}, ana)
    assert resposta["status"] == "ok" and len(recebidos) == 1


def test_negacao_pelo_catalogo_continua_negacao_mesmo_se_o_registro_falha(ana):
    governanca.adicionar_destino(destino_que_falha)
    resposta = catalogo.executar("nao_existe", {}, ana, ("consultar_cliente",))
    assert resposta["tipo_erro"] == "ferramenta_inexistente"


# --- banco ou sistema do mock fora do ar -------------------------------------------------------


@pytest.mark.parametrize(
    ("sistema", "ferramenta", "argumentos"),
    [
        ("cadastro", "consultar_cliente", {"id_cliente": "M00001"}),
        ("cadastro", "consultar_transacoes_cliente", {"id_cliente": "M00001"}),  # escopo precisa do cadastro
        ("core", "consultar_transacoes_cliente", {"id_cliente": "M00001"}),
    ],
)
def test_sistema_simulado_fora_do_ar_vira_integracao_indisponivel(ana, sistema, ferramenta, argumentos):
    ligar(sistema)
    resposta = executar(ferramenta, argumentos, ana)
    assert resposta["status"] == "erro" and resposta["dados"] is None
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert resposta["mensagem"] == "Integração fora do ar."
    assert sistema not in str(resposta)
    desligar(sistema)
    assert executar(ferramenta, argumentos, ana)["status"] == "ok"
    assert governanca.REGISTROS[0]["tipo_erro"] == "integracao_indisponivel"


def test_falha_do_core_nao_derruba_quem_so_usa_o_cadastro(ana):
    ligar("core")
    assert executar("consultar_cliente", {"id_cliente": "M00001"}, ana)["status"] == "ok"


def test_ferramentas_sem_banco_continuam_funcionando_com_o_mock_fora_do_ar(ana):
    for sistema in SISTEMAS:
        ligar(sistema)
    assert executar("calcular_multa_atraso", {"valor_fatura": 100, "dias_atraso": 1}, ana)["status"] == "ok"
    assert executar("consultar_endereco_cep", {"cep": "01310100"}, ana)["status"] == "ok"


def test_banco_sem_tabelas_ou_inacessivel_vira_integracao_indisponivel(ana, tmp_path):
    dados_sinteticos.configurar(criar_engine("sqlite://"))  # existe, mas sem as tabelas do mock
    sem_tabelas = executar("consultar_cliente", {"id_cliente": "M00001"}, ana)
    assert sem_tabelas["tipo_erro"] == "integracao_indisponivel"
    assert "lojistas" not in str(sem_tabelas) and "sqlite" not in str(sem_tabelas).lower()
    inacessivel = tmp_path / "pasta_que_nao_existe" / "mock.sqlite"
    dados_sinteticos.configurar(f"sqlite:///{inacessivel}")
    sem_arquivo = executar("consultar_cliente", {"id_cliente": "M00001"}, ana)
    assert sem_arquivo["tipo_erro"] == "integracao_indisponivel"
    assert str(tmp_path) not in str(sem_arquivo)


def test_erro_do_banco_nao_vaza_no_registro(ana):
    dados_sinteticos.configurar(criar_engine("sqlite://"))
    executar("consultar_cliente", {"id_cliente": "M00001"}, ana)
    texto = json.dumps(governanca.REGISTROS)
    assert "lojistas" not in texto and "SELECT" not in texto and "M00001" not in texto
