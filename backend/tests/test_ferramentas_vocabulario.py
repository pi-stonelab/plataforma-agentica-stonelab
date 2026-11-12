"""Uma lista só por conceito: governança, mock e segurança não podem divergir (crítica I4)."""

from ferramentas import catalogo, governanca
from mock.consultas import LIMITE_MAXIMO
from mock.regras import AREAS, CARGOS, CATEGORIAS_DADO, NIVEIS_FERRAMENTA
from seguranca.permissoes import AREAS as AREAS_DA_SEGURANCA
from seguranca.permissoes import ROLES


def test_listas_da_governanca_vem_do_mock():
    assert governanca.AREAS_USUARIO == AREAS == ("atendimento", "financeiro")
    assert governanca.NIVEIS == NIVEIS_FERRAMENTA
    assert governanca.LIMITE_LINHAS == LIMITE_MAXIMO == 50
    assert set(CATEGORIAS_DADO) <= set(governanca.CATEGORIAS_DADOS)


def test_ficha_usa_categoria_conhecida_e_as_ativas_usam_so_as_do_mock():
    for nome, ferramenta in catalogo.carregar().items():
        assert set(ferramenta.categorias_dados) <= set(governanca.CATEGORIAS_DADOS), nome
        if ferramenta.status == "ativa":
            assert set(ferramenta.categorias_dados) <= set(CATEGORIAS_DADO), nome
        assert set(ferramenta.areas_permitidas) <= {*governanca.AREAS_USUARIO, "todas"}, nome


def test_nenhum_cargo_permite_categoria_que_nao_existe():
    for regra in CARGOS.values():
        assert regra.categorias_dado <= set(governanca.CATEGORIAS_DADOS), regra.cargo


def test_areas_do_mock_e_da_seguranca_sao_as_mesmas():
    assert set(AREAS_DA_SEGURANCA) == set(AREAS)


def test_perfil_padrao_de_cada_cargo_existe_na_seguranca():
    perfis = {classe.__name__ for classe in ROLES}
    faltam = {r.perfil_padrao for r in CARGOS.values()} - perfis
    assert not faltam, faltam


def test_nenhuma_ficha_aceita_parametro_com_nome_reservado():
    for nome, ferramenta in catalogo.carregar().items():
        assert not set(ferramenta.parametros) & set(governanca.PARAMETROS_RESERVADOS), nome
