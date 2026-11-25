"""Login, token e /me: a porta 1 (quem é você?) com o diretório do mock como fonte.

O banco da plataforma é SQLite em memória (conftest) e o diretório é o mock em memória (apoio_agente).
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from ferramentas import dados_sinteticos

from app import models
from app.auth import ALGORITMO, MENSAGEM_LOGIN, criar_token, segredo_do_token
from app.db import Base, SessaoLocal, engine
from app.main import app
from app.permissoes import PERFIL_DO_CARGO
from app.seed import FUNCIONARIOS_DA_DEMO, contas_da_demo, semear

from . import apoio_agente as apoio

SENHA = "senha-de-teste"


@pytest.fixture
def cliente():
    apoio.mundo()  # liga o diretório do mock (em memória) às ferramentas
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessaoLocal() as sessao:
        semear(sessao, SENHA)
    with TestClient(app) as cliente:
        yield cliente


def email_de(id_usuario):
    with SessaoLocal() as sessao:
        return sessao.get(models.Usuario, id_usuario).email


def entrar(cliente, id_usuario, senha=SENHA):
    return cliente.post("/auth/login", json={"email": email_de(id_usuario), "senha": senha})


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


def perfil_de(cliente, id_usuario):
    token = entrar(cliente, id_usuario).json()["token"]
    resposta = cliente.get("/me", headers=cabecalho(token))
    assert resposta.status_code == 200
    return resposta.json()


# ---------------------------------------------------------------- login
def test_login_devolve_token_bearer(cliente):
    resposta = entrar(cliente, "F0001")
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "bearer"


def test_email_ignora_maiusculas_e_espacos(cliente):
    email = "  " + email_de("F0001").upper() + " "
    resposta = cliente.post("/auth/login", json={"email": email, "senha": SENHA})
    assert resposta.status_code == 200


def test_senha_errada_e_email_inexistente_tem_a_mesma_resposta(cliente):
    errada = entrar(cliente, "F0001", senha="outra")
    inexistente = cliente.post("/auth/login", json={"email": "ninguem@stonesim.example", "senha": SENHA})
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"detail": MENSAGEM_LOGIN}


def test_senha_maior_que_o_limite_do_bcrypt_e_recusada_sem_erro(cliente):
    assert entrar(cliente, "F0001", senha="x" * 100).status_code == 401


@pytest.mark.parametrize("id_usuario", ["F0014", "F0015"])  # desligado e afastada
def test_funcionario_inativo_nao_entra_mesmo_com_a_senha_certa(cliente, id_usuario):
    resposta = entrar(cliente, id_usuario)
    assert resposta.status_code == 401
    assert resposta.json() == {"detail": MENSAGEM_LOGIN}


def test_token_leva_so_sub_e_validade(cliente):
    token = entrar(cliente, "F0006").json()["token"]
    carga = jwt.decode(token, segredo_do_token(), algorithms=[ALGORITMO])
    assert set(carga) == {"sub", "iat", "exp"}
    assert carga["sub"] == "F0006"


# ---------------------------------------------------------------- /me
def test_me_do_atendente_n1(cliente):
    assert perfil_de(cliente, "F0001") == {
        "id": "F0001",
        "nome": "Ana Lima",
        "email": email_de("F0001"),
        "perfil": "Colaborador",
        "area": "AtendimentoCliente",
        "areas_extras": [],
        "carteira": ["varejo"],
        "uso_mes": None,
    }


def test_me_do_supervisor_e_do_coordenador(cliente):
    assert perfil_de(cliente, "F0006")["perfil"] == "Supervisor"
    assert perfil_de(cliente, "F0006")["area"] == "AtendimentoCliente"
    assert perfil_de(cliente, "F0011")["perfil"] == "Supervisor"
    assert perfil_de(cliente, "F0011")["area"] == "Financeiro"


def test_me_de_quem_nao_usa_ferramentas(cliente):
    admin = perfil_de(cliente, "F0013")
    assert (admin["perfil"], admin["area"], admin["carteira"]) == ("AdminGlobal", None, [])
    gestor = perfil_de(cliente, "G0001")
    assert (gestor["perfil"], gestor["carteira"]) == ("GestorDeAcessos", [])


def test_me_le_o_perfil_do_banco_a_cada_pedido(cliente):
    """Perfil trocado no banco vale no pedido seguinte, sem novo login."""
    token = entrar(cliente, "F0001").json()["token"]
    with SessaoLocal() as sessao:
        sessao.get(models.Usuario, "F0001").perfil = "Supervisor"
        sessao.commit()
    assert cliente.get("/me", headers=cabecalho(token)).json()["perfil"] == "Supervisor"


def test_perfil_fora_dos_roles_perde_o_acesso(cliente):
    token = entrar(cliente, "F0001").json()["token"]
    with SessaoLocal() as sessao:
        sessao.get(models.Usuario, "F0001").perfil = "SuperAdmin"
        sessao.commit()
    assert cliente.get("/me", headers=cabecalho(token)).status_code == 401


def test_conta_apagada_perde_o_acesso(cliente):
    token = entrar(cliente, "F0001").json()["token"]
    with SessaoLocal() as sessao:
        sessao.delete(sessao.get(models.Usuario, "F0001"))
        sessao.commit()
    assert cliente.get("/me", headers=cabecalho(token)).status_code == 401


# ---------------------------------------------------------------- token inválido
def test_sem_token_recebe_401(cliente):
    resposta = cliente.get("/me")
    assert resposta.status_code == 401
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


def test_token_expirado_recebe_401(cliente):
    token = criar_token("F0001", agora=datetime.now(UTC) - timedelta(days=1))
    assert cliente.get("/me", headers=cabecalho(token)).status_code == 401


def test_token_com_outra_assinatura_recebe_401(cliente):
    falso = jwt.encode(
        {"sub": "F0013", "exp": datetime.now(UTC) + timedelta(hours=1)}, "outro-segredo-com-pelo-menos-32-bytes!!", algorithm=ALGORITMO
    )
    assert cliente.get("/me", headers=cabecalho(falso)).status_code == 401


def test_token_sem_assinatura_recebe_401(cliente):
    carga = {"sub": "F0013", "exp": datetime.now(UTC) + timedelta(hours=1)}
    sem_assinatura = jwt.encode(carga, key=None, algorithm="none")
    assert cliente.get("/me", headers=cabecalho(sem_assinatura)).status_code == 401


def test_perfil_no_token_e_ignorado(cliente):
    """Claim extra (perfil) num token assinado não muda nada: o perfil vem do banco."""
    carga = {"sub": "F0001", "perfil": "AdminGlobal", "exp": datetime.now(UTC) + timedelta(hours=1)}
    token = jwt.encode(carga, segredo_do_token(), algorithm=ALGORITMO)
    assert cliente.get("/me", headers=cabecalho(token)).json()["perfil"] == "Colaborador"


def test_diretorio_fora_do_ar_responde_503(cliente, monkeypatch):
    token = entrar(cliente, "F0001").json()["token"]

    def fora_do_ar(_id):
        raise ConnectionError("integração indisponível")

    monkeypatch.setattr(dados_sinteticos, "buscar_funcionario", fora_do_ar)
    resposta = cliente.get("/me", headers=cabecalho(token))
    assert resposta.status_code == 503


def test_funcionario_desligado_depois_do_login_perde_o_acesso(cliente, monkeypatch):
    token = entrar(cliente, "F0001").json()["token"]
    original = dados_sinteticos.buscar_funcionario

    def desligado(id_funcionario):
        return {**original(id_funcionario), "situacao": "desligado"}

    monkeypatch.setattr(dados_sinteticos, "buscar_funcionario", desligado)
    assert cliente.get("/me", headers=cabecalho(token)).status_code == 401


# ---------------------------------------------------------------- seed
def test_seed_cria_uma_conta_por_funcionario_mais_o_gestor_e_nao_duplica():
    apoio.mundo()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessaoLocal() as sessao:
        primeira = semear(sessao, SENHA)
        segunda = semear(sessao, SENHA)
    assert primeira == [*FUNCIONARIOS_DA_DEMO, "G0001"]
    assert segunda == []


def test_seed_usa_a_correspondencia_cargo_perfil_e_emails_sinteticos():
    apoio.mundo()
    contas = {conta["id"]: conta for conta in contas_da_demo()}
    for id_funcionario in FUNCIONARIOS_DA_DEMO:
        cargo = dados_sinteticos.buscar_funcionario(id_funcionario)["cargo"]
        assert contas[id_funcionario]["perfil"] == PERFIL_DO_CARGO[cargo].__name__
    assert all(conta["email"].endswith(".example") for conta in contas.values())


def test_seed_le_a_senha_do_env_pelo_configuracao(monkeypatch):
    """Revisão do Enrico no #27: quem só preenche SEED_SENHA_DEMO no .env não precisa passar --senha."""
    from pydantic import SecretStr

    from app import seed
    from app.config import configuracao

    monkeypatch.setattr(configuracao, "seed_senha_demo", SecretStr("senha-do-env"))
    assert seed.senha_padrao() == "senha-do-env"
    monkeypatch.setattr(configuracao, "seed_senha_demo", None)
    assert seed.senha_padrao() is None
    with pytest.raises(SystemExit):  # sem senha em lugar nenhum: o argparse avisa e sai
        seed.main([])
