"""Ferramentas de leitura do atendimento (bloco C): base de conhecimento, chamado, identidade, busca e CSAT."""

import json

import pytest
from ferramentas import governanca
from ferramentas.base import MENSAGEM_TERCEIROS
from mock.falhas import ligar

from . import gabaritos as g
from .apoio_bloco_c import chamar, dados_de, resultado, usuario
from .apoio_ferramentas import limpar_estado, mundo_do_mock

NEGADA = ("erro", "permissao_negada")
BLOQUEADA = ("erro", "ferramenta_inexistente")
INVALIDO = ("erro", "parametro_invalido")


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


# --- consultar_base_conhecimento (KAN-14, caso 1) -----------------------------------------------


def test_base_de_conhecimento_responde_a_duvida_da_maquininha_para_qualquer_cargo(engine):
    for cargo in ("atendente_n1", "analista_cobranca", "coordenador_financeiro"):
        resposta = chamar("consultar_base_conhecimento", {"termo": "maquininha não liga"}, usuario(engine, cargo))
        assert resultado(resposta) == ("ok", None)
        codigos = [artigo["codigo"] for artigo in resposta["dados"]["artigos"]]
        assert "KB015" in codigos


def test_base_de_conhecimento_acha_segunda_via_e_respeita_limite(engine):
    resposta = chamar("consultar_base_conhecimento", {"termo": "segunda via", "limite": 1}, usuario(engine, "atendente_n1"))
    artigos = resposta["dados"]["artigos"]
    assert [a["codigo"] for a in artigos] == ["KB017"] and resposta["dados"]["truncado"] is True
    assert set(artigos[0]) == {"codigo", "titulo_artigo", "categoria", "texto_artigo", "atualizado_em"}


def test_base_de_conhecimento_sem_resultado_devolve_lista_vazia(engine):
    resposta = chamar("consultar_base_conhecimento", {"termo": "criptomoeda"}, usuario(engine, "atendente_n1"))
    assert resposta["dados"] == {"artigos": [], "total_encontrado": 0, "truncado": False}


@pytest.mark.parametrize("argumentos", [{"termo": "ab"}, {"termo": "boleto", "limite": 11}, {"termo": "boleto", "limite": 0}])
def test_base_de_conhecimento_recusa_termo_curto_e_limite_fora(engine, argumentos):
    assert resultado(chamar("consultar_base_conhecimento", argumentos, usuario(engine, "atendente_n1"))) == INVALIDO


def test_base_de_conhecimento_nao_vale_para_cargo_sem_area(engine):
    for cargo in ("auditor_compliance", "admin_plataforma"):
        assert resultado(chamar("consultar_base_conhecimento", {"termo": "boleto"}, usuario(engine, cargo))) == BLOQUEADA


# --- consultar_chamado (KAN-14, caso 2; cenários 7 e 9) ------------------------------------------


def test_chamado_da_ouvidoria_com_prazo_e_mensagens_do_cenario_9(engine):
    resposta = chamar(
        "consultar_chamado", {"id_cliente": g.C9_LOJISTA, "id_chamado": g.C9_CHAMADO_OUVIDORIA}, usuario(engine, "analista_ouvidoria")
    )
    assert resultado(resposta) == ("ok", None) and resposta["mensagem"] == MENSAGEM_TERCEIROS
    dados = dados_de(resposta)
    chamado = dados["chamado"]
    assert (chamado["fila"], chamado["aberto_em"], chamado["prazo_em"]) == ("ouvidoria", g.C9_ABERTURA, g.C9_PRAZO)
    assert (chamado["dias_uteis_restantes"], chamado["prazo_estourado"]) == (g.C9_DIAS_UTEIS_RESTANTES, False)
    assert all(codigo in chamado["resumo"] for codigo in g.C9_CHAMADOS_FECHADOS)
    assert dados["total_de_mensagens"] == len(dados["mensagens"]) and dados["truncado"] is False


