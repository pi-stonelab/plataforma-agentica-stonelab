"""Seis ferramentas de leitura novas: cargo, escopo, janela, parâmetros, campos e integração (B2b)."""

import ast
from pathlib import Path

import pytest
from ferramentas import catalogo, dados_sinteticos, governanca
from ferramentas.base import TIPOS_ERRO
from mock.falhas import ligar

from .apoio_ferramentas import (
    CARGOS_COM_FERRAMENTA,
    CARGOS_TRANSVERSAIS,
    FUNCIONARIO_DO_CARGO,
    NEGADO_PELO_CATALOGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_ferramentas_novas import (
    AGENTE,
    CARGOS_DA_FERRAMENTA,
    CARGOS_DO_CALCULO,
    NOVAS,
    argumentos_de,
)

VAREJO, CONTAS_CHAVE, INEXISTENTE = "M00001", "M00005", "M99999"
NEGADA = ("erro", "permissao_negada")
FERRAMENTAS_DE_LOJISTA = tuple(CARGOS_DA_FERRAMENTA)
# Campos de `dados` de cada ferramenta: conjunto fechado (E55, só o que a ficha promete).
CAMPOS_DE_DADOS = {
    "consultar_liquidacoes_cliente": {
        "codigo",
        "liquidacoes",
        "total_encontrado",
        "truncado",
        "janela_dias",
    },
    "listar_chamados_cliente": {"codigo", "chamados", "total_encontrado", "truncado"},
    "listar_faturas_em_atraso": {
        "codigo",
        "faturas",
        "total_encontrado",
        "truncado",
        "valor_total",
    },
    "consultar_contatos_lojista": {"codigo", "contatos", "total_encontrado"},
}
CAMPOS_DOS_ITENS = {
    "consultar_liquidacoes_cliente": (
        "liquidacoes",
        {"id_liquidacao", "data", "valor", "situacao", "motivo_falha"},
    ),
    "listar_chamados_cliente": (
        "chamados",
        {
            "codigo",
            "protocolo",
            "categoria",
            "prioridade",
            "situacao",
            "aberto_por",
            "aberto_em",
            "dias_em_aberto",
            "id_liquidacao",
            "id_fatura",
        },
    ),
    "listar_faturas_em_atraso": (
        "faturas",
        {
            "codigo",
            "tipo",
            "mes_referencia",
            "vencimento",
            "valor",
            "situacao",
            "dias_em_atraso",
        },
    ),
    "consultar_contatos_lojista": (
        "contatos",
        {"id", "nome", "cpf", "papel", "telefone", "email"},
    ),
}


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


def usuario(engine, cargo):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO[cargo])


def pelo_catalogo(nome, argumentos, usuario_):
    return catalogo.executar(nome, argumentos, usuario_, AGENTE)


def resultado(resposta):
    return resposta["status"], resposta["tipo_erro"]


# --- fichas ------------------------------------------------------------------------------------


def test_as_seis_estao_ativas_e_sao_de_leitura_ou_calculo():
    fichas = catalogo.carregar()
    for nome in NOVAS:
        assert fichas[nome].esta_ativa(), nome
        assert fichas[nome].acesso == ("calculo" if nome == "calcular_parcelas" else "leitura")


def test_categorias_sao_finas_e_a_de_calculo_nao_tem_dado_de_lojista():
    fichas = catalogo.carregar()
    esperado = {
        "consultar_liquidacoes_cliente": ("liquidacao",),
        "listar_chamados_cliente": ("chamado",),
        "consultar_historico_contato": ("interacao",),
        "listar_faturas_em_atraso": ("cobranca",),
        "consultar_contatos_lojista": ("contato",),
        "calcular_parcelas": (),
    }
    assert {nome: fichas[nome].categorias_dados for nome in NOVAS} == esperado


def test_so_o_historico_e_conteudo_de_terceiros():
    fichas = catalogo.carregar()
    assert {n for n in NOVAS if fichas[n].conteudo_terceiros} == {"consultar_historico_contato"}


def test_o_esqueleto_de_tickets_virou_listar_chamados_cliente():
    fichas = catalogo.carregar()
    assert "listar_tickets_cliente" not in fichas
    assert fichas["listar_chamados_cliente"].area == "atendimento"


def test_a_ficha_de_cada_ferramenta_tem_os_blocos_completos():
    for nome in NOVAS:
        texto = catalogo._ler_arquivo(catalogo.RAIZ / catalogo.carregar()[nome].area / nome)
        for bloco in ("## Quando usar", "## Quando não usar", "## Parâmetros", "## O que devolve"):
            assert bloco in texto, (nome, bloco)
        assert "[preencher" not in texto, nome
        for parametro in catalogo.carregar()[nome].parametros:
            assert f"`{parametro}`" in texto, (nome, parametro)
        assert "Erros possíveis" in texto or nome == "calcular_parcelas", nome


