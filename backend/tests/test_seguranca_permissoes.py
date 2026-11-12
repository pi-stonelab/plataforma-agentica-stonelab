"""Testes da camada 1 (acesso ao agente): matriz de decisão, auditoria e ciclo de perfis.

A tabela ESPERADA é escrita à mão, a partir da decisão do grupo (seguranca/README.md).
Ela não é calculada com o código que está sendo testado.
"""

import runpy
from pathlib import Path

import pytest
from seguranca.permissoes import (
    DONO_PLATAFORMA,
    Acao,
    AcessoNegado,
    AdminGlobal,
    Agente,
    AtendimentoCliente,
    Auditor,
    Colaborador,
    Financeiro,
    GestorDeAcessos,
    Plataforma,
    Supervisor,
    Visibilidade,
    area_do_slug,
)

TODAS = frozenset(Acao)
USAR = frozenset({Acao.VER, Acao.EXECUTAR})
NADA = frozenset()
PRIV, CONV, PUB = Visibilidade.PRIVADO, Visibilidade.CONVIDADOS, Visibilidade.PUBLICO

# Quem gerencia faz tudo, mas só convida com visibilidade CONVIDADOS (decisão do Pedro, 11/11).
GERENCIA = {PRIV: TODAS - {Acao.CONVIDAR}, CONV: TODAS, PUB: TODAS - {Acao.CONVIDAR}}
GERENCIA_SEM_EXECUTAR = {v: acoes - {Acao.EXECUTAR} for v, acoes in GERENCIA.items()}

# relação da pessoa com o agente (a pessoa de teste é sempre da área Financeiro)
RELACOES = ["dono", "convidado_mesma_area", "convidado_outra_area", "mesma_area", "outra_area"]

# (perfil, relação) -> {visibilidade: ações permitidas com o agente ATIVO}
ESPERADO_ATIVO = {
    ("Colaborador", "dono"): GERENCIA,
    ("Colaborador", "convidado_mesma_area"): {PRIV: NADA, CONV: USAR, PUB: USAR},
    ("Colaborador", "convidado_outra_area"): {PRIV: NADA, CONV: USAR, PUB: USAR},
    ("Colaborador", "mesma_area"): {PRIV: NADA, CONV: NADA, PUB: USAR},
    ("Colaborador", "outra_area"): {PRIV: NADA, CONV: NADA, PUB: USAR},
    ("Supervisor", "dono"): GERENCIA,
    ("Supervisor", "convidado_mesma_area"): {PRIV: NADA, CONV: TODAS, PUB: GERENCIA[PUB]},
    ("Supervisor", "convidado_outra_area"): {PRIV: NADA, CONV: USAR, PUB: USAR},
    ("Supervisor", "mesma_area"): {PRIV: NADA, CONV: TODAS, PUB: GERENCIA[PUB]},
    ("Supervisor", "outra_area"): {PRIV: NADA, CONV: NADA, PUB: USAR},
}
_ADMIN = {PRIV: {Acao.DEPRECAR}, CONV: {Acao.VER, Acao.DEPRECAR}, PUB: {Acao.VER, Acao.DEPRECAR}}
for _rel in RELACOES:
    ESPERADO_ATIVO[("AdminGlobal", _rel)] = {v: frozenset(a) for v, a in _ADMIN.items()}
    ESPERADO_ATIVO[("Auditor", _rel)] = {PRIV: NADA, CONV: NADA, PUB: NADA}
    ESPERADO_ATIVO[("GestorDeAcessos", _rel)] = {PRIV: NADA, CONV: NADA, PUB: NADA}

# Agente INATIVO: quem gerencia perde só o EXECUTAR; quem só usa perde tudo (some da lista).
ESPERADO_INATIVO = {
    ("Colaborador", "dono"): GERENCIA_SEM_EXECUTAR,
    ("Supervisor", "dono"): GERENCIA_SEM_EXECUTAR,
    ("Supervisor", "convidado_mesma_area"): {**GERENCIA_SEM_EXECUTAR, PRIV: NADA},
    ("Supervisor", "mesma_area"): {**GERENCIA_SEM_EXECUTAR, PRIV: NADA},
}
for _chave, _por_vis in ESPERADO_ATIVO.items():
    if _chave in ESPERADO_INATIVO:
        continue
    if _chave[0] in {"Colaborador", "Supervisor"}:
        ESPERADO_INATIVO[_chave] = {v: NADA for v in Visibilidade}
    else:  # Admin, Auditor e Gestor: ativo não muda nada (Admin nunca executa mesmo)
        ESPERADO_INATIVO[_chave] = _por_vis


