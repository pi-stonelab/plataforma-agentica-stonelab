"""KAN-60: agentes, conversas e mensagens de ponta a ponta (API → permissões → agente → ferramentas).

O modelo segue um roteiro; o catálogo, a governança e o diretório do mock rodam de verdade.
"""

import json

import pytest
from agentes.agente_atendimento import agente as agente_atendimento
from agentes.agente_geral import agente as agente_geral
from fastapi.testclient import TestClient

from app import models
from app.db import Base, SessaoLocal, engine
from app.llm_client import ErroLLM, RespostaLLM
from app.main import app
from app.rotas.conversas import obter_llm
from app.seed import semear, semear_agentes

from .apoio_ferramentas import limpar_estado, mundo_do_mock

SENHA = "senha-de-teste"


class ModeloRoteirizado:
    """Faz o papel do LLMClient: devolve as respostas na ordem e guarda o que recebeu."""

    def __init__(self):
        self.respostas = []
        self.chamadas = []

    def roteiro(self, *respostas):
        self.respostas = list(respostas)

    def como_chamar_modelo(self, opcoes=None, ao_responder=None):
        def chamar_modelo(prompt_sistema, prompt, tempo_limite=None):
            self.chamadas.append({"sistema": prompt_sistema, "prompt": prompt})
            if not self.respostas:
                raise ErroLLM("indisponivel", "Servidor do modelo indisponível.")
            texto = self.respostas.pop(0)
            if ao_responder is not None:
                ao_responder(RespostaLLM(texto, "roteiro", 100, 20, 50))
            return texto

        return chamar_modelo


@pytest.fixture
def modelo():
    return ModeloRoteirizado()


@pytest.fixture
def cliente(modelo):
    limpar_estado()
    mundo_do_mock()  # leituras e escritas das ferramentas no mesmo mock em memória
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


