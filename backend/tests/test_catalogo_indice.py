"""Índice do catálogo (P1 da crítica B): já lista as ferramentas liberadas, com a primeira frase da ficha."""

import re

import pytest
from ferramentas import catalogo
from mock.regras import CARGOS

from .apoio_agente import usuario_do_cargo
from .apoio_ferramentas import CARGOS_COM_FERRAMENTA, CARGOS_TRANSVERSAIS

TODAS = tuple(catalogo.nomes())
LINHA = re.compile(r"^- `(?P<caminho>[a-z_]+/[a-z_]+)`: (?P<frase>.+)$", re.MULTILINE)
SECAO = "## Ferramentas liberadas para você"


def ferramentas_do_indice(texto):
    corpo = texto.split(SECAO)[1].split("\n## ")[0]
    return {m["caminho"]: m["frase"] for m in LINHA.finditer(corpo)}


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_indice_lista_exatamente_as_ferramentas_liberadas_com_a_primeira_frase(cargo):
    usuario = usuario_do_cargo(cargo)
    liberadas = catalogo.ferramentas_liberadas(usuario, TODAS)
    listadas = ferramentas_do_indice(catalogo.ler("", usuario, TODAS))
    esperado = {f"{catalogo.carregar()[n].area}/{n}" for n in liberadas}
    assert set(listadas) == esperado
    assert all(frase.endswith((".", ")")) and len(frase) > 20 for frase in listadas.values())


@pytest.mark.parametrize("cargo", CARGOS_TRANSVERSAIS)
def test_cargo_sem_ferramenta_nao_ve_a_secao_nem_nome_de_ferramenta(cargo):
    texto = catalogo.ler("", usuario_do_cargo(cargo), TODAS)
    assert SECAO not in texto
    assert not any(nome in texto for nome in TODAS)


def test_ferramenta_de_agente_sem_ela_nao_aparece_no_indice():
    usuario = usuario_do_cargo("atendente_n1")
    texto = catalogo.ler("", usuario, ("consultar_cliente",))
    assert set(ferramentas_do_indice(texto)) == {"atendimento/consultar_cliente"}


def test_do_indice_vai_direto_para_a_ficha_e_a_area_continua_disponivel():
    usuario = usuario_do_cargo("atendente_n1")
    ficha = catalogo.ler("atendimento/consultar_cliente", usuario, TODAS)
    assert "id_cliente" in ficha and "Para quem mantém" not in ficha
    area = catalogo.ler("atendimento", usuario, TODAS)
    assert "`consultar_cliente`" in area


# O índice vai inteiro para o modelo em todo passo. O agente geral (TODAS) lista tudo o que o cargo pode usar, então
# o índice cresce com o catálogo; o controle é por ferramenta: frase curta e um custo fixo por linha.
TAMANHO_MAXIMO_DA_FRASE = 160
TAMANHO_FIXO_DO_INDICE = 2000  # cabeçalho, áreas, tipos de erro e regras gerais
TAMANHO_POR_FERRAMENTA = 170  # "- `area/nome`: " + a frase


@pytest.mark.parametrize("cargo", CARGOS)
def test_indice_nao_cresce_sem_controle(cargo):
    texto = catalogo.ler("", usuario_do_cargo(cargo), TODAS)
    listadas = ferramentas_do_indice(texto) if SECAO in texto else {}
    longas = {caminho: len(frase) for caminho, frase in listadas.items() if len(frase) > TAMANHO_MAXIMO_DA_FRASE}
    assert longas == {}, "Encurte a primeira frase do agents.md destas fichas."
    assert len(texto) <= TAMANHO_FIXO_DO_INDICE + TAMANHO_POR_FERRAMENTA * len(listadas)
