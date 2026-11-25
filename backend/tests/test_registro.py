import json

import pytest
from fastapi.testclient import TestClient
from ferramentas import governanca
from sqlalchemy import select

from app import models, orquestrador
from app.config import configuracao
from app.db import Base, SessaoLocal, engine
from app.main import app
from app.registro import gravar_execucao
from app.rotas.conversas import obter_llm
from app.seed import semear, semear_agentes

from .apoio_ferramentas import limpar_estado, mundo_do_mock
from .test_conversas import SENHA, ModeloRoteirizado, abrir, entrar, roteiro_consultar_cliente


@pytest.fixture
def modelo():
    return ModeloRoteirizado()


@pytest.fixture
def cliente(modelo):
    limpar_estado()
    mundo_do_mock()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessaoLocal() as sessao:
        semear(sessao, SENHA)
        semear_agentes(sessao)
    app.dependency_overrides[obter_llm] = lambda: modelo
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()
    limpar_estado()


def linhas(tabela):
    with SessaoLocal() as sessao:
        return list(sessao.scalars(select(tabela).order_by(tabela.id)))


def derrubar(tabela):
    tabela.__table__.drop(engine)


def enviar(cliente, cabecalho, conversa_id, texto="Situação do M00001?"):
    return cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": texto}, headers=cabecalho
    )


def turno_com_ferramenta(cliente, modelo, id_usuario="F0001"):
    cabecalho = entrar(cliente, id_usuario)
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_consultar_cliente("M00001"))
    resposta = enviar(cliente, cabecalho, conversa_id)
    assert resposta.status_code == 200, resposta.text
    return cabecalho, conversa_id, resposta.json()


def test_o_destino_de_execucoes_e_ligado_uma_vez_so(cliente):
    with TestClient(app):
        pass
    assert governanca.DESTINOS.count(gravar_execucao) == 1


def test_auditoria_e_execucao_se_ligam_pelo_execucao_id(cliente, modelo):
    turno_com_ferramenta(cliente, modelo)

    execucoes = linhas(models.ExecucaoFerramenta)
    assert len(execucoes) == 1
    execucao = execucoes[0]
    assert execucao.ferramenta == "consultar_cliente"
    assert execucao.id_usuario == "F0001"
    assert execucao.agente_id == "ag-atendimento"
    assert execucao.status == "ok"
    assert execucao.passo == 4
    assert isinstance(execucao.integracoes, list)
    assert isinstance(execucao.categorias_dados, list)

    ligados = [e for e in linhas(models.Auditoria) if e.execucao_id == execucao.execucao_id]
    assert ligados
    assert all(e.acao == "EXECUTAR" and e.permitido for e in ligados)
    assert {e.alvo for e in ligados} == {"ag-atendimento"}


def test_registros_nao_guardam_conteudo_nem_nome(cliente, modelo):
    turno_com_ferramenta(cliente, modelo)
    with SessaoLocal() as sessao:
        nome = sessao.get(models.Usuario, "F0001").nome

    gravado = []
    for tabela in (models.Auditoria, models.ExecucaoFerramenta, models.UsoModelo):
        for linha in linhas(tabela):
            gravado.append(
                {c.name: str(getattr(linha, c.name)) for c in tabela.__table__.columns}
            )
    texto = json.dumps(gravado, ensure_ascii=False)
    assert "M00001" not in texto
    assert nome not in texto


def test_tabela_de_execucoes_tem_todos_os_campos_do_registro():
    colunas = {c.name for c in models.ExecucaoFerramenta.__table__.columns}
    assert colunas == {"id", *governanca.CAMPOS_REGISTRO}


def test_acesso_negado_tambem_e_gravado(cliente):
    resposta = cliente.post(
        "/conversas", json={"agente_id": "ag-atendimento"}, headers=entrar(cliente, "F0013")
    )
    assert resposta.status_code == 403
    evento = linhas(models.Auditoria)[-1]
    assert (evento.id_usuario, evento.acao, evento.alvo, evento.permitido) == (
        "F0013",
        "EXECUTAR",
        "ag-atendimento",
        False,
    )


def test_agente_desativado_grava_a_negacao(cliente):
    resposta = cliente.post(
        "/conversas", json={"agente_id": "ag-conciliacao"}, headers=entrar(cliente, "F0011")
    )
    assert resposta.json() == {"detail": "Este agente foi desativado e só pode ser consultado."}
    evento = linhas(models.Auditoria)[-1]
    assert (evento.alvo, evento.permitido) == ("ag-conciliacao", False)


def test_sem_auditoria_a_acao_e_negada_e_o_modelo_nao_e_chamado(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_consultar_cliente("M00001"))
    derrubar(models.Auditoria)

    resposta = enviar(cliente, cabecalho, conversa_id)

    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "Acesso negado."}
    assert modelo.chamadas == []
    assert linhas(models.Mensagem) == []