def test_chamado_traz_as_mensagens_mais_recentes_em_ordem_cronologica(engine):
    ana = usuario(engine, "atendente_n1")
    completo = dados_de(chamar("consultar_chamado", {"id_cliente": g.C7_LOJISTA, "id_chamado": g.C7_CHAMADO, "limite": 50}, ana))
    curto = dados_de(chamar("consultar_chamado", {"id_cliente": g.C7_LOJISTA, "id_chamado": g.C7_CHAMADO, "limite": 2}, ana))
    assert completo["total_de_mensagens"] > 2
    assert curto["mensagens"] == completo["mensagens"][-2:] and curto["truncado"] is True
    horas = [m["data_hora"] for m in completo["mensagens"]]
    assert horas == sorted(horas)


def test_chamado_do_cenario_7_chega_como_dado_e_com_cpf_e_cartao_mascarados(engine):
    resposta = chamar(
        "consultar_chamado", {"id_cliente": g.C7_LOJISTA, "id_chamado": g.C7_CHAMADO, "limite": 50}, usuario(engine, "atendente_n1")
    )
    texto = json.dumps(resposta, ensure_ascii=False)
    assert resposta["mensagem"] == MENSAGEM_TERCEIROS and "conteudo_de_terceiros" in resposta["dados"]
    for cpf in g.C7_CPFS_DIGITADOS:
        assert cpf not in texto
    for cartao in g.C7_CARTOES_DIGITADOS:
        assert cartao not in texto


def test_chamado_de_outro_lojista_e_chamado_inexistente_tem_a_mesma_resposta(engine):
    ana = usuario(engine, "atendente_n1")
    de_outro = chamar("consultar_chamado", {"id_cliente": "M00001", "id_chamado": g.C7_CHAMADO}, ana)
    inexistente = chamar("consultar_chamado", {"id_cliente": "M00001", "id_chamado": "CH999999"}, ana)
    assert de_outro == inexistente and resultado(de_outro) == ("erro", "nao_encontrado")


def test_chamado_fora_da_carteira_e_negado_antes_de_ler(engine):
    resposta = chamar("consultar_chamado", {"id_cliente": "M00005", "id_chamado": "CH000001"}, usuario(engine, "atendente_n1"))
    assert resultado(resposta) == NEGADA and resposta["mensagem"] == g.MENSAGEM_FORA_DA_CARTEIRA


@pytest.mark.parametrize("id_chamado", ["CH62", "ch000062", "CH0000621", "CH000062' OR '1'='1"])
def test_chamado_recusa_codigo_fora_do_formato(engine, id_chamado):
    resposta = chamar("consultar_chamado", {"id_cliente": g.C7_LOJISTA, "id_chamado": id_chamado}, usuario(engine, "atendente_n1"))
    assert resultado(resposta) == INVALIDO


def test_chamado_e_negado_para_quem_nao_le_chamado(engine):
    resposta = chamar("consultar_chamado", {"id_cliente": "M00001", "id_chamado": "CH000061"}, usuario(engine, "analista_cobranca"))
    assert resultado(resposta) == BLOQUEADA


# --- verificar_identidade_contato (cenário 6) -----------------------------------------------------


def test_cenario_6_numero_fora_do_cadastro_nao_confere_e_manda_encaminhar_ao_n2(engine):
    resposta = chamar(
        "verificar_identidade_contato",
        {"id_cliente": g.C6_LOJISTA, "telefone": g.C6_TELEFONE_NAO_CADASTRADO},
        usuario(engine, "especialista_n2"),
    )
    assert resultado(resposta) == ("ok", None)
    dados = resposta["dados"]
    assert (dados["confere"], dados["papel"]) == (False, None)
    assert "N2" in dados["orientacao"] and "suspeita" in dados["orientacao"]


def test_identidade_confere_com_contato_cadastrado_e_nunca_devolve_o_contato(engine):
    from ferramentas import dados_sinteticos

    contato = dados_sinteticos.buscar_contatos(g.C6_LOJISTA)[0][0]
    resposta = chamar(
        "verificar_identidade_contato",
        {"id_cliente": g.C6_LOJISTA, "email": contato["email"].upper()},
        usuario(engine, "especialista_n2"),
    )
    assert resposta["dados"]["confere"] is True and resposta["dados"]["papel"] == contato["papel"]
    texto = json.dumps(resposta, ensure_ascii=False)
    assert contato["email"].lower() not in texto.lower() and contato["telefone"] not in texto
    assert set(resposta["dados"]) == {"codigo", "confere", "papel", "orientacao"}