def montar_cenario(perfil: str, relacao: str, visibilidade: Visibilidade, ativo: bool):
    """Devolve (plataforma, pessoa, agente) já cadastrados, com a relação pedida."""
    plataforma = Plataforma()
    fabrica = {
        "Colaborador": lambda: Colaborador("pessoa", Financeiro(), id="pessoa"),
        "Supervisor": lambda: Supervisor("pessoa", Financeiro(), id="pessoa"),
        "AdminGlobal": lambda: AdminGlobal("pessoa", id="pessoa"),
        "Auditor": lambda: Auditor("pessoa", id="pessoa"),
        "GestorDeAcessos": lambda: GestorDeAcessos("pessoa", Financeiro(), id="pessoa"),
    }
    pessoa = plataforma.cadastrar(fabrica[perfil]())
    em_outra_area = relacao in {"convidado_outra_area", "outra_area"}
    area_do_agente = AtendimentoCliente() if em_outra_area else Financeiro()
    dono_id = "pessoa" if relacao == "dono" else "outro-dono"
    convidados = {"pessoa"} if relacao.startswith("convidado") else set()
    agente = Agente("agente", area_do_agente, dono_id, convidados_ids=convidados,
                    visibilidade=visibilidade, ativo=ativo)
    plataforma.carregar_agente(agente)  # a Plataforma só decide sobre agente registrado
    return plataforma, pessoa, agente


CASOS = [(perfil, rel) for (perfil, rel) in ESPERADO_ATIVO]


@pytest.mark.parametrize("ativo", [True, False], ids=["ativo", "inativo"])
@pytest.mark.parametrize("visibilidade", list(Visibilidade), ids=lambda v: v.name)
@pytest.mark.parametrize("perfil,relacao", CASOS)
@pytest.mark.parametrize("acao", list(Acao), ids=lambda a: a.name)
def test_matriz_pode_e_autorizar(perfil, relacao, visibilidade, acao, ativo):
    tabela = ESPERADO_ATIVO if ativo else ESPERADO_INATIVO
    esperado = acao in tabela[(perfil, relacao)][visibilidade]
    plataforma, pessoa, agente = montar_cenario(perfil, relacao, visibilidade, ativo)

    assert pessoa.pode(acao, agente) is esperado
    if esperado:
        plataforma.autorizar(pessoa, acao, agente)
    else:
        with pytest.raises(AcessoNegado):
            plataforma.autorizar(pessoa, acao, agente)
    assert plataforma.auditoria[-1].permitido is esperado


def test_matriz_cobre_todos_os_perfis_e_relacoes():
    perfis = {perfil for perfil, _ in CASOS}
    assert perfis == {"Colaborador", "Supervisor", "AdminGlobal", "Auditor", "GestorDeAcessos"}
    assert len(CASOS) == 5 * len(RELACOES)
    assert set(ESPERADO_INATIVO) == set(ESPERADO_ATIVO)


# ---------------------------------------------------------------- casos que a matriz não cobre
def test_padrao_do_agente_e_privado_e_ativo():
    agente = Agente("a", Financeiro(), "dono-1")
    assert agente.visibilidade is Visibilidade.PRIVADO
    assert agente.ativo is True


def test_para_convidar_o_dono_muda_para_convidados():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    amigo = plataforma.cadastrar(Colaborador("a", Financeiro(), id="amigo"))
    agente = dono.criar_agente("meu", plataforma)  # nasce PRIVADO
    with pytest.raises(AcessoNegado):
        plataforma.convidar(dono, amigo, agente)
    assert agente.convidados_ids == set()
    plataforma.alterar_visibilidade(dono, agente, Visibilidade.CONVIDADOS)
    plataforma.convidar(dono, amigo, agente)
    plataforma.autorizar(amigo, Acao.EXECUTAR, agente)


def test_supervisor_com_area_extra_gerencia_agente_aberto_da_outra_area():
    plataforma = Plataforma()
    sup = Supervisor("s", Financeiro(), id="sup", areas_extras={AtendimentoCliente()})
    plataforma.cadastrar(sup)
    aberto = Agente("a", AtendimentoCliente(), "outro", visibilidade=CONV)
    privado = Agente("b", AtendimentoCliente(), "outro", visibilidade=PRIV)
    assert sup.pode(Acao.EDITAR, aberto)
    assert not sup.pode(Acao.VER, privado)