def entrar(cliente, id_usuario):
    with SessaoLocal() as sessao:
        email = sessao.get(models.Usuario, id_usuario).email
    token = cliente.post("/auth/login", json={"email": email, "senha": SENHA}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def abrir(cliente, cabecalho, agente_id="ag-atendimento"):
    resposta = cliente.post("/conversas", json={"agente_id": agente_id}, headers=cabecalho)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def roteiro_consultar_cliente(codigo, final="FINAL: Pronto."):
    return (
        "PENSAMENTO: ver áreas.\nLER: ",
        "PENSAMENTO: atendimento.\nLER: atendimento",
        "PENSAMENTO: ler a ficha.\nLER: atendimento/consultar_cliente",
        f'PENSAMENTO: consultar.\nUSAR: consultar_cliente | {{"id_cliente": "{codigo}"}}',
        f"PENSAMENTO: responder.\n{final}",
    )


# ---------------------------------------------------------------- agentes
def ids_dos_agentes(cliente, cabecalho):
    resposta = cliente.get("/agentes", headers=cabecalho)
    assert resposta.status_code == 200
    return {agente["id"]: agente for agente in resposta.json()}


def test_atendente_ve_os_publicos_e_o_proprio_mas_nao_o_convidados_de_outra_area(cliente):
    agentes = ids_dos_agentes(cliente, entrar(cliente, "F0001"))
    assert {"ag-geral", "ag-atendimento", "ag-chamados"} <= set(agentes)
    assert "ag-cobranca" not in agentes
    assert agentes["ag-chamados"]["relacao"] == "dono"
    assert "EXECUTAR" in agentes["ag-atendimento"]["acoes"]
    assert agentes["ag-atendimento"]["dono"] == {"id": "F0006", "nome": "Paulo Rezende"}
    assert agentes["ag-geral"]["dono"]["nome"] == "Plataforma"
    assert len(agentes["ag-geral"]["ferramentas"]) > len(agentes["ag-atendimento"]["ferramentas"])


def test_convidado_ve_o_agente_para_o_qual_foi_convidado(cliente):
    agentes = ids_dos_agentes(cliente, entrar(cliente, "F0009"))
    assert agentes["ag-cobranca"]["relacao"] == "convidado"
    assert "EXECUTAR" in agentes["ag-cobranca"]["acoes"]


def test_agente_desativado_aparece_so_para_ver(cliente):
    agentes = ids_dos_agentes(cliente, entrar(cliente, "F0011"))
    assert agentes["ag-conciliacao"]["ativo"] is False
    assert "EXECUTAR" not in agentes["ag-conciliacao"]["acoes"]
    assert list(agentes)[-1] == "ag-conciliacao"  # ativos primeiro


def test_admin_ve_sem_executar_e_gestor_nao_ve_nada(cliente):
    admin = ids_dos_agentes(cliente, entrar(cliente, "F0013"))
    assert "ag-chamados" not in admin  # privado de outra pessoa
    assert all("EXECUTAR" not in agente["acoes"] for agente in admin.values())
    assert all(agente["relacao"] == "admin" for agente in admin.values())
    assert ids_dos_agentes(cliente, entrar(cliente, "G0001")) == {}


def test_agente_privado_de_outra_pessoa_responde_404(cliente):
    resposta = cliente.get("/agentes/ag-chamados", headers=entrar(cliente, "F0002"))
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Agente não encontrado."}
    assert cliente.get("/agentes/ag-chamados", headers=entrar(cliente, "F0001")).status_code == 200


# ---------------------------------------------------------------- abrir conversa
def test_abrir_conversa_devolve_conversa_vazia(cliente):
    cabecalho = entrar(cliente, "F0001")
    conversa = cliente.post("/conversas", json={"agente_id": "ag-atendimento"}, headers=cabecalho).json()
    assert conversa["mensagens"] == []
    assert conversa["agente"]["pode_executar"] is True
    assert conversa["agente"]["ferramentas"][0] == "consultar_cliente"


def test_nao_abre_conversa_com_agente_desativado_nem_sem_executar(cliente):
    desativado = cliente.post(
        "/conversas", json={"agente_id": "ag-conciliacao"}, headers=entrar(cliente, "F0011")
    )
    assert desativado.status_code == 403
    assert desativado.json() == {"detail": "Este agente foi desativado e só pode ser consultado."}
    admin = cliente.post("/conversas", json={"agente_id": "ag-atendimento"}, headers=entrar(cliente, "F0013"))
    assert admin.status_code == 403
    assert admin.json() == {"detail": "Acesso negado."}  # sem nome de agente nem de pessoa
    invisivel = cliente.post("/conversas", json={"agente_id": "ag-chamados"}, headers=entrar(cliente, "F0002"))
    assert invisivel.status_code == 404


# ---------------------------------------------------------------- mensagens
def test_mensagem_roda_o_agente_com_a_ferramenta_de_verdade(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_consultar_cliente("M00001", "FINAL: O lojista M00001 está ativo."))

    resposta = cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": "  Situação do M00001?  "}, headers=cabecalho
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["resposta"] == "O lojista M00001 está ativo."
    assert corpo["tipo"] == "final"
    assert corpo["confirmacao"] is None
    assert any("'consultar_cliente' executada: ok" in passo for passo in corpo["trajetoria"])
    assert corpo["uso"]["chamadas_modelo"] == 5
    assert corpo["uso"]["tokens_entrada"] == 500
    assert all(chamada["sistema"] == agente_atendimento.SISTEMA for chamada in modelo.chamadas)
    # O resultado mascarado da ferramenta voltou ao modelo.
    assert '"status": "ok"' in modelo.chamadas[-1]["prompt"]

    conversa = cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()
    assert [m["autor"] for m in conversa["mensagens"]] == ["usuario", "agente"]
    assert conversa["mensagens"][0]["texto"] == "Situação do M00001?"
    assert conversa["mensagens"][1]["texto"] == "O lojista M00001 está ativo."
    resumo = cliente.get("/conversas", headers=cabecalho).json()
    assert resumo[0]["id"] == conversa_id
    assert resumo[0]["titulo"] == "Situação do M00001?"


def test_lojista_fora_da_carteira_e_negado_pela_ferramenta(cliente, modelo):
    """Porta 4: a Ana (varejo) não alcança o M00005. Não é erro HTTP; o passo fica no rastro."""
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_consultar_cliente("M00005", "FINAL: Não tenho acesso a esse lojista."))

    corpo = cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": "Situação do M00005?"}, headers=cabecalho
    ).json()

    assert corpo["tipo"] == "final"
    assert any("permissao_negada" in passo for passo in corpo["trajetoria"])
    assert '"permissao_negada"' in modelo.chamadas[-1]["prompt"]