def test_ferramenta_nao_toca_sql_nem_o_conector_do_mock():
    for nome in NOVAS:
        ficha = catalogo.carregar()[nome]
        arquivo = catalogo.RAIZ / ficha.area / nome / "func.py"
        for no in ast.walk(ast.parse(Path(arquivo).read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                modulos = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                modulos = [no.module or ""] + [f"{no.module}.{a.name}" for a in no.names]
            else:
                continue
            assert not any(
                m.startswith(("sqlalchemy", "mock.consultas", "mock.modelos")) for m in modulos
            ), nome


# --- cargo: permitido e negado -----------------------------------------------------------------


@pytest.mark.parametrize("nome", FERRAMENTAS_DE_LOJISTA)
@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_cargo_permitido_recebe_dado_e_cargo_sem_a_categoria_nao_ve_a_ferramenta(
    engine, nome, cargo
):
    pessoa = usuario(engine, cargo)
    argumentos = argumentos_de(nome, VAREJO)
    if nome == "consultar_historico_contato":
        argumentos["id_cliente"] = "M00009"
    resposta = pelo_catalogo(nome, argumentos, pessoa)
    if cargo in CARGOS_DA_FERRAMENTA[nome]:
        assert resultado(resposta) == ("ok", None), (nome, cargo)
    else:
        assert resposta == NEGADO_PELO_CATALOGO, (nome, cargo)
        direto = catalogo.carregar()[nome].executar(argumentos, pessoa)
        assert resultado(direto) == NEGADA, (nome, cargo)
        assert direto["mensagem"] == "Acesso não permitido."


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_calcular_parcelas_serve_a_todo_cargo_com_ferramenta(engine, cargo):
    resposta = pelo_catalogo(
        "calcular_parcelas", {"valor_total": 100, "numero_parcelas": 2}, usuario(engine, cargo)
    )
    assert cargo in CARGOS_DO_CALCULO and resultado(resposta) == ("ok", None)


@pytest.mark.parametrize("cargo", CARGOS_TRANSVERSAIS)
def test_auditor_e_admin_nao_veem_nenhuma_das_seis(engine, cargo):
    pessoa = usuario(engine, cargo)
    for nome in NOVAS:
        resposta = pelo_catalogo(nome, argumentos_de(nome, VAREJO), pessoa)
        assert resposta == NEGADO_PELO_CATALOGO, nome
    assert not set(NOVAS) & set(catalogo.ferramentas_liberadas(pessoa, AGENTE))


def test_o_que_cada_cargo_lista_no_catalogo_bate_com_a_tabela_escrita_a_mao(engine):
    for cargo in CARGOS_COM_FERRAMENTA:
        liberadas = set(catalogo.ferramentas_liberadas(usuario(engine, cargo), AGENTE))
        esperadas = {n for n, cargos in CARGOS_DA_FERRAMENTA.items() if cargo in cargos}
        assert liberadas & set(NOVAS) == esperadas | {"calcular_parcelas"}, cargo


# --- escopo: fora da carteira == inexistente ---------------------------------------------------


@pytest.mark.parametrize("nome", FERRAMENTAS_DE_LOJISTA)
def test_lojista_fora_do_escopo_e_inexistente_dao_a_mesma_resposta(engine, nome):
    ana = usuario(engine, "atendente_n1")
    fora = pelo_catalogo(nome, argumentos_de(nome, CONTAS_CHAVE), ana)
    inexistente = pelo_catalogo(nome, argumentos_de(nome, INEXISTENTE), ana)
    assert fora == inexistente
    assert resultado(fora) == NEGADA and fora["dados"] is None
    assert "Clínica" not in str(fora)


@pytest.mark.parametrize("nome", FERRAMENTAS_DE_LOJISTA)
def test_quem_ve_todas_as_carteiras_acessa_o_lojista_de_outra_carteira(engine, nome):
    pessoa = usuario(engine, "supervisor_atendimento")  # tem a categoria das cinco, escopo "todas"
    ok = pelo_catalogo(nome, argumentos_de(nome, CONTAS_CHAVE), pessoa)
    if nome == "consultar_historico_contato":  # o chamado CH000062 é de outro lojista
        assert resultado(ok) == ("erro", "nao_encontrado")
    else:
        assert resultado(ok) == ("ok", None)
    inexistente = pelo_catalogo(nome, argumentos_de(nome, INEXISTENTE), pessoa)
    assert resultado(inexistente) == ("erro", "nao_encontrado")


def test_atendente_sem_carteira_no_time_nao_ve_ninguem(engine):
    sem_carteira = governanca.usuario_do_cargo("F0001", "atendente_n1", ())
    for nome in FERRAMENTAS_DE_LOJISTA:
        resposta = pelo_catalogo(nome, argumentos_de(nome, VAREJO), sem_carteira)
        assert resultado(resposta) == NEGADA, nome


# --- parâmetros --------------------------------------------------------------------------------


@pytest.mark.parametrize("nome", FERRAMENTAS_DE_LOJISTA)
@pytest.mark.parametrize(
    "codigo", ["M0001", "m00001", "M00001;", "M00001'; DROP TABLE lojistas;--", "CLI-0001", ""]
)
def test_codigo_malformado_e_recusado(engine, nome, codigo):
    resposta = pelo_catalogo(
        nome, argumentos_de(nome, codigo), usuario(engine, "supervisor_atendimento")
    )
    assert resultado(resposta) == ("erro", "parametro_invalido"), (nome, codigo)


@pytest.mark.parametrize("nome", NOVAS)
def test_argumento_fora_da_ficha_ou_reservado_e_recusado(engine, nome):
    pessoa = usuario(engine, "supervisor_atendimento")  # tem a categoria de todas as de lojista
    base = {"valor_total": 100, "numero_parcelas": 2} if nome == "calcular_parcelas" else None
    for extra in ({"nivel": "N2"}, {"carteira": "todas"}, {"motivo": "preciso"}, {"usuario": "x"}):
        argumentos = {**(base or argumentos_de(nome, VAREJO)), **extra}
        resposta = pelo_catalogo(nome, argumentos, pessoa)
        assert resultado(resposta) == ("erro", "parametro_invalido"), (nome, extra)
        assert resposta["mensagem"] == "Argumentos não aceitos pela ferramenta."


@pytest.mark.parametrize("nome", ["consultar_liquidacoes_cliente", "listar_chamados_cliente"])
@pytest.mark.parametrize("limite", [0, -1, 51, 1000])
def test_limite_fora_de_1_a_50_e_recusado(engine, nome, limite):
    resposta = pelo_catalogo(
        nome, {"id_cliente": VAREJO, "limite": limite}, usuario(engine, "supervisor_atendimento")
    )
    assert resultado(resposta) == ("erro", "parametro_invalido")


def test_historico_recusa_chamado_malformado_e_limite_fora_da_faixa(engine):
    supervisor = usuario(engine, "supervisor_atendimento")
    for chamado in ("ch000062", "CH62", "CH000062;", "CH000062' OR '1'='1", ""):
        resposta = pelo_catalogo(
            "consultar_historico_contato",
            {"id_cliente": "M00009", "id_chamado": chamado},
            supervisor,
        )
        assert resultado(resposta) == ("erro", "parametro_invalido"), chamado
    for limite in (0, 51):
        resposta = pelo_catalogo(
            "consultar_historico_contato",
            {"id_cliente": "M00009", "id_chamado": "CH000062", "limite": limite},
            supervisor,
        )
        assert resultado(resposta) == ("erro", "parametro_invalido")


def test_liquidacoes_recusa_data_inicio_depois_da_data_fim(engine):
    resposta = pelo_catalogo(
        "consultar_liquidacoes_cliente",
        {"id_cliente": VAREJO, "data_inicio": "2026-10-10", "data_fim": "2026-10-01"},
        usuario(engine, "supervisor_atendimento"),
    )
    assert resultado(resposta) == ("erro", "parametro_invalido")


# --- janela de 90 dias nas liquidações (O4) ----------------------------------------------------


def test_liquidacoes_dia_90_passa_e_dia_91_e_negado(engine):
    ana = usuario(engine, "atendente_n1")
    pedido = {"id_cliente": VAREJO}
    dia_90 = pelo_catalogo(
        "consultar_liquidacoes_cliente", {**pedido, "data_inicio": "2026-07-17"}, ana
    )
    dia_91 = pelo_catalogo(
        "consultar_liquidacoes_cliente", {**pedido, "data_inicio": "2026-07-16"}, ana
    )
    assert resultado(dia_90) == ("ok", None)
    assert resultado(dia_91) == NEGADA and dia_91["dados"] is None


def test_liquidacoes_sem_data_inicio_trazem_so_a_janela_do_n1(engine):
    ana = usuario(engine, "atendente_n1")
    dados = pelo_catalogo(
        "consultar_liquidacoes_cliente", {"id_cliente": VAREJO, "limite": 50}, ana
    )["dados"]
    datas = [item["data"] for item in dados["liquidacoes"]]
    assert datas and min(datas) >= "2026-07-17" and dados["janela_dias"] == 90


def test_liquidacoes_do_recebiveis_nao_tem_janela(engine):
    pessoa = usuario(engine, "analista_recebiveis")
    resposta = pelo_catalogo(
        "consultar_liquidacoes_cliente",
        {"id_cliente": VAREJO, "data_inicio": "2026-01-01", "data_fim": "2026-06-30", "limite": 50},
        pessoa,
    )
    assert resultado(resposta) == ("ok", None) and resposta["dados"]["janela_dias"] is None


def test_liquidacoes_cortam_no_limite_e_dizem_que_ha_mais(engine):
    supervisor = usuario(engine, "supervisor_atendimento")
    pedido = {"id_cliente": VAREJO}
    um = pelo_catalogo("consultar_liquidacoes_cliente", {**pedido, "limite": 1}, supervisor)[
        "dados"
    ]
    todos = pelo_catalogo("consultar_liquidacoes_cliente", {**pedido, "limite": 50}, supervisor)[
        "dados"
    ]
    assert len(um["liquidacoes"]) == 1 and um["truncado"] is True
    assert um["total_encontrado"] == todos["total_encontrado"] > 1
    assert todos["liquidacoes"][0] == um["liquidacoes"][0]  # a mais recente primeiro


# --- campos: só o que a ficha promete (E55) ----------------------------------------------------


@pytest.mark.parametrize("nome", list(CAMPOS_DE_DADOS))
def test_dados_tem_exatamente_os_campos_da_ficha(engine, nome):
    codigo = (
        "M00003" if nome == "listar_faturas_em_atraso" else VAREJO
    )  # M00003 deve aluguel e saldo
    resposta = pelo_catalogo(
        nome, argumentos_de(nome, codigo), usuario(engine, "supervisor_atendimento")
    )
    dados = resposta["dados"]
    assert set(dados) == CAMPOS_DE_DADOS[nome]
    lista, campos = CAMPOS_DOS_ITENS[nome]
    assert dados[lista], nome
    for item in dados[lista]:
        assert set(item) == campos, nome


def test_chamados_nao_trazem_resumo_nem_texto_livre(engine):
    resposta = pelo_catalogo(
        "listar_chamados_cliente", {"id_cliente": VAREJO}, usuario(engine, "atendente_n1")
    )
    assert "resumo" not in str(resposta) and "conta de recebimento inválida" not in str(resposta)
    assert set(resposta["dados"]) == CAMPOS_DE_DADOS["listar_chamados_cliente"]  # sem embrulho


def test_chamado_fechado_nao_tem_dias_em_aberto_e_aberto_tem(engine):
    chamados = pelo_catalogo(
        "listar_chamados_cliente",
        {"id_cliente": VAREJO, "limite": 50},
        usuario(engine, "atendente_n1"),
    )["dados"]["chamados"]
    for chamado in chamados:
        assert (chamado["dias_em_aberto"] is None) == (chamado["situacao"] == "fechado")


# --- integração fora do ar e registro sem conteúdo ---------------------------------------------

SISTEMA_DA_FERRAMENTA = {
    "consultar_liquidacoes_cliente": "core",
    "listar_chamados_cliente": "crm",
    "consultar_historico_contato": "crm",
    "listar_faturas_em_atraso": "cobranca",
    "consultar_contatos_lojista": "cadastro",
}


@pytest.mark.parametrize("nome", list(SISTEMA_DA_FERRAMENTA))
def test_sistema_fora_do_ar_vira_integracao_indisponivel_sem_detalhe(engine, nome):
    ligar(SISTEMA_DA_FERRAMENTA[nome])
    argumentos = argumentos_de(nome, "M00009" if nome == "consultar_historico_contato" else VAREJO)
    resposta = pelo_catalogo(nome, argumentos, usuario(engine, "supervisor_atendimento"))
    assert resposta == {
        "status": "erro",
        "dados": None,
        "mensagem": "Integração fora do ar.",
        "tipo_erro": "integracao_indisponivel",
    }
    assert resposta["tipo_erro"] in TIPOS_ERRO


def test_registro_das_seis_nao_guarda_argumento_nem_dado(engine, caplog):
    caplog.set_level("DEBUG")
    coordenador = usuario(engine, "coordenador_financeiro")
    for nome in NOVAS:
        if nome == "calcular_parcelas":
            pelo_catalogo(nome, {"valor_total": 330.67, "numero_parcelas": 4}, coordenador)
        else:
            pelo_catalogo(
                nome, argumentos_de(nome, "M00009"), usuario(engine, "supervisor_atendimento")
            )
    assert len(governanca.REGISTROS) == len(NOVAS)
    for registro in governanca.REGISTROS:
        assert set(registro) == set(governanca.CAMPOS_REGISTRO)
    texto = str(governanca.REGISTROS) + caplog.text
    for segredo in ("M00009", "CH000062", "330", "123.456", "Casa de Sucos", "concorrente"):
        assert segredo not in texto, segredo


def test_fachada_nao_deixa_centavo_solto_e_reais_formata_no_padrao_brasileiro():
    assert dados_sinteticos.reais(184230) == "R$ 1.842,30"
    assert dados_sinteticos.reais(5) == "R$ 0,05"