def test_visibilidade_aceita_valor_do_banco_e_recusa_invalido():
    agente = Agente("a", Financeiro(), "dono", visibilidade="publico")
    assert agente.visibilidade is Visibilidade.PUBLICO
    with pytest.raises(ValueError):
        Agente("a", Financeiro(), "dono", visibilidade="qualquer")
    with pytest.raises(ValueError):
        Agente("a", Financeiro(), "")


def test_id_do_agente_vem_do_banco_ou_do_contador():
    do_banco = Agente("a", Financeiro(), "dono", id="ag-uuid-1")
    assert do_banco.id == "ag-uuid-1"
    sem_id_1, sem_id_2 = Agente("a", Financeiro(), "d"), Agente("b", Financeiro(), "d")
    assert isinstance(sem_id_1.id, int) and sem_id_2.id == sem_id_1.id + 1


def test_convidados_ids_nao_e_compartilhado_entre_agentes():
    um, outro = Agente("a", Financeiro(), "d"), Agente("b", Financeiro(), "d")
    um.convidados_ids.add("x")
    assert outro.convidados_ids == set()


def test_colaborador_e_supervisor_exigem_area():
    with pytest.raises(ValueError):
        Colaborador("c", None)
    with pytest.raises(ValueError):
        Supervisor("s", None)


def test_admin_e_auditor_aceitam_area_opcional():
    assert AdminGlobal("a").area is None
    assert Auditor("a").area is None


# ---------------------------------------------------------------- Admin
def test_admin_nunca_executa_nem_edita_nem_convida():
    plataforma = Plataforma()
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    for visibilidade in Visibilidade:
        agente = Agente("x", Financeiro(), "dono", visibilidade=visibilidade)
        for acao in (Acao.EXECUTAR, Acao.EDITAR, Acao.CONVIDAR):
            with pytest.raises(AcessoNegado):
                plataforma.autorizar(admin, acao, agente)


def test_admin_nao_cria_agente_nem_lista_privado():
    plataforma = Plataforma()
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    privado = dono.criar_agente("privado", plataforma)
    publico = dono.criar_agente("publico", plataforma)
    plataforma.alterar_visibilidade(dono, publico, PUB)
    with pytest.raises(AcessoNegado):
        admin.criar_agente("meu", plataforma)
    assert plataforma.agentes_visiveis(admin) == [publico]
    assert privado not in plataforma.agentes_visiveis(admin)


# ---------------------------------------------------------------- Auditor
def test_auditor_le_auditoria_e_admin_nao():
    plataforma = Plataforma()
    auditor = plataforma.cadastrar(Auditor("a", id="aud"))
    admin = plataforma.cadastrar(AdminGlobal("b", id="adm"))
    dono = plataforma.cadastrar(Colaborador("c", Financeiro(), id="dono"))
    dono.criar_agente("x", plataforma)

    # só autoriza: não devolve eventos (quem lê é o back-end, na tabela de auditoria)
    assert plataforma.autorizar_leitura_auditoria(auditor) is None
    assert [e.acao for e in plataforma.auditoria] == ["CRIAR", "LER_AUDITORIA"]
    assert plataforma.auditoria[-1].permitido is True  # a leitura também é registrada
    with pytest.raises(AcessoNegado):
        plataforma.autorizar_leitura_auditoria(admin)
    assert plataforma.auditoria[-1].acao == "LER_AUDITORIA"  # a tentativa também fica registrada
    assert plataforma.auditoria[-1].permitido is False


def test_so_o_auditor_declara_pode_ler_auditoria():
    from seguranca.permissoes import ROLES

    com_poder = {r for r in ROLES if r.pode_ler_auditoria}
    assert com_poder == {Auditor}


def test_auditor_nao_cria_nem_ve_nem_executa():
    plataforma = Plataforma()
    auditor = plataforma.cadastrar(Auditor("a", id="aud"))
    with pytest.raises(AcessoNegado):
        auditor.criar_agente("x", plataforma)
    assert plataforma.agentes_visiveis(auditor) == []


def test_pessoa_desconhecida_nao_le_auditoria():
    plataforma = Plataforma()
    with pytest.raises(AcessoNegado):
        plataforma.autorizar_leitura_auditoria(Auditor("fantasma", id="nao-cadastrado"))


