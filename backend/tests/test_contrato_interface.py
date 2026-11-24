"""Adaptadores do contrato do front (`frontend/CONTRATO_API.md`): `Ferramenta` (§4.10) e `Confirmacao` (§4.9).

O back-end devolve estes objetos como estão. Os testes conferem campo a campo, com os tipos do contrato, e que
nada além do combinado sai (nem o objeto da ferramenta, nem o e-mail em claro da prévia).
"""

import json
import re

import pytest
from ferramentas import catalogo, confirmacoes, dados_sinteticos, governanca

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

CAMPOS_DA_FERRAMENTA = [
    "nome", "area", "descricao", "acesso", "sensibilidade", "status", "integracoes", "liberada", "motivo",
]
CAMPOS_DA_CONFIRMACAO = ["id", "ferramenta", "titulo", "campos", "situacao", "expira_em", "aviso"]
ENVIAR = "enviar_email"
AGENTE = (ENVIAR,)
PEDIDO = {"id_cliente": "M00001", "assunto": "Liquidação de 14/10", "corpo": "Olá, a liquidação falhou."}


@pytest.fixture(scope="module")
def mundo():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(mundo):
    limpar_estado()
    yield
    limpar_estado()


def pessoa(mundo, cargo):
    return usuario_do_diretorio(mundo, FUNCIONARIO_DO_CARGO[cargo])


# --- Ferramenta (§4.10) ----------------------------------------------------------------------------


def test_listar_fichas_traz_o_catalogo_inteiro_com_os_campos_do_contrato_na_ordem(mundo):
    fichas = catalogo.listar_fichas(pessoa(mundo, "atendente_n1"))
    assert [f["nome"] for f in fichas] == catalogo.nomes()
    for ficha in fichas:
        assert list(ficha) == CAMPOS_DA_FERRAMENTA
        assert ficha["acesso"] in governanca.ACESSOS
        assert ficha["sensibilidade"] in governanca.SENSIBILIDADES
        assert ficha["status"] in ("ativa", "inativa", "planejada")
        assert isinstance(ficha["integracoes"], list) and all(isinstance(i, str) for i in ficha["integracoes"])
        assert isinstance(ficha["liberada"], bool)
        assert (ficha["motivo"] is None) == ficha["liberada"]
    json.dumps(fichas)  # só texto, número, booleano e lista: nunca o objeto da ferramenta (MED-3)


def test_liberada_e_motivo_seguem_a_governanca_o_status_e_a_integracao_para_cada_cargo(mundo):
    for cargo in FUNCIONARIO_DO_CARGO:
        usuario = pessoa(mundo, cargo)
        for ficha in catalogo.listar_fichas(usuario):
            tecnico = governanca.motivo_bloqueio(catalogo.carregar()[ficha["nome"]], usuario)
            if tecnico is not None:
                esperado = catalogo.MOTIVOS_PARA_A_PESSOA.get(tecnico, catalogo.MOTIVO_GENERICO)
            elif ficha["status"] == "planejada":
                esperado = catalogo.MOTIVO_PLANEJADA
            elif ficha["status"] == "inativa":
                esperado = ficha["motivo"]
                assert esperado, (cargo, ficha["nome"])
            else:
                esperado = None
            assert (ficha["liberada"], ficha["motivo"]) == (esperado is None, esperado), (cargo, ficha["nome"])


def test_motivo_e_uma_frase_simples_e_nunca_o_texto_tecnico(mundo):
    por_nome = {f["nome"]: f for f in catalogo.listar_fichas(pessoa(mundo, "atendente_n1"))}
    assert por_nome["consultar_saldo_conta"]["motivo"] == "Seu cargo não tem o nível que esta ferramenta pede."
    assert (por_nome["consultar_cliente"]["liberada"], por_nome["consultar_cliente"]["motivo"]) == (True, None)
    sem_perfil = catalogo.listar_fichas(None)  # auditor e admin não usam ferramentas de dados
    assert {(f["liberada"], f["motivo"]) for f in sem_perfil} == {(False, "Seu perfil não usa ferramentas de dados.")}
    tecnicos = set(catalogo.MOTIVOS_PARA_A_PESSOA)
    for cargo in FUNCIONARIO_DO_CARGO:
        assert not tecnicos & {f["motivo"] for f in catalogo.listar_fichas(pessoa(mundo, cargo))}, cargo


def test_ferramenta_com_integracao_desligada_diz_o_porque_na_tela(mundo, monkeypatch):
    monkeypatch.delenv("EMAIL_SMTP_HOST")
    ficha = {f["nome"]: f for f in catalogo.listar_fichas(pessoa(mundo, "atendente_n1"))}[ENVIAR]
    assert (ficha["status"], ficha["liberada"]) == ("inativa", False)
    assert ficha["motivo"] == "E-mail (SMTP): integração desligada pela administração da plataforma."
    assert ".env" not in ficha["motivo"]