def test_sem_registro_de_execucao_a_ferramenta_nao_entrega_dado(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_consultar_cliente("M00001", "FINAL: Não consegui consultar."))
    derrubar(models.ExecucaoFerramenta)

    resposta = enviar(cliente, cabecalho, conversa_id)

    assert resposta.status_code == 200, resposta.text
    assert any("integracao_indisponivel" in passo for passo in resposta.json()["trajetoria"])
    esperado = (
        '{"status": "erro", "dados": null, "mensagem": "Registro indisponível.", '
        '"tipo_erro": "integracao_indisponivel"}'
    )
    assert esperado in modelo.chamadas[-1]["prompt"]


def test_uso_do_modelo_e_gravado_por_chamada(cliente, modelo):
    _, conversa_id, corpo = turno_com_ferramenta(cliente, modelo)

    usos = linhas(models.UsoModelo)
    assert len(usos) == corpo["uso"]["chamadas_modelo"] == 5
    assert {u.usuario_id for u in usos} == {"F0001"}
    assert {u.conversa_id for u in usos} == {conversa_id}
    assert {u.execucao_id for u in usos} == {linhas(models.ExecucaoFerramenta)[0].execucao_id}
    assert sum(u.tokens_entrada for u in usos) == 500
    assert sum(u.tokens_saida for u in usos) == 100
    assert sum(u.latencia_ms for u in usos) == 250
    assert sum(u.custo_simulado for u in usos) == pytest.approx(corpo["uso"]["custo"])


def test_uso_fica_gravado_mesmo_quando_o_turno_vira_504(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro("PENSAMENTO: ver áreas.\nLER: ")

    assert enviar(cliente, cabecalho, conversa_id).status_code == 504
    assert len(linhas(models.UsoModelo)) == 1
    assert linhas(models.Mensagem) == []


def test_sem_registro_de_uso_responde_503_e_nao_grava_mensagem(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro("PENSAMENTO: simples.\nFINAL: Olá!")
    derrubar(models.UsoModelo)

    resposta = enviar(cliente, cabecalho, conversa_id)

    assert resposta.status_code == 503
    assert linhas(models.Mensagem) == []


def test_auditor_le_a_trilha_com_filtros(cliente, modelo):
    turno_com_ferramenta(cliente, modelo)
    execucao_id = linhas(models.ExecucaoFerramenta)[0].execucao_id
    auditor = entrar(cliente, "F0012")

    todos = cliente.get("/auditoria", headers=auditor)
    assert todos.status_code == 200, todos.text
    eventos = todos.json()
    assert eventos[0]["acao"] == "LER_AUDITORIA"
    assert eventos[0]["id_usuario"] == "F0012"
    assert [e["id"] for e in eventos] == sorted((e["id"] for e in eventos), reverse=True)
    assert set(eventos[0]) == {
        "id",
        "quando",
        "id_usuario",
        "acao",
        "alvo",
        "permitido",
        "execucao_id",
    }

    do_turno = cliente.get(f"/auditoria?execucao_id={execucao_id}", headers=auditor).json()
    assert do_turno
    assert {e["execucao_id"] for e in do_turno} == {execucao_id}

    primeira = cliente.get("/auditoria?limite=1", headers=auditor).json()
    seguinte = cliente.get(
        f"/auditoria?limite=1&antes_de={primeira[0]['id']}", headers=auditor
    ).json()
    assert len(primeira) == len(seguinte) == 1
    assert seguinte[0]["id"] < primeira[0]["id"]

    da_pessoa = cliente.get("/auditoria?id_usuario=F0001&permitido=true", headers=auditor).json()
    assert da_pessoa
    assert all(e["id_usuario"] == "F0001" and e["permitido"] for e in da_pessoa)

    assert cliente.get("/auditoria?limite=201", headers=auditor).status_code == 422


@pytest.mark.parametrize("id_usuario", ["F0001", "F0006", "F0013", "G0001"])
def test_so_o_auditor_le_a_auditoria(cliente, id_usuario):
    resposta = cliente.get("/auditoria", headers=entrar(cliente, id_usuario))
    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "Acesso negado."}
    evento = linhas(models.Auditoria)[-1]
    assert (evento.id_usuario, evento.acao, evento.permitido) == (
        id_usuario,
        "LER_AUDITORIA",
        False,
    )


def test_auditoria_sem_token_responde_401(cliente):
    assert cliente.get("/auditoria").status_code == 401


def test_leitura_sem_poder_gravar_o_proprio_acesso_e_negada(cliente):
    auditor = entrar(cliente, "F0012")
    derrubar(models.Auditoria)
    assert cliente.get("/auditoria", headers=auditor).status_code == 403


@pytest.mark.parametrize("segundos", [None, 600.0])
def test_tempo_do_turno_vem_da_configuracao(cliente, modelo, monkeypatch, segundos):
    contextos = []
    original = orquestrador.rodar_turno

    def espiar(*args, **kwargs):
        contextos.append(kwargs["contexto"])
        return original(*args, **kwargs)

    monkeypatch.setattr(orquestrador, "rodar_turno", espiar)
    monkeypatch.setattr(configuracao, "turno_segundos", segundos)
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro("PENSAMENTO: simples.\nFINAL: Olá!")

    enviar(cliente, cabecalho, conversa_id, "Oi")

    assert contextos[0]["segundos_por_turno"] == segundos