# ---------------------------------------------------------------- usa_ferramentas
def test_usa_ferramentas_so_para_colaborador_e_supervisor():
    from seguranca.permissoes import ROLES

    assert {r for r in ROLES if r.usa_ferramentas} == {Colaborador, Supervisor}
    assert Colaborador.usa_ferramentas is True and AdminGlobal.usa_ferramentas is False


def test_perfil_novo_nasce_sem_poder():
    from seguranca.permissoes import Usuario

    class Novo(Usuario):
        def pode(self, acao, agente):
            return False

    assert (Novo.usa_ferramentas, Novo.cria_agentes, Novo.pode_ler_auditoria) == (False,) * 3


# ---------------------------------------------------------------- Area.slug
def test_slug_das_areas_e_conversao():
    assert Financeiro().slug == "financeiro"
    assert AtendimentoCliente().slug == "atendimento"
    assert area_do_slug("atendimento") == AtendimentoCliente()
    assert area_do_slug("financeiro") == Financeiro()
    for invalido in ("dados", "tecnologia", ""):
        with pytest.raises(ValueError):
            area_do_slug(invalido)


# ---------------------------------------------------------------- Evento e mensagens sem nome
NOME = "Fulana Sobrenome Secreto"


def test_evento_guarda_so_o_id_nunca_o_objeto_nem_o_nome():
    plataforma = Plataforma()
    pessoa = plataforma.cadastrar(Colaborador(NOME, Financeiro(), id="u-1"))
    agente = pessoa.criar_agente("Agente Confidencial", plataforma)
    plataforma.autorizar(pessoa, Acao.VER, agente)
    for evento in plataforma.auditoria:
        assert isinstance(evento.id_usuario, str) and evento.id_usuario == "u-1"
        assert NOME not in repr(evento) and "Agente Confidencial" not in repr(evento)
        assert not hasattr(evento, "usuario")


def test_acesso_negado_e_repr_nao_tem_nome():
    plataforma = Plataforma()
    estranho = plataforma.cadastrar(Colaborador(NOME, Financeiro(), id="u-2"))
    dono = plataforma.cadastrar(Colaborador("Outro Nome", Financeiro(), id="u-3"))
    agente = dono.criar_agente("Agente Confidencial", plataforma)
    gestor = plataforma.cadastrar(GestorDeAcessos("Gestora Nome", Financeiro(), id="u-4"))
    fantasma = Colaborador("Fantasma Nome", Financeiro(), id="f")
    tentativas = [
        lambda: plataforma.autorizar(estranho, Acao.VER, agente),
        lambda: gestor.criar_agente("x", plataforma),
        lambda: plataforma.atribuir_role(gestor, gestor, AdminGlobal),
        lambda: plataforma.atribuir_role(estranho, dono, AdminGlobal),
        lambda: plataforma.convidar(dono, fantasma, agente),
        lambda: plataforma.autorizar_leitura_auditoria(estranho),
    ]
    mensagens = []
    for tentativa in tentativas:
        with pytest.raises(AcessoNegado) as erro:
            tentativa()
        mensagens.append(str(erro.value))
    texto = " ".join(mensagens) + repr(estranho) + repr(gestor)
    for proibido in (NOME, "Outro Nome", "Gestora Nome", "Agente Confidencial", "Fantasma Nome"):
        assert proibido not in texto


def test_pessoa_sem_id_textual_vira_desconhecida_no_evento():
    plataforma = Plataforma()
    agente = Agente("a", Financeiro(), "dono", id="ag")
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(object(), Acao.VER, agente)
    assert plataforma.auditoria[-1].id_usuario == "desconhecido"


# ---------------------------------------------------------------- gancho de auditoria
def test_gancho_recebe_cada_evento():
    recebidos = []
    plataforma = Plataforma(ao_registrar=recebidos.append)
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.autorizar(dono, Acao.VER, agente)
    assert [(e.acao, e.permitido) for e in recebidos] == [("CRIAR", True), ("VER", True)]
    assert recebidos == plataforma.auditoria


def test_gancho_que_falha_nega_a_autorizacao():
    def gancho_quebrado(evento):
        raise RuntimeError("banco fora do ar")

    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma._ao_registrar = gancho_quebrado
    with pytest.raises(AcessoNegado) as erro:
        plataforma.autorizar(dono, Acao.EXECUTAR, agente)
    assert "banco fora do ar" not in str(erro.value)
    assert plataforma.auditoria[-1].permitido is False  # nunca fica "permitido" sem ter sido gravado