@pytest.mark.parametrize(
    "argumentos",
    [{}, {"telefone": "90000-0606"}, {"email": "sem-arroba"}, {"telefone": "", "email": ""}],
)
def test_identidade_exige_telefone_com_ddd_ou_email_valido(engine, argumentos):
    resposta = chamar("verificar_identidade_contato", {"id_cliente": g.C6_LOJISTA} | argumentos, usuario(engine, "especialista_n2"))
    assert resultado(resposta) == INVALIDO


# Contatos de M00001 no mundo do mock: sócio (21) 90000-4321 e financeiro (21) 90000-1873 (dado sintético).
C1_TELEFONE_DO_SOCIO = "(21) 90000-4321"
C1_EMAIL_DO_SOCIO = "felipe.barbosa.m00001@lojistas.example"
C1_EMAIL_DO_FINANCEIRO = "wanda.andrade.m00001@lojistas.example"


def verificar(engine, **contato):
    argumentos = {"id_cliente": "M00001"} | contato
    return chamar("verificar_identidade_contato", argumentos, usuario(engine, "especialista_n2"))


@pytest.mark.parametrize(
    "telefone",
    ["+55 21 90000-4321", "55 (21) 90000-4321", "0 21 90000-4321", "0 (21) 90000-4321", "(21) 90000-4321", "21900004321"],
)
def test_identidade_confere_telefone_com_55_ou_0_na_frente(engine, telefone):
    dados = verificar(engine, telefone=telefone)["dados"]
    assert (dados["confere"], dados["papel"]) == (True, "socio")


def test_identidade_nao_confere_telefone_de_outro_lojista_nem_com_55_na_frente(engine):
    assert verificar(engine, telefone="+55 21 90000-6005")["dados"]["confere"] is False  # sócio de M00006


def test_identidade_com_telefone_e_email_exige_que_os_dois_conferam(engine):
    golpista = verificar(engine, telefone=g.C6_TELEFONE_NAO_CADASTRADO, email=C1_EMAIL_DO_SOCIO)["dados"]
    assert (golpista["confere"], golpista["papel"]) == (False, None) and "suspeita" in golpista["orientacao"]
    outro_email = verificar(engine, telefone=C1_TELEFONE_DO_SOCIO, email="ninguem@lojistas.example")["dados"]
    assert outro_email["confere"] is False


def test_identidade_com_telefone_e_email_de_contatos_diferentes_nao_confere(engine):
    assert verificar(engine, telefone=C1_TELEFONE_DO_SOCIO, email=C1_EMAIL_DO_FINANCEIRO)["dados"]["confere"] is False


def test_identidade_com_telefone_e_email_do_mesmo_contato_confere(engine):
    dados = verificar(engine, telefone="+55 21 90000-4321", email=C1_EMAIL_DO_SOCIO.upper())["dados"]
    assert (dados["confere"], dados["papel"]) == (True, "socio")


def test_identidade_recusa_telefone_curto_mesmo_com_55_na_frente(engine):
    assert resultado(verificar(engine, telefone="+55 1234")) == INVALIDO


def test_identidade_nao_registra_o_telefone_informado(engine):
    chamar("verificar_identidade_contato", {"id_cliente": g.C6_LOJISTA, "telefone": g.C6_TELEFONE_NAO_CADASTRADO}, usuario(engine, "especialista_n2"))
    assert "90000-0606" not in json.dumps(governanca.REGISTROS, ensure_ascii=False, default=str)


def test_identidade_fora_da_carteira_e_negada(engine):
    resposta = chamar("verificar_identidade_contato", {"id_cliente": "M00005", "telefone": "(21) 90000-0000"}, usuario(engine, "atendente_n1"))
    assert resultado(resposta) == NEGADA


# --- buscar_clientes (E31) ---------------------------------------------------------------------