def test_descricao_sem_marcador_e_a_planejada_mostra_a_frase_sugerida(mundo):
    por_nome = {f["nome"]: f for f in catalogo.listar_fichas(pessoa(mundo, "atendente_n1"))}
    for ficha in por_nome.values():
        assert "[" not in ficha["descricao"] and "preencher" not in ficha["descricao"], ficha["nome"]
        assert ficha["descricao"] == "" or ficha["descricao"].endswith("."), ficha["nome"]
    assert por_nome["consultar_endereco_cep"]["descricao"] == "Mostra a rua, o bairro e a cidade de um CEP."
    assert por_nome[ENVIAR]["descricao"] == (
        "Prepara um e-mail para um contato do lojista; ele só sai depois que você confirma."
    )
    assert por_nome["resumir_receita_periodo"]["descricao"] == "Receita total de um período."


def test_status_efetivo_planejada_ativa_e_ativa_com_integracao_desligada(mundo, monkeypatch):
    ana = pessoa(mundo, "atendente_n1")
    por_nome = {f["nome"]: f for f in catalogo.listar_fichas(ana)}
    assert por_nome["criar_evento_agenda"]["status"] == "planejada"
    assert por_nome["abrir_chamado_jira"]["status"] == "inativa"  # ativa, mas a suíte deixa o Jira desligado
    assert por_nome["consultar_cliente"]["status"] == "ativa"
    assert por_nome[ENVIAR]["status"] == "ativa"  # a suíte liga o SMTP local
    assert por_nome[ENVIAR]["integracoes"] == ["email"]
    monkeypatch.delenv("EMAIL_SMTP_HOST")
    monkeypatch.setenv("APIS_PUBLICAS_MODO", "desligado")
    por_nome = {f["nome"]: f for f in catalogo.listar_fichas(ana)}
    assert por_nome[ENVIAR]["status"] == "inativa"
    assert por_nome["consultar_endereco_cep"]["status"] == "inativa"
    assert por_nome["consultar_cliente"]["status"] == "ativa"


# --- Confirmacao (§4.9) ----------------------------------------------------------------------------


def preparar(usuario, contexto):
    resposta = catalogo.executar(ENVIAR, PEDIDO, usuario, AGENTE, contexto)
    assert resposta["status"] == "ok", resposta
    return resposta["dados"]["confirmacao_id"]


def test_confirmacao_da_execucao_tem_os_campos_do_contrato_e_a_previa_mascarada(mundo):
    ana = pessoa(mundo, "atendente_n1")
    confirmacao_id = preparar(ana, {"execucao_id": "ex-1", "passo": 4, "agente_id": "ag-1"})
    lista = confirmacoes.confirmacoes_da_execucao("ex-1", ana)
    assert len(lista) == 1
    confirmacao = lista[0]
    assert list(confirmacao) == CAMPOS_DA_CONFIRMACAO
    assert (confirmacao["id"], confirmacao["ferramenta"], confirmacao["titulo"], confirmacao["situacao"]) == (
        confirmacao_id, ENVIAR, "Enviar e-mail", "pendente",
    )
    assert [c["rotulo"] for c in confirmacao["campos"]] == ["Para", "Assunto", "Mensagem"]
    assert all(list(c) == ["rotulo", "valor"] and isinstance(c["valor"], str) for c in confirmacao["campos"])
    para, assunto, mensagem = (c["valor"] for c in confirmacao["campos"])
    assert (assunto, mensagem) == (PEDIDO["assunto"], PEDIDO["corpo"])
    contatos, _ = dados_sinteticos.buscar_contatos("M00001")
    email_em_claro = next(c["email"] for c in contatos if c["papel"] == "financeiro")
    assert email_em_claro not in json.dumps(confirmacao, ensure_ascii=False)
    assert re.fullmatch(r"\S*\*\*\*\S*@\S+ \(financeiro do M00001\)", para)


def test_confirmacao_e_so_da_execucao_e_da_pessoa_que_pediu(mundo):
    ana, outro = pessoa(mundo, "atendente_n1"), pessoa(mundo, "supervisor_atendimento")
    confirmacao_id = preparar(ana, {"execucao_id": "ex-1"})
    preparar(ana, {"execucao_id": "ex-2"})
    assert [c["id"] for c in confirmacoes.confirmacoes_da_execucao("ex-1", ana)] == [confirmacao_id]
    assert confirmacoes.confirmacoes_da_execucao("ex-1", outro) == []
    assert confirmacoes.confirmacoes_da_execucao(None, ana) == []
    assert confirmacoes.confirmacao_para_interface(confirmacao_id, outro) is None
    assert confirmacoes.confirmacao_para_interface(confirmacao_id, ana)["id"] == confirmacao_id
    assert confirmacoes.confirmacao_para_interface("CONF-NAOEXISTE", ana) is None