def test_gancho_que_falha_impede_criar_agente_e_mudar_perfil():
    def gancho_quebrado(evento):
        raise RuntimeError("falha")

    plataforma = Plataforma(ao_registrar=gancho_quebrado)
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    with pytest.raises(AcessoNegado):
        dono.criar_agente("x", plataforma)
    assert plataforma._agentes == {}
    with pytest.raises(AcessoNegado):
        gestor.atribuir_role(dono, Supervisor, plataforma)
    assert type(plataforma.usuario("dono")) is Colaborador
    with pytest.raises(AcessoNegado):
        gestor.remover_role(dono, plataforma)
    assert plataforma.usuario("dono") is dono


# ---------------------------------------------------------------- pessoa removida ou rebaixada
def test_pessoa_removida_perde_acesso_mesmo_com_objeto_antigo():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.autorizar(dono, Acao.EXECUTAR, agente)
    gestor.remover_role(dono, plataforma)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.VER, agente)
    assert plataforma.agentes_visiveis(dono) == []


def test_pessoa_rebaixada_perde_os_poderes_do_perfil_antigo():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    sup = plataforma.cadastrar(Supervisor("s", Financeiro(), id="sup"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.alterar_visibilidade(dono, agente, PUB)
    plataforma.autorizar(sup, Acao.EDITAR, agente)  # supervisor da área edita aberto
    gestor.atribuir_role(sup, Colaborador, plataforma)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(sup, Acao.EDITAR, agente)  # o objeto antigo (Supervisor) não vale
    plataforma.autorizar(sup, Acao.EXECUTAR, agente)  # continua podendo usar um agente público


def test_rebaixado_a_admin_deixa_de_executar_o_proprio_agente():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    gestor.atribuir_role(dono, AdminGlobal, plataforma)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.EXECUTAR, agente)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.VER, agente)  # privado: nem o ex-dono, agora Admin


def test_perfil_com_area_obrigatoria_nao_nasce_sem_area():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    with pytest.raises(ValueError):
        gestor.atribuir_role(admin, Colaborador, plataforma)  # admin não tem área
    assert type(plataforma.usuario("adm")) is AdminGlobal
    assert plataforma.auditoria[-1].permitido is False
    gestor.atribuir_role(admin, Colaborador, plataforma, area=Financeiro())  # com área, ok


# ---------------------------------------------------------------- GestorDeAcessos
def test_gestor_nao_altera_a_si_mesmo():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    with pytest.raises(AcessoNegado):
        gestor.atribuir_role(gestor, AdminGlobal, plataforma)
    with pytest.raises(AcessoNegado):
        gestor.remover_role(gestor, plataforma)
    assert type(plataforma.usuario("gestor")) is GestorDeAcessos


def test_so_o_gestor_administra_perfis_e_role_desconhecida_falha():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    alvo = plataforma.cadastrar(Colaborador("c", Financeiro(), id="alvo"))
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    with pytest.raises(AcessoNegado):
        plataforma.atribuir_role(admin, alvo, Supervisor)
    with pytest.raises(ValueError):
        gestor.atribuir_role(alvo, Agente, plataforma)  # não é um perfil
    with pytest.raises(AcessoNegado):
        gestor.atribuir_role(Colaborador("x", Financeiro(), id="fora"), Supervisor, plataforma)


def test_gestor_cria_auditor_e_admin_sem_dono_de_agente():
    plataforma = Plataforma()
    gestor = plataforma.cadastrar(GestorDeAcessos("g", Financeiro(), id="gestor"))
    alvo = plataforma.cadastrar(Colaborador("c", Financeiro(), id="alvo"))
    novo = gestor.atribuir_role(alvo, Auditor, plataforma)
    assert isinstance(novo, Auditor) and novo.id == "alvo" and novo.pode_ler_auditoria


# ---------------------------------------------------------------- registrar e convidar
def test_so_registra_agente_em_nome_proprio():
    plataforma = Plataforma()
    ana = plataforma.cadastrar(Colaborador("a", Financeiro(), id="ana"))
    plataforma.cadastrar(Colaborador("b", Financeiro(), id="bia"))
    falso = Agente("x", Financeiro(), "bia")
    with pytest.raises(AcessoNegado):
        plataforma.registrar(falso, ana)  # ana tentando criar agente em nome da bia
    assert plataforma._agentes == {}