def test_busca_por_nome_sem_acento_e_sem_caixa(engine):
    resposta = chamar("buscar_clientes", {"nome": "PAO DA VILA"}, usuario(engine, "atendente_n1"))
    lojistas = dados_de(resposta)["lojistas"]
    assert [lojista["codigo"] for lojista in lojistas] == [g.C1_LOJISTA]
    assert resposta["mensagem"] == MENSAGEM_TERCEIROS  # nome fantasia é escrito pelo lojista


def test_busca_so_olha_a_carteira_de_quem_pergunta(engine):
    ana = dados_de(chamar("buscar_clientes", {"nome": g.C5_NOME_FANTASIA_FORA}, usuario(engine, "atendente_n1")))
    cobranca = dados_de(chamar("buscar_clientes", {"nome": g.C5_NOME_FANTASIA_FORA}, usuario(engine, "analista_cobranca")))
    assert ana["lojistas"] == [] and ana["total_encontrado"] == 0
    assert [lojista["codigo"] for lojista in cobranca["lojistas"]] == [g.C5_LOJISTA_FORA]


def test_busca_traz_o_nome_armadilha_como_dado(engine):
    resposta = chamar("buscar_clientes", {"nome": "Loja Central"}, usuario(engine, "atendente_n1"))
    assert dados_de(resposta)["lojistas"][0]["codigo"] == g.C7_LOJISTA_DO_NOME_ARMADILHA
    assert "conteudo_de_terceiros" in resposta["dados"]


@pytest.mark.parametrize("nome", ["%%%", "___", "' OR '1'='1"])
def test_busca_trata_curinga_e_aspas_como_texto(engine, nome):
    resposta = chamar("buscar_clientes", {"nome": nome}, usuario(engine, "analista_cobranca"))
    assert resultado(resposta) == ("ok", None) and dados_de(resposta)["lojistas"] == []


def test_busca_recusa_nome_curto(engine):
    assert resultado(chamar("buscar_clientes", {"nome": "pa"}, usuario(engine, "atendente_n1"))) == INVALIDO


# --- resumir_satisfacao (KAN-14, caso 3) ---------------------------------------------------------


def test_satisfacao_resume_notas_e_media_para_o_supervisor(engine):
    resposta = chamar("resumir_satisfacao", {}, usuario(engine, "supervisor_atendimento"))
    resumo = dados_de(resposta)["resumo"]
    assert resumo["respostas"] == sum(resumo["notas"].values()) == 31
    assert resumo["media"] == "3,52"


def test_satisfacao_filtra_reclamacoes_e_traz_o_comentario_armadilha_como_dado(engine):
    resposta = chamar("resumir_satisfacao", {"nota_maxima": 2, "limite": 50}, usuario(engine, "analista_ouvidoria"))
    assert resposta["mensagem"] == MENSAGEM_TERCEIROS
    comentarios = dados_de(resposta)["comentarios"]
    assert comentarios and all(item["nota"] <= 2 and item["comentario"] for item in comentarios)
    assert g.C11_COMENTARIO_ARMADILHA_NO_CHAMADO in {item["id_chamado"] for item in comentarios}


def test_satisfacao_e_so_de_quem_tem_a_categoria(engine):
    for cargo in ("atendente_n1", "especialista_n2", "analista_cobranca", "coordenador_financeiro"):
        assert resultado(chamar("resumir_satisfacao", {}, usuario(engine, cargo))) == BLOQUEADA


@pytest.mark.parametrize(
    "argumentos",
    [{"fila": "vip"}, {"nota_maxima": 6}, {"nota_maxima": 0}, {"data_inicio": "2026-10-10", "data_fim": "2026-10-01"}],
)
def test_satisfacao_recusa_parametro_invalido(engine, argumentos):
    assert resultado(chamar("resumir_satisfacao", argumentos, usuario(engine, "supervisor_atendimento"))) == INVALIDO


def test_crm_fora_do_ar_responde_integracao_indisponivel(engine):
    ligar("crm")
    resposta = chamar("consultar_chamado", {"id_cliente": g.C9_LOJISTA, "id_chamado": g.C9_CHAMADO_OUVIDORIA}, usuario(engine, "analista_ouvidoria"))
    assert resultado(resposta) == ("erro", "integracao_indisponivel")
