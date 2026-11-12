"""MED-1, MED-2 e MED-3 da auditoria B: escrita registra antes de agir, bloqueio deixa rastro, `.rodar` fica dentro."""

import ast
import json
import sys
import time
from pathlib import Path

import pytest
from ferramentas import catalogo, governanca
from ferramentas.base import Ferramenta
from ferramentas.plataforma.solicitar_ferramenta_ausente import func as pedidos_func

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    NEGADO_PELO_CATALOGO,
    executar,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

RAIZ = Path(__file__).resolve().parents[2]
PEDIDO = {"nome_sugerido": "exportar_tudo", "descricao": "preciso do cpf 52998224700 do socio"}


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["atendente_n1"])


def destino_que_falha(registro):
    raise OSError("destino fora do ar")


# --- MED-1 ---------------------------------------------------------------------------------------


def test_escrita_com_destino_de_registro_falho_nao_grava_nada(ana):
    governanca.adicionar_destino(destino_que_falha)
    resposta = executar("solicitar_ferramenta_ausente", PEDIDO, ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert resposta["mensagem"] == "Registro indisponível."
    assert pedidos_func.PEDIDOS == []


def test_escrita_registra_inicio_e_fim_e_o_inicio_vem_antes_da_acao(ana):
    visto_no_inicio = []

    def espiao(registro):
        visto_no_inicio.append((registro["status"], len(pedidos_func.PEDIDOS)))

    governanca.adicionar_destino(espiao)
    assert executar("solicitar_ferramenta_ausente", PEDIDO, ana)["status"] == "ok"
    assert visto_no_inicio == [("iniciada", 0), ("ok", 1)]


def test_escrita_com_argumento_invalido_nao_deixa_registro_de_inicio(ana):
    executar("solicitar_ferramenta_ausente", {"nome_sugerido": "x"}, ana)
    assert [r["status"] for r in governanca.REGISTROS] == ["erro"]


def test_descricao_do_pedido_e_mascarada_antes_de_ser_guardada(ana):
    assert executar("solicitar_ferramenta_ausente", PEDIDO, ana)["status"] == "ok"
    guardado = json.dumps(pedidos_func.PEDIDOS, ensure_ascii=False)
    assert "52998224700" not in guardado
    assert pedidos_func.PEDIDOS[-1]["descricao"] == "preciso do cpf ***.982.247-** do socio"


@pytest.mark.parametrize(
    "nome",
    ["cpf_52998224700", "c4111111111111111", "cartao_4111111111111111", "x123456", "cpf_529_982_247_00", "CPF"],
)
def test_nome_sugerido_com_numero_longo_ou_fora_do_padrao_e_recusado_sem_gravar(ana, nome):
    """MED-2 da auditoria C: o nome vai para a fila do Jira; nada de CPF ou cartão nele."""
    resposta = executar("solicitar_ferramenta_ausente", {**PEDIDO, "nome_sugerido": nome}, ana)
    assert resposta["tipo_erro"] == "parametro_invalido"
    assert pedidos_func.PEDIDOS == []
    assert nome not in json.dumps(resposta)


def test_nome_sugerido_com_digitos_curtos_continua_valido(ana):
    resposta = executar("solicitar_ferramenta_ausente", {**PEDIDO, "nome_sugerido": "listar_v2_5"}, ana)
    assert resposta["status"] == "ok"
    assert pedidos_func.PEDIDOS[-1]["nome_sugerido"] == "listar_v2_5"


class ListaQueCedeAVez(list):
    """Lista que passa a vez para outra thread antes de `append`: abre a janela da corrida de propósito."""

    def append(self, item):
        time.sleep(0.0005)
        super().append(item)


def test_pedidos_de_16_threads_nao_repetem_id_nem_passam_do_limite(ana, monkeypatch):
    """BAIXO-6 da auditoria C: tamanho, id e inclusão na fila andam juntos sob a trava."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(pedidos_func, "PEDIDOS", ListaQueCedeAVez())
    intervalo_antigo = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # troca de thread o tempo todo: sem a trava, o id repetiria

    def pedir(_):
        return pedidos_func.FERRAMENTA.rodar(
            {"nome_sugerido": "listar_algo", "descricao": "x"}, ana
        )["id_pedido"]

    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            ids = list(pool.map(pedir, range(800)))
    finally:
        sys.setswitchinterval(intervalo_antigo)
    assert len(set(ids)) == 800
    assert [p["id_pedido"] for p in pedidos_func.PEDIDOS] == sorted(ids)


def test_leitura_continua_com_um_registro_so(ana):
    executar("consultar_cliente", {"id_cliente": "M00001"}, ana, ("consultar_cliente",))
    assert [r["status"] for r in governanca.REGISTROS] == ["ok"]


# --- MED-2 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "agente", "camada"),
    [
        ("consultar_cliente", (), "agente"),
        ("enviar_email", ("consultar_cliente",), "agente"),
        ("enviar_email", ("enviar_email",), "usuario"),
        ("ferramenta_que_nao_existe", ("consultar_cliente",), "desconhecida"),
    ],
)
def test_tentativa_bloqueada_deixa_registro_com_a_camada_e_a_mesma_resposta(
    ana, nome, agente, camada
):
    resposta = executar(nome, {"id_cliente": "M00002"}, ana, agente)
    assert resposta == NEGADO_PELO_CATALOGO
    (registro,) = governanca.REGISTROS
    assert registro["camada_bloqueio"] == camada
    assert registro["tipo_erro"] == "ferramenta_inexistente"
    assert "M00002" not in json.dumps(governanca.REGISTROS)


def test_ferramenta_de_outra_area_barrada_pelo_cargo_registra_a_camada_usuario(engine):
    auditor = usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["auditor_compliance"])
    resposta = executar("consultar_cliente", {"id_cliente": "M00001"}, auditor)
    assert resposta == NEGADO_PELO_CATALOGO
    assert governanca.REGISTROS[-1]["camada_bloqueio"] == "usuario"


def test_registrar_bloqueio_publico_serve_ao_agente_que_barra_antes_do_catalogo(ana):
    contexto = {"execucao_id": "exe-1", "passo": 3, "agente_id": "agente_geral"}
    resposta = catalogo.registrar_bloqueio("enviar_email", ana, contexto, "agente")
    assert resposta == NEGADO_PELO_CATALOGO
    (registro,) = governanca.REGISTROS
    assert registro["camada_bloqueio"] == "agente" and registro["passo"] == 3


def test_nome_inventado_nao_vira_conteudo_do_registro(ana):
    executar("cpf_52998224700", {}, ana, ("cpf_52998224700",))
    assert "52998224700" not in json.dumps(governanca.REGISTROS)
    assert governanca.REGISTROS[-1]["ferramenta"] == "inexistente"


def test_destino_falho_numa_recusa_nao_vira_erro_diferente(ana):
    governanca.adicionar_destino(destino_que_falha)
    assert executar("enviar_email", {}, ana, ()) == NEGADO_PELO_CATALOGO


# --- MED-3 ---------------------------------------------------------------------------------------

# Só o código de produção das outras pastas. Teste e ferramenta de teste podem chamar `.rodar`.
PASTAS_DE_PRODUCAO = ("agentes", "seguranca", "mock", "backend/app")


def _arquivos_de_producao_fora_de_ferramentas():
    for pasta in PASTAS_DE_PRODUCAO:
        yield from (RAIZ / pasta).rglob("*.py")


def _importa_func(no):
    if isinstance(no, ast.ImportFrom):
        return ".func" in (no.module or "")
    return isinstance(no, ast.Import) and any(a.name.endswith(".func") for a in no.names)


def _e_texto_de_func(no):
    texto = no.value if isinstance(no, ast.Constant) else None
    return isinstance(texto, str) and texto.startswith("ferramentas.") and texto.endswith(".func")


def _achados_de_acesso_direto(codigo, nome):
    """Linhas de `codigo` (módulo `nome`) que pegam `.rodar`, uma func.py ou `catalogo.carregar`."""
    for no in ast.walk(ast.parse(codigo)):
        achado = None
        if isinstance(no, ast.Attribute) and no.attr == "rodar":
            achado = "usa .rodar"
        elif isinstance(no, ast.Attribute) and no.attr == "carregar":
            achado = "usa catalogo.carregar"
        elif _importa_func(no):
            achado = "importa uma func.py"
        elif _e_texto_de_func(no):
            achado = "importa uma func.py por texto"
        if achado:
            yield f"{nome}:{no.lineno} {achado}"


def test_nenhum_modulo_fora_de_ferramentas_chama_rodar_ou_importa_func():
    achados = []
    for arquivo in _arquivos_de_producao_fora_de_ferramentas():
        relativo = arquivo.relative_to(RAIZ).as_posix()
        codigo = arquivo.read_text(encoding="utf-8")
        achados += _achados_de_acesso_direto(codigo, relativo)
    assert achados == []


def test_o_varredor_enxerga_o_que_deve():
    codigo = (
        "from ferramentas.financeiro.x.func import FERRAMENTA\n"
        "import ferramentas.a.b.func\n"
        "catalogo.carregar()['x'].rodar({}, None)\n"
        "importlib.import_module('ferramentas.a.b.func')\n"
    )
    achados = [a.split(" ", 1)[1] for a in _achados_de_acesso_direto(codigo, "m.py")]
    assert sorted(achados) == sorted(
        ["importa uma func.py", "importa uma func.py", "usa catalogo.carregar", "usa .rodar",
         "importa uma func.py por texto"]
    )


def test_catalogo_nomes_lista_so_nomes_e_executar_e_o_unico_caminho_para_rodar():
    assert all(isinstance(nome, str) for nome in catalogo.nomes())
    assert set(catalogo.nomes()) == set(catalogo.carregar())
    assert hasattr(Ferramenta, "executar")