def test_convidar_exige_pessoa_cadastrada_e_permissao():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    outro = plataforma.cadastrar(Colaborador("o", Financeiro(), id="outro"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.alterar_visibilidade(dono, agente, Visibilidade.CONVIDADOS)
    with pytest.raises(AcessoNegado):
        plataforma.convidar(outro, dono, agente)  # só o dono convida
    with pytest.raises(AcessoNegado):
        plataforma.convidar(dono, Colaborador("f", Financeiro(), id="fantasma"), agente)
    plataforma.convidar(dono, outro, agente)
    assert agente.convidados_ids == {"outro"}


# ---------------------------------------------------------------- autorizar: falha fechada
def test_autorizar_nega_com_agente_ou_pessoa_invalidos():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.VER, None)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(None, Acao.VER, Agente("a", Financeiro(), "dono"))


def test_autorizar_nega_executar_em_inativo_mesmo_se_o_perfil_esquecer():
    from seguranca.permissoes import Usuario

    class Esquecido(Usuario):
        def pode(self, acao, agente):
            return True  # perfil novo que não olha `ativo`

    plataforma = Plataforma()
    pessoa = plataforma.cadastrar(Esquecido("e", None, id="esq"))
    agente = Agente("a", Financeiro(), "dono", ativo=False)
    plataforma.carregar_agente(agente)
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(pessoa, Acao.EXECUTAR, agente)


def test_uma_decisao_gera_um_evento():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    antes = len(plataforma.auditoria)
    plataforma.autorizar(dono, Acao.VER, agente)
    assert len(plataforma.auditoria) == antes + 1


# ---------------------------------------------------------------- demo
def test_demo_roda_e_nao_imprime_nome(capsys):
    caminho = Path(__file__).resolve().parents[2] / "seguranca" / "permissoes.py"
    runpy.run_path(str(caminho), run_name="__main__")
    saida = capsys.readouterr().out
    assert "Bloqueado" in saida
    for nome in ("Ana", "Bruno", "João", "Maria", "Carla", "Davi"):
        assert nome not in saida


# ---------------------------------------------------------------- ALTO-1: decide o agente registrado
def test_agente_forjado_com_mesmo_id_nao_ganha_acesso():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    atacante = plataforma.cadastrar(Colaborador("m", Financeiro(), id="atacante"))
    real = dono.criar_agente("privado", plataforma)  # PRIVADO, do "dono"
    forjado = Agente("privado", Financeiro(), "atacante", id=real.id, visibilidade=PUB)
    for acao in Acao:
        with pytest.raises(AcessoNegado):
            plataforma.autorizar(atacante, acao, forjado)
    assert plataforma.auditoria[-1].permitido is False
    assert plataforma._agentes[real.id] is real  # o registrado não foi trocado


def test_agente_nao_registrado_e_negado_ate_para_o_dono():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    solto = Agente("solto", Financeiro(), "dono")
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.VER, solto)


def test_copia_igual_ao_registrado_vale_e_copia_alterada_nao():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    real = dono.criar_agente("x", plataforma)
    copia = Agente("x", Financeiro(), "dono", id=real.id)  # como se viesse de outra leitura do banco
    plataforma.autorizar(dono, Acao.VER, copia)
    copia.visibilidade = PUB  # a cópia agora difere do registrado
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(dono, Acao.VER, copia)


def test_convidar_grava_no_agente_registrado():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    amigo = plataforma.cadastrar(Colaborador("a", Financeiro(), id="amigo"))
    real = dono.criar_agente("x", plataforma)
    real.visibilidade = Visibilidade.CONVIDADOS
    plataforma.convidar(dono, amigo, real)
    assert plataforma._agentes[real.id].convidados_ids == {"amigo"}


# ---------------------------------------------------------------- MED-4: registrar
def test_registrar_nao_sobrescreve_agente_com_id_existente():
    plataforma = Plataforma()
    ana = plataforma.cadastrar(Colaborador("a", Financeiro(), id="ana"))
    bia = plataforma.cadastrar(Colaborador("b", Financeiro(), id="bia"))
    original = ana.criar_agente("original", plataforma)
    colide = Agente("colide", Financeiro(), "bia", id=original.id)
    with pytest.raises(AcessoNegado):
        plataforma.registrar(colide, bia)
    assert plataforma._agentes[original.id] is original
    assert plataforma.auditoria[-1].acao == "CRIAR" and plataforma.auditoria[-1].permitido is False