def test_pergunta_guarda_o_estado_no_servidor_e_a_resposta_seguinte_continua(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro("PENSAMENTO: falta o valor.\nPERGUNTAR: Qual o valor da fatura e os dias de atraso?")

    primeira = cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": "Calcule a multa"}, headers=cabecalho
    ).json()
    assert primeira["tipo"] == "pergunta"
    with SessaoLocal() as sessao:
        assert sessao.get(models.Conversa, conversa_id).estado is not None

    # O motor não aceita FINAL sem ler o índice: o turno da resposta começa pela leitura.
    modelo.roteiro("PENSAMENTO: ver áreas.\nLER: ", "PENSAMENTO: tenho tudo.\nFINAL: Multa calculada.")
    segunda = cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": "R$ 1.250,00 e 15 dias"}, headers=cabecalho
    ).json()
    assert segunda.get("tipo") == "final", segunda
    assert "Calcule a multa" in modelo.chamadas[-1]["prompt"]  # o histórico foi junto
    with SessaoLocal() as sessao:
        assert sessao.get(models.Conversa, conversa_id).estado is None


def test_agente_geral_usa_o_prompt_do_geral(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho, "ag-geral")
    modelo.roteiro("PENSAMENTO: simples.\nFINAL: Olá!")
    cliente.post(f"/conversas/{conversa_id}/mensagens", json={"texto": "Oi"}, headers=cabecalho)
    assert modelo.chamadas[0]["sistema"] == agente_geral.SISTEMA


def test_modelo_fora_do_ar_responde_504_e_nao_grava_nada(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro()  # sem respostas: o modelo "cai"

    resposta = cliente.post(f"/conversas/{conversa_id}/mensagens", json={"texto": "Oi"}, headers=cabecalho)

    assert resposta.status_code == 504
    assert resposta.json() == {"detail": "O modelo não respondeu. Tente de novo."}
    assert cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()["mensagens"] == []


@pytest.mark.parametrize(
    ("texto", "detalhe"),
    [("   ", "Escreva uma mensagem."), ("x" * 2001, "Mensagem muito longa (máximo 2.000 caracteres).")],
)
def test_texto_vazio_ou_longo_demais_responde_422(cliente, texto, detalhe):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    resposta = cliente.post(f"/conversas/{conversa_id}/mensagens", json={"texto": texto}, headers=cabecalho)
    assert resposta.status_code == 422
    assert resposta.json() == {"detail": detalhe}


def test_conversa_de_outra_pessoa_responde_404_inclusive_para_o_admin(cliente, modelo):
    conversa_id = abrir(cliente, entrar(cliente, "F0001"))
    for outra in ("F0002", "F0013"):
        cabecalho = entrar(cliente, outra)
        assert cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).status_code == 404
        enviar = cliente.post(f"/conversas/{conversa_id}/mensagens", json={"texto": "Oi"}, headers=cabecalho)
        assert enviar.status_code == 404
        assert cliente.get("/conversas", headers=cabecalho).json() == []
    assert modelo.chamadas == []


