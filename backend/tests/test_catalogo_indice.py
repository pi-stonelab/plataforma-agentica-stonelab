"""Índice do catálogo (P1 da crítica B): já lista as ferramentas liberadas, com a primeira frase da ficha."""

import re

import pytest
from agentes.agente_atendimento import agente as agente_atendimento
from agentes.agente_atendimento.agente import MAX_CHARS_MD, Atendimento
from agentes.agente_geral import agente as agente_geral
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
    assert all(len(frase) > 20 for frase in listadas.values())


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


# O índice vai inteiro para o modelo em todo passo e o motor corta cada leitura em MAX_CHARS_MD (6000). O catálogo
# encurta as frases para o texto caber (`catalogo.LIMITE_DO_INDICE`): a cauda do índice não pode sumir.
TAMANHO_MAXIMO_DA_FRASE = 160


def _tudo_ligado(monkeypatch):
    """Pior caso para o tamanho: todas as integrações ligadas no .env, então nenhuma ferramenta some do índice."""
    monkeypatch.setattr(catalogo, "_integracao_desligada", lambda ferramenta: None)


@pytest.mark.parametrize("cargo", CARGOS)
def test_indice_cabe_no_corte_do_motor_e_lista_tudo_o_que_o_cargo_alcanca(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    usuario = usuario_do_cargo(cargo)
    texto = catalogo.ler("", usuario, TODAS)
    assert len(texto) <= catalogo.LIMITE_DO_INDICE < MAX_CHARS_MD
    liberadas = catalogo.ferramentas_liberadas(usuario, TODAS)
    listadas = ferramentas_do_indice(texto) if SECAO in texto else {}
    assert set(listadas) == {f"{catalogo.carregar()[n].area}/{n}" for n in liberadas}
    assert all(len(frase) <= TAMANHO_MAXIMO_DA_FRASE for frase in listadas.values())
    if liberadas:  # a cauda do texto (erros e regras gerais) continua lá
        assert "Ferramenta que altera algo só age depois de confirmação" in texto


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_motor_entrega_o_indice_inteiro_ao_modelo(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    atendimento = Atendimento(usuario_do_cargo(cargo), TODAS, "exec-1", "agente_geral")
    texto, _ = atendimento.ler("")
    assert texto == catalogo.ler("", atendimento.usuario, TODAS)  # o corte do motor não tirou nada
    assert texto.rstrip().endswith("Ferramenta que altera algo só age depois de confirmação em duas etapas.")


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_indice_nao_lista_o_que_o_cargo_nao_alcanca(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    usuario = usuario_do_cargo(cargo)
    liberadas = set(catalogo.ferramentas_liberadas(usuario, TODAS))
    texto = catalogo.ler("", usuario, TODAS)
    for nome in set(TODAS) - liberadas:
        assert f"/{nome}`" not in texto, nome
    areas_liberadas = {catalogo.carregar()[n].area for n in liberadas}
    for area in {f.area for f in catalogo.carregar().values()} - areas_liberadas:
        assert f"- `{area}`" not in texto and f"- `{area}/" not in texto, area


@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_leitura_de_cada_area_cabe_no_corte_do_motor(cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    usuario = usuario_do_cargo(cargo)
    areas = {catalogo.carregar()[n].area for n in catalogo.ferramentas_liberadas(usuario, TODAS)}
    for area in areas:
        assert len(catalogo.ler(area, usuario, TODAS)) <= MAX_CHARS_MD, area


def test_catalogo_inteiro_so_com_os_nomes_ainda_cabe_no_corte_do_motor(monkeypatch):
    """Folga para o catálogo crescer: com todas as ferramentas de uma só pessoa e sem frase nenhuma."""
    _tudo_ligado(monkeypatch)
    ferramentas, liberadas = catalogo.carregar(), catalogo.nomes()
    areas = sorted({ferramentas[n].area for n in liberadas})
    texto = catalogo._indice(ferramentas, liberadas, areas)
    assert len(texto) <= catalogo.LIMITE_DO_INDICE


@pytest.mark.parametrize("agente", [agente_geral, agente_atendimento])
@pytest.mark.parametrize("cargo", CARGOS_COM_FERRAMENTA)
def test_indice_dos_dois_agentes_so_lista_as_ferramentas_do_agente_liberadas_ao_cargo(agente, cargo, monkeypatch):
    _tudo_ligado(monkeypatch)
    usuario = usuario_do_cargo(cargo)
    do_agente = agente.FERRAMENTAS_DO_AGENTE
    texto = catalogo.ler("", usuario, do_agente)
    esperado = set(catalogo.ferramentas_liberadas(usuario, do_agente))
    assert esperado <= set(do_agente)
    assert {c.split("/")[1] for c in ferramentas_do_indice(texto)} == esperado
    assert len(texto) <= MAX_CHARS_MD


def test_poucas_ferramentas_mantem_a_frase_inteira_da_ficha():
    usuario = usuario_do_cargo("atendente_n1")
    listadas = ferramentas_do_indice(catalogo.ler("", usuario, ("consultar_cliente", "buscar_clientes")))
    assert listadas and not any(frase.endswith("…") for frase in listadas.values())


def test_com_muitas_ferramentas_a_frase_vem_cortada_na_palavra_inteira(monkeypatch):
    _tudo_ligado(monkeypatch)
    listadas = ferramentas_do_indice(catalogo.ler("", usuario_do_cargo("supervisor_atendimento"), TODAS))
    cortadas = [frase for frase in listadas.values() if frase.endswith("…")]
    assert cortadas and all(" " not in frase[-2:] and not frase[:-1].endswith((" ", ",", ";", ":")) for frase in cortadas)


def test_frase_curta_e_limite_das_frases():
    assert catalogo._frase_curta("Mostra as vendas.", 20) == "Mostra as vendas."
    assert catalogo._frase_curta("Mostra as vendas de um lojista.", 20) == "Mostra as vendas…"
    frases = ["a" * 100, "b" * 20, "c" * 100]
    assert catalogo._limite_das_frases(frases, 220) == catalogo.FRASE_MAXIMA  # cabem inteiras
    assert catalogo._limite_das_frases(frases, 140) == 60  # as curtas cedem espaço às longas
    assert catalogo._limite_das_frases(frases, 20) == 0  # nem o mínimo cabe: só os nomes