def test_registrar_so_na_area_do_criador():
    plataforma = Plataforma()
    ana = plataforma.cadastrar(Colaborador("a", AtendimentoCliente(), id="ana"))
    de_outra_area = Agente("x", Financeiro(), "ana")
    with pytest.raises(AcessoNegado):
        plataforma.registrar(de_outra_area, ana)
    assert plataforma._agentes == {}
    # a própria área é aceita
    plataforma.registrar(Agente("y", AtendimentoCliente(), "ana"), ana)


def test_supervisor_registra_nas_suas_areas_extras_e_so_nelas():
    plataforma = Plataforma()
    sup = plataforma.cadastrar(
        Supervisor("s", Financeiro(), id="sup", areas_extras={AtendimentoCliente()})
    )
    plataforma.registrar(Agente("a", AtendimentoCliente(), "sup"), sup)
    plataforma.registrar(Agente("f", Financeiro(), "sup"), sup)


def test_agente_sem_area_so_existe_para_a_plataforma():
    with pytest.raises(ValueError):
        Agente("x", None, "ana")  # sem área e com dono pessoa
    with pytest.raises(ValueError):
        Agente("x", Financeiro(), DONO_PLATAFORMA)  # dono plataforma com área
    with pytest.raises(ValueError):
        Agente("x", "financeiro", "ana")  # área precisa ser uma Area


def test_pessoa_nao_pode_ter_o_id_da_plataforma():
    with pytest.raises(ValueError):
        Colaborador("c", Financeiro(), id=DONO_PLATAFORMA)
    with pytest.raises(ValueError):
        AdminGlobal("a", id=DONO_PLATAFORMA)


# ---------------------------------------------------------------- C2: carregar agente do banco
def test_carregar_agente_nao_grava_evento_nem_exige_criador():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    do_banco = Agente("x", Financeiro(), "dono", id="ag-1")
    plataforma.carregar_agente(do_banco)
    assert plataforma.auditoria == []  # nenhum CRIAR falso
    plataforma.autorizar(dono, Acao.EXECUTAR, do_banco)
    assert plataforma.agentes_visiveis(dono) == [do_banco]
    assert [e.acao for e in plataforma.auditoria] == ["EXECUTAR"]


def test_carregar_agente_de_dono_ausente_do_cadastro_funciona_e_ninguem_mais_acessa():
    plataforma = Plataforma()
    estranho = plataforma.cadastrar(Colaborador("e", Financeiro(), id="estranho"))
    plataforma.carregar_agente(Agente("x", Financeiro(), "dono-que-saiu", id="ag-1"))
    assert plataforma.agentes_visiveis(estranho) == []  # privado de outra pessoa


def test_carregar_agente_recusa_id_repetido_e_tipo_errado():
    plataforma = Plataforma()
    agente = Agente("x", Financeiro(), "dono", id="ag-1")
    plataforma.carregar_agente(agente)
    plataforma.carregar_agente(agente)  # o mesmo objeto de novo não muda nada
    with pytest.raises(ValueError):
        plataforma.carregar_agente(Agente("outro", Financeiro(), "dono", id="ag-1"))
    assert plataforma._agentes["ag-1"] is agente
    with pytest.raises(TypeError):
        plataforma.carregar_agente({"id": "ag-2"})


# ---------------------------------------------------------------- I1: auditoria só autoriza
def test_plataforma_nao_tem_metodo_que_devolva_a_auditoria():
    assert not hasattr(Plataforma, "ler_auditoria")


# ---------------------------------------------------------------- I2: ciclo de vida com evento
def test_alterar_visibilidade_autoriza_edita_e_grava_um_evento():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    outro = plataforma.cadastrar(Colaborador("o", Financeiro(), id="outro"))
    agente = dono.criar_agente("x", plataforma)
    antes = len(plataforma.auditoria)
    plataforma.alterar_visibilidade(dono, agente, PUB)
    assert agente.visibilidade is PUB
    assert len(plataforma.auditoria) == antes + 1
    assert plataforma.auditoria[-1].acao == "ALTERAR_VISIBILIDADE:publico"
    assert plataforma.auditoria[-1].permitido is True
    plataforma.autorizar(outro, Acao.VER, agente)  # agora o outro enxerga
    plataforma.alterar_visibilidade(dono, agente, "privado")  # aceita o valor do banco
    assert agente.visibilidade is PRIV