def test_agente_desativado_depois_bloqueia_a_conversa_mas_mantem_o_historico(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id = abrir(cliente, cabecalho)
    with SessaoLocal() as sessao:
        sessao.get(models.Agente, "ag-atendimento").ativo = False
        sessao.commit()

    conversa = cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()
    assert conversa["agente"]["pode_executar"] is False
    resposta = cliente.post(f"/conversas/{conversa_id}/mensagens", json={"texto": "Oi"}, headers=cabecalho)
    assert resposta.status_code == 403
    assert modelo.chamadas == []


def test_sem_token_nenhuma_rota_de_agente_ou_conversa_responde(cliente):
    for metodo, caminho in [("get", "/agentes"), ("get", "/conversas"), ("post", "/conversas")]:
        assert getattr(cliente, metodo)(caminho).status_code == 401


def test_front_servido_em_app(cliente):
    resposta = cliente.get("/app/")
    assert resposta.status_code == 200
    assert "<html" in resposta.text.lower()


# ---------------------------------------------------------------- escrita em duas fases (PR 25)
def roteiro_abrir_chamado(codigo="M00001"):
    argumentos = json.dumps(
        {"id_cliente": codigo, "categoria": "Maquininha", "resumo": "Maquininha não liga.", "impede_vender": "sim"}
    )
    return (
        "PENSAMENTO: ver áreas.\nLER: ",
        "PENSAMENTO: atendimento.\nLER: atendimento",
        "PENSAMENTO: ler a ficha.\nLER: atendimento/abrir_chamado",
        f"PENSAMENTO: preparar.\nUSAR: abrir_chamado | {argumentos}",
        "PENSAMENTO: avisar.\nFINAL: A prévia do chamado está esperando a sua confirmação.",
    )


def pedir_chamado(cliente, modelo, cabecalho):
    conversa_id = abrir(cliente, cabecalho)
    modelo.roteiro(*roteiro_abrir_chamado())
    corpo = cliente.post(
        f"/conversas/{conversa_id}/mensagens", json={"texto": "Abra um chamado para o M00001"}, headers=cabecalho
    ).json()
    return conversa_id, corpo


def test_escrita_volta_como_cartao_de_confirmacao_sem_executar(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id, corpo = pedir_chamado(cliente, modelo, cabecalho)

    assert corpo["tipo"] == "confirmacao", corpo
    confirmacao = corpo["confirmacao"]
    assert confirmacao["id"].startswith("CONF-")
    assert confirmacao["ferramenta"] == "abrir_chamado"
    assert confirmacao["situacao"] == "pendente"
    assert {"rotulo", "valor"} <= set(confirmacao["campos"][0])
    historico = cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()
    assert historico["mensagens"][-1]["confirmacao"]["id"] == confirmacao["id"]


def test_confirmar_executa_uma_vez_e_o_historico_mostra_aprovada(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id, corpo = pedir_chamado(cliente, modelo, cabecalho)
    caminho = f"/conversas/{conversa_id}/confirmacoes/{corpo['confirmacao']['id']}"

    feito = cliente.post(caminho, json={"aprovar": True}, headers=cabecalho)
    assert feito.status_code == 200, feito.text
    assert feito.json()["confirmacao"] is None
    assert feito.json()["tipo"] == "final"
    assert cliente.post(caminho, json={"aprovar": True}, headers=cabecalho).status_code == 409

    mensagens = cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()["mensagens"]
    assert mensagens[1]["confirmacao"]["situacao"] == "aprovada"
    assert mensagens[-1]["texto"] == feito.json()["resposta"]


def test_cancelar_nao_executa(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id, corpo = pedir_chamado(cliente, modelo, cabecalho)
    caminho = f"/conversas/{conversa_id}/confirmacoes/{corpo['confirmacao']['id']}"

    cancelado = cliente.post(caminho, json={"aprovar": False}, headers=cabecalho)
    assert cancelado.status_code == 200
    mensagens = cliente.get(f"/conversas/{conversa_id}", headers=cabecalho).json()["mensagens"]
    assert mensagens[1]["confirmacao"]["situacao"] == "cancelada"
    assert cliente.post(caminho, json={"aprovar": True}, headers=cabecalho).status_code == 409


def test_confirmacao_de_outra_pessoa_ou_inexistente_responde_404(cliente, modelo):
    cabecalho = entrar(cliente, "F0001")
    conversa_id, corpo = pedir_chamado(cliente, modelo, cabecalho)
    confirmacao_id = corpo["confirmacao"]["id"]

    outra = entrar(cliente, "F0002")
    caminho = f"/conversas/{conversa_id}/confirmacoes/{confirmacao_id}"
    assert cliente.post(caminho, json={"aprovar": True}, headers=outra).status_code == 404
    inexistente = f"/conversas/{conversa_id}/confirmacoes/CONF-NAOEXISTE"
    assert cliente.post(inexistente, json={"aprovar": True}, headers=cabecalho).status_code == 404


# ---------------------------------------------------------------- catálogo e integrações
def test_ferramentas_marcadas_para_a_pessoa(cliente):
    fichas = {f["nome"]: f for f in cliente.get("/ferramentas", headers=entrar(cliente, "F0001")).json()}
    assert fichas["consultar_cliente"]["liberada"] is True
    assert fichas["registrar_acordo"]["liberada"] is False  # escrita do financeiro
    assert fichas["registrar_acordo"]["motivo"]


def test_gestor_nao_ve_ferramentas(cliente):
    resposta = cliente.get("/ferramentas", headers=entrar(cliente, "G0001"))
    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "Seu perfil não usa ferramentas."}


def test_integracoes_dizem_o_modo_sem_mostrar_credencial(cliente):
    linhas = cliente.get("/integracoes", headers=entrar(cliente, "F0001")).json()
    nomes = {linha["nome"] for linha in linhas}
    assert {"jira", "email", "google_workspace"} <= nomes
    assert all(set(linha) >= {"modo", "configurado", "saude"} for linha in linhas)
    assert "token" not in json.dumps(linhas).lower()
