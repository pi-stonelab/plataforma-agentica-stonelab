"""Testes do decorator exige_permissao (camada 1 aplicada às funções)."""

import pytest
from seguranca import envelope
from seguranca.envelope import PLATAFORMA, exige_permissao
from seguranca.permissoes import (
    Acao,
    AcessoNegado,
    Agente,
    Colaborador,
    Financeiro,
    Plataforma,
)


def montar():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    estranho = plataforma.cadastrar(Colaborador("e", Financeiro(), id="estranho"))
    agente = dono.criar_agente("x", plataforma)
    return plataforma, dono, estranho, agente


@exige_permissao(Acao.EXECUTAR)
def rodar_com_plataforma(plataforma, usuario, agente, pergunta="oi"):
    return f"rodou:{pergunta}"


def test_plataforma_vale_por_chamada_e_nao_vaza_entre_pedidos():
    plataforma_a, dono, estranho, agente = montar()
    plataforma_b = Plataforma()  # pedido de outra pessoa: cadastro vazio
    assert rodar_com_plataforma(plataforma_a, dono, agente) == "rodou:oi"
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(plataforma_b, dono, agente)  # dono não existe nesta plataforma
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(plataforma_a, estranho, agente)
    assert rodar_com_plataforma(plataforma_a, dono, agente, pergunta="de novo") == "rodou:de novo"
    assert [e.permitido for e in plataforma_a.auditoria if e.acao == "EXECUTAR"] == [
        True, False, True,
    ]


def test_plataforma_por_nome_nas_chamadas_com_palavra_chave():
    plataforma, dono, _, agente = montar()
    assert rodar_com_plataforma(
        plataforma=plataforma, usuario=dono, agente=agente, pergunta="k"
    ) == "rodou:k"


@pytest.mark.parametrize("invalida", [None, "texto", object(), 42])
def test_plataforma_que_nao_e_plataforma_nega(invalida):
    _, dono, _, agente = montar()
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(invalida, dono, agente)


def test_plataforma_do_argumento_vence_a_fixada_no_decorator():
    fixada = Plataforma()

    @exige_permissao(Acao.EXECUTAR, plataforma=fixada)
    def funcao(plataforma, usuario, agente):
        return "ok"

    plataforma, dono, _, agente = montar()
    assert funcao(plataforma, dono, agente) == "ok"  # a da chamada, não a fixada (vazia)
    assert fixada.auditoria == []


def test_sem_parametro_plataforma_usa_a_fixada():
    fixada = Plataforma()
    dono = fixada.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", fixada)

    @exige_permissao(Acao.EXECUTAR, plataforma=fixada)
    def funcao(usuario, agente):
        return "ok"

    assert funcao(dono, agente) == "ok"
    assert fixada.auditoria[-1].acao == "EXECUTAR"


def test_sem_parametro_nem_fixada_usa_a_global_da_demo():
    PLATAFORMA._usuarios.clear()
    PLATAFORMA.auditoria.clear()
    PLATAFORMA._agentes.clear()
    try:
        @exige_permissao(Acao.VER)
        def funcao(usuario, agente):
            return "ok"

        dono = PLATAFORMA.cadastrar(Colaborador("d", Financeiro(), id="dono-global"))
        agente = dono.criar_agente("x", PLATAFORMA)
        assert funcao(dono, agente) == "ok"
        with pytest.raises(AcessoNegado):
            funcao(Colaborador("e", Financeiro(), id="fora"), agente)
    finally:
        PLATAFORMA._usuarios.clear()
        PLATAFORMA.auditoria.clear()
        PLATAFORMA._agentes.clear()


def test_funcao_sem_usuario_ou_agente_falha_ao_importar():
    with pytest.raises(TypeError):
        @exige_permissao(Acao.EXECUTAR)
        def sem_agente(usuario, nome_ferramenta):
            ...

    with pytest.raises(TypeError):
        @exige_permissao(Acao.EXECUTAR)
        def sem_usuario(agente):
            ...


def test_acao_invalida_falha_ao_importar():
    with pytest.raises(TypeError):
        exige_permissao("EXECUTAR")


def test_acao_exigida_fica_marcada():
    assert rodar_com_plataforma.acao_exigida is Acao.EXECUTAR

    @exige_permissao(Acao.EDITAR)
    def editar(plataforma, usuario, agente):
        ...

    assert editar.acao_exigida is Acao.EDITAR
    assert editar.__name__ == "editar"  # functools.wraps preserva o nome


def test_chamada_sem_usuario_ou_agente_nega():
    plataforma, dono, _, _ = montar()
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(plataforma, dono)  # falta o agente
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(plataforma)


def test_funcao_nao_roda_quando_a_permissao_e_negada():
    chamadas = []

    @exige_permissao(Acao.EDITAR)
    def editar(plataforma, usuario, agente):
        chamadas.append(1)

    plataforma, _, estranho, agente = montar()
    with pytest.raises(AcessoNegado):
        editar(plataforma, estranho, agente)
    assert chamadas == []


def test_erro_inesperado_na_checagem_vira_acesso_negado():
    class PlataformaQuebrada(Plataforma):
        def autorizar(self, usuario, acao, agente):
            raise RuntimeError("segredo interno")

    quebrada = PlataformaQuebrada()
    _, dono, _, agente = montar()
    chamadas = []

    @exige_permissao(Acao.EXECUTAR)
    def funcao(plataforma, usuario, agente):
        chamadas.append(1)

    with pytest.raises(AcessoNegado) as erro:
        funcao(quebrada, dono, agente)
    assert "segredo interno" not in str(erro.value)
    assert chamadas == []
    assert quebrada.auditoria[-1].permitido is False  # a negação foi registrada


def test_erro_inesperado_com_auditoria_quebrada_ainda_nega():
    class TudoQuebrado(Plataforma):
        def autorizar(self, usuario, acao, agente):
            raise RuntimeError("x")

        def _log(self, *args, **kwargs):
            raise RuntimeError("y")

    _, dono, _, agente = montar()
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(TudoQuebrado(), dono, agente)


def test_gancho_de_auditoria_que_falha_nega_a_acao_decorada():
    def gancho_quebrado(evento):
        raise RuntimeError("banco fora do ar")

    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma._ao_registrar = gancho_quebrado
    chamadas = []

    @exige_permissao(Acao.EXECUTAR)
    def funcao(plataforma, usuario, agente):
        chamadas.append(1)

    with pytest.raises(AcessoNegado):
        funcao(plataforma, dono, agente)
    assert chamadas == []
    assert plataforma.auditoria[-1].permitido is False


def test_agente_inativo_nao_executa_pelo_decorator():
    plataforma, dono, _, agente = montar()
    agente.ativo = False
    with pytest.raises(AcessoNegado):
        rodar_com_plataforma(plataforma, dono, agente)


def test_agente_que_nao_e_agente_nega():
    plataforma, dono, _, _ = montar()
    for falso in (None, "agente", object(), Agente):
        with pytest.raises(AcessoNegado):
            rodar_com_plataforma(plataforma, dono, falso)


def test_global_nao_e_tocada_por_quem_passa_plataforma():
    antes = len(envelope.PLATAFORMA.auditoria)
    plataforma, dono, _, agente = montar()
    rodar_com_plataforma(plataforma, dono, agente)
    assert len(envelope.PLATAFORMA.auditoria) == antes