def test_alterar_visibilidade_negada_nao_muda_nada():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    outro = plataforma.cadastrar(Colaborador("o", Financeiro(), id="outro"))
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.alterar_visibilidade(dono, agente, PUB)
    for intruso in (outro, admin):
        with pytest.raises(AcessoNegado):
            plataforma.alterar_visibilidade(intruso, agente, PRIV)
        assert plataforma.auditoria[-1].permitido is False
    assert agente.visibilidade is PUB
    with pytest.raises(ValueError):
        plataforma.alterar_visibilidade(dono, agente, "qualquer")


def test_supervisor_da_area_edita_visibilidade_de_agente_aberto_mas_nao_de_privado():
    plataforma = Plataforma()
    sup = plataforma.cadastrar(Supervisor("s", Financeiro(), id="sup"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    with pytest.raises(AcessoNegado):
        plataforma.alterar_visibilidade(sup, agente, PUB)  # privado: o supervisor não vê
    plataforma.alterar_visibilidade(dono, agente, CONV)
    plataforma.alterar_visibilidade(sup, agente, PUB)
    assert agente.visibilidade is PUB


def test_desativar_pelo_dono_pelo_supervisor_e_pelo_admin():
    plataforma = Plataforma()
    sup = plataforma.cadastrar(Supervisor("s", Financeiro(), id="sup"))
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    do_dono, do_supervisor, do_admin = (dono.criar_agente(f"x{i}", plataforma) for i in range(3))
    plataforma.alterar_visibilidade(dono, do_supervisor, PUB)  # o supervisor só gerencia o aberto
    plataforma.desativar(dono, do_dono)
    plataforma.desativar(sup, do_supervisor)
    plataforma.desativar(admin, do_admin)
    assert [a.ativo for a in (do_dono, do_supervisor, do_admin)] == [False, False, False]
    assert [e.acao for e in plataforma.auditoria[-3:]] == ["DESATIVAR"] * 3
    assert all(e.permitido for e in plataforma.auditoria[-3:])


def test_admin_desativa_agente_privado_que_nao_ve_pelo_id():
    # README: o Admin pode DEPRECAR até o privado, sem enxergá-lo (nem na lista, nem o conteúdo)
    plataforma = Plataforma()
    admin = plataforma.cadastrar(AdminGlobal("a", id="adm"))
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    privado = dono.criar_agente("x", plataforma)
    assert plataforma.agentes_visiveis(admin) == []
    with pytest.raises(AcessoNegado):
        plataforma.autorizar(admin, Acao.VER, privado)
    plataforma.desativar(admin, privado)
    assert privado.ativo is False


def test_desativar_negado_para_quem_so_usa_e_agente_inativo_nao_executa():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    outro = plataforma.cadastrar(Colaborador("o", Financeiro(), id="outro"))
    auditor = plataforma.cadastrar(Auditor("u", id="aud"))
    agente = dono.criar_agente("x", plataforma)
    plataforma.alterar_visibilidade(dono, agente, PUB)
    for intruso in (outro, auditor):
        with pytest.raises(AcessoNegado):
            plataforma.desativar(intruso, agente)
    assert agente.ativo is True
    plataforma.desativar(dono, agente)
    for pessoa in (dono, outro):
        with pytest.raises(AcessoNegado):
            plataforma.autorizar(pessoa, Acao.EXECUTAR, agente)


def test_mudanca_com_agente_forjado_ou_solto_e_negada():
    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    atacante = plataforma.cadastrar(Colaborador("a", Financeiro(), id="atacante"))
    real = dono.criar_agente("x", plataforma)
    forjado = Agente("x", Financeiro(), "atacante", id=real.id)
    with pytest.raises(AcessoNegado):
        plataforma.alterar_visibilidade(atacante, forjado, PUB)
    with pytest.raises(AcessoNegado):
        plataforma.desativar(atacante, forjado)
    assert real.visibilidade is PRIV and real.ativo is True


def test_gancho_que_falha_impede_a_mudanca_de_estado():
    def gancho_quebrado(evento):
        raise RuntimeError("falha")

    plataforma = Plataforma()
    dono = plataforma.cadastrar(Colaborador("d", Financeiro(), id="dono"))
    agente = dono.criar_agente("x", plataforma)
    plataforma._ao_registrar = gancho_quebrado
    with pytest.raises(AcessoNegado):
        plataforma.alterar_visibilidade(dono, agente, PUB)
    with pytest.raises(AcessoNegado):
        plataforma.desativar(dono, agente)
    assert agente.visibilidade is PRIV and agente.ativo is True  # sem rastro, sem mudança