def test_confirmacao_some_depois_de_confirmar_ou_cancelar_e_decidida_muda_a_situacao(mundo):
    ana = pessoa(mundo, "atendente_n1")
    primeira = preparar(ana, {"execucao_id": "ex-1"})
    segunda = preparar(ana, {"execucao_id": "ex-1"})
    antes = confirmacoes.confirmacao_para_interface(primeira, ana)
    assert confirmacoes.confirmar(primeira, ana)["status"] == "ok"
    assert confirmacoes.cancelar(segunda, ana)["status"] == "ok"
    assert confirmacoes.confirmacao_para_interface(primeira, ana) is None
    assert confirmacoes.confirmacoes_da_execucao("ex-1", ana) == []
    assert confirmacoes.decidida(antes, aprovada=True) == {**antes, "situacao": "aprovada"}
    assert confirmacoes.decidida(antes, aprovada=False)["situacao"] == "cancelada"
    assert antes["situacao"] == "pendente"  # decidida devolve uma cópia


def test_toda_escrita_com_confirmacao_declara_titulo_e_rotulos():
    for nome in governanca.ESCRITA_COM_CONFIRMACAO:
        ferramenta = catalogo.carregar()[nome]
        assert ferramenta.titulo and ferramenta.rotulos_da_previa, nome


def test_rotulos_cobrem_todo_campo_da_previa(mundo):
    """Campo da prévia sem rótulo some do cartão: a pessoa confirmaria sem ver."""
    ana = pessoa(mundo, "atendente_n1")
    resposta = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE, {"execucao_id": "ex-1"})
    campos_da_previa = set(resposta["dados"]) - {"confirmacao_id", "situacao", "expira_em"}
    assert campos_da_previa == set(catalogo.carregar()[ENVIAR].rotulos_da_previa)


def test_expira_em_sai_no_horario_de_brasilia(mundo):
    ana = pessoa(mundo, "atendente_n1")
    resposta = catalogo.executar(ENVIAR, PEDIDO, ana, AGENTE, {"execucao_id": "ex-1"})
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}-03:00", resposta["dados"]["expira_em"])


def test_uma_confirmacao_por_resposta_a_mais_recente_da_execucao(mundo):
    ana = pessoa(mundo, "atendente_n1")
    assert confirmacoes.confirmacao_da_execucao("ex-1", ana) is None
    preparar(ana, {"execucao_id": "ex-1"})
    segunda = preparar(ana, {"execucao_id": "ex-1"})
    assert confirmacoes.confirmacao_da_execucao("ex-1", ana)["id"] == segunda
    assert confirmacoes.confirmacao_da_execucao(None, ana) is None


def test_previa_ja_decidida_e_diferente_de_previa_que_nao_existe(mundo, monkeypatch):
    ana, outro = pessoa(mundo, "atendente_n1"), pessoa(mundo, "supervisor_atendimento")
    confirmada, descartada = preparar(ana, {"execucao_id": "ex-1"}), preparar(ana, {"execucao_id": "ex-1"})
    confirmacoes.confirmar(confirmada, ana)
    confirmacoes.cancelar(descartada, ana)
    assert confirmacoes.situacao_da_decisao(confirmada, ana) == "aprovada"
    assert confirmacoes.situacao_da_decisao(descartada, ana) == "cancelada"
    assert confirmacoes.situacao_da_decisao(confirmada, outro) is None  # a decisão é de quem pediu
    assert confirmacoes.situacao_da_decisao("CONF-NAOEXISTE", ana) is None
    assert confirmacoes.confirmar(confirmada, ana)["mensagem"] == "Esta prévia já foi confirmada."
    assert confirmacoes.cancelar(descartada, ana)["mensagem"] == "Esta prévia já foi descartada."
    assert confirmacoes.confirmar("CONF-NAOEXISTE", ana)["mensagem"] == confirmacoes.MENSAGEM_NAO_ENCONTRADO
    depois = confirmacoes.agora() + confirmacoes.LEMBRAR_DECISAO
    monkeypatch.setattr(confirmacoes, "agora", lambda: depois)
    assert confirmacoes.situacao_da_decisao(confirmada, ana) is None  # esquecida depois de uma hora


def test_envio_que_nao_saiu_nao_fica_marcado_como_confirmado(mundo, monkeypatch):
    ana = pessoa(mundo, "atendente_n1")
    confirmacao_id = preparar(ana, {"execucao_id": "ex-1"})
    monkeypatch.setenv("EMAIL_SMTP_PORTA", "1")  # porta local fechada: nada sai
    resultado = confirmacoes.confirmar(confirmacao_id, ana)
    assert resultado["mensagem"] == confirmacoes.mensagem_nada_saiu(catalogo.carregar()[ENVIAR])
    assert confirmacoes.situacao_da_decisao(confirmacao_id, ana) is None
    assert [c["id"] for c in confirmacoes.confirmacoes_da_execucao("ex-1", ana)] == [confirmacao_id]  # volta à fila
