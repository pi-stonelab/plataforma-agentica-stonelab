"""Guardas de arquitetura baratas: quebram cedo quando alguém muda um vocabulário ou quebra uma regra.

Nada aqui roda agente nem modelo. Valores de referência: `gabaritos.py` (escritos à mão).
A varredura de LGPD nunca imprime o valor achado, só arquivo, linha e tipo.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest
from agentes.agente_atendimento import agente as motor
from agentes.agente_geral import agente as geral
from ferramentas import catalogo, governanca
from mock import regras  # noqa: UP026 (pacote da Stone simulada, não o mock do PyPI)
from mock.banco import criar_engine
from mock.gerar import recriar
from mock.modelos import Funcionario, Lojista, Time
from seguranca import permissoes
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import apoio_agente as apoio
from . import gabaritos as gab
from . import test_regressao_ataques as ataques
from .apoio_ferramentas import FUNCIONARIO_DO_CARGO, NEGADO_PELO_CATALOGO

RAIZ = Path(__file__).resolve().parents[2]
FERRAMENTAS = catalogo.carregar()
ATIVAS = sorted(nome for nome, ficha in FERRAMENTAS.items() if ficha.status == "ativa")


@pytest.fixture(autouse=True)
def mundo_limpo():
    apoio.limpar()
    yield
    apoio.limpar()


def arquivos_rastreados():
    saida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=False)
    if saida.returncode != 0:
        pytest.skip("sem git para listar os arquivos rastreados")
    return [RAIZ / linha for linha in saida.stdout.splitlines() if linha]


# ---------- ferramentas ----------


@pytest.mark.parametrize("arquivo", sorted((RAIZ / "ferramentas").glob("*/*/func.py")), ids=lambda a: a.parent.name)
def test_func_py_nao_importa_sqlalchemy_nem_mock(arquivo):
    """O banco só entra pela fachada `ferramentas/dados_sinteticos.py` (D10)."""
    proibidos = []
    for no in ast.walk(ast.parse(arquivo.read_text("utf-8"))):
        nomes = [a.name for a in no.names] if isinstance(no, ast.Import) else []
        if isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes.append(no.module)
        proibidos += [n for n in nomes if n.split(".")[0] in ("sqlalchemy", "mock")]
    assert proibidos == []


@pytest.mark.parametrize(
    "nome",
    ATIVAS,
)
def test_toda_ferramenta_ativa_tem_agents_md_preenchido(nome):
    ficha = FERRAMENTAS[nome]
    texto = (RAIZ / "ferramentas" / ficha.area / nome / "agents.md").read_text("utf-8")
    assert "[preencher" not in texto
    for secao in ("## Quando usar", "## Parâmetros", "## O que devolve", "## Para quem mantém"):
        assert secao in texto, secao
    for parametro in ficha.parametros:
        assert f"`{parametro}`" in texto, f"parâmetro {parametro} sem explicação"


@pytest.mark.parametrize("nome", sorted(FERRAMENTAS))
def test_ficha_nao_declara_parametro_reservado_e_escrita_nao_esta_ativa(nome):
    ficha = FERRAMENTAS[nome]
    assert not set(ficha.parametros) & set(gab.PARAMETROS_RESERVADOS)
    if ficha.acesso == "escrita" and nome not in governanca.ESCRITA_SEM_CONFIRMACAO:
        assert not ficha.esta_ativa()


def test_todo_nome_de_ferramenta_dos_gabaritos_existe_no_catalogo():
    nomes = set(gab.CAMINHO) | set(gab.NUNCA_EXECUTAM) | {gab.CONSULTAR_CEP, gab.SOLICITAR_AUSENTE}
    assert nomes <= set(FERRAMENTAS)
    for nome, caminho in gab.CAMINHO.items():
        assert caminho == f"{FERRAMENTAS[nome].area}/{nome}"


@pytest.mark.parametrize("nome", ATIVAS)
def test_toda_ferramenta_ativa_e_alcancada_por_algum_cargo(nome):
    alcancam = [c for c, nomes in gab.FERRAMENTAS_DO_CARGO.items() if nome in nomes]
    assert alcancam, f"{nome} não é liberada para nenhum cargo"


def test_ferramentas_ativas_sao_exatamente_as_dos_gabaritos():
    assert set(ATIVAS) == set().union(*gab.FERRAMENTAS_DO_CARGO.values())


def test_ninguem_usa_date_today_no_codigo_de_producao():
    """O "hoje" do mock é HOJE_DO_MOCK (O8, E38)."""
    achados = []
    for pasta in ("ferramentas", "mock", "agentes", "seguranca"):
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            for no in ast.walk(ast.parse(arquivo.read_text("utf-8"))):
                chamada = isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                if chamada and no.func.attr == "today":
                    achados.append(f"{arquivo.relative_to(RAIZ).as_posix()}:{no.lineno}")
    assert achados == []


# ---------- vocabulários iguais no mock, na governança e na segurança ----------


def test_areas_batem_entre_mock_governanca_e_seguranca():
    areas_dos_cargos = {r.area for r in regras.CARGOS.values() if r.area}
    assert set(regras.AREAS) == set(governanca.AREAS_USUARIO) == set(permissoes.AREAS) == areas_dos_cargos
    assert set(regras.AREAS) == {"atendimento", "financeiro"}


def test_carteiras_batem_entre_regras_e_mundo_gerado():
    engine = criar_engine("sqlite://")
    recriar(engine)
    with Session(engine) as sessao:
        dos_lojistas = set(sessao.scalars(select(Lojista.carteira)))
        dos_times = {c for c in sessao.scalars(select(Time.carteira)) if c}
    assert set(regras.CARTEIRAS) == set(regras.CARTEIRA_POR_PORTE.values()) == dos_lojistas == dos_times


def test_categorias_batem_entre_mock_governanca_e_fichas():
    assert set(governanca.CATEGORIAS_DADOS) == set(regras.CATEGORIAS_DADO) | set(
        regras.CATEGORIAS_DE_FERRAMENTAS_PLANEJADAS
    )
    for cargo, regra in regras.CARGOS.items():
        assert regra.categorias_dado <= set(regras.CATEGORIAS_DADO), cargo
    for nome, ficha in FERRAMENTAS.items():
        assert set(ficha.categorias_dados) <= set(governanca.CATEGORIAS_DADOS), nome
    for nome in ATIVAS:  # ferramenta ativa só usa os nomes finos
        assert set(FERRAMENTAS[nome].categorias_dados) <= set(regras.CATEGORIAS_DADO), nome


def test_cargos_batem_entre_gabarito_mock_diretorio_e_apoio_dos_testes():
    engine = criar_engine("sqlite://")
    recriar(engine)
    with Session(engine) as sessao:
        no_diretorio = set(sessao.scalars(select(Funcionario.cargo)))
    assert len(gab.CARGOS) == 10
    assert set(gab.CARGOS) == set(regras.CARGOS) == no_diretorio == set(FUNCIONARIO_DO_CARGO)
    assert set(gab.FERRAMENTAS_DO_CARGO) == set(gab.CARGOS)


def test_perfis_e_areas_dos_cargos_existem_na_seguranca():
    perfis_da_seguranca = {papel.__name__ for papel in permissoes.ROLES}
    assert set(regras.PERFIS) <= perfis_da_seguranca
    for cargo, regra in regras.CARGOS.items():
        assert regra.perfil_padrao in regras.PERFIS, cargo
        assert regra.nivel_ferramenta in (*governanca.NIVEIS, None), cargo
        assert regra.escopo_lojistas in regras.ESCOPOS, cargo
        sem_area = regra.area is None
        assert sem_area == (regra.perfil_padrao in ("Auditor", "AdminGlobal")), cargo
        assert sem_area == (regra.nivel_ferramenta is None) == (regra.escopo_lojistas == regras.ESCOPO_NENHUM), cargo
    assert {c for c, r in regras.CARGOS.items() if r.escopo_lojistas == regras.ESCOPO_CARTEIRAS_DO_TIME} == set(
        gab.CARGOS_QUE_VEEM_SO_A_PROPRIA_CARTEIRA
    )
    assert {c for c, r in regras.CARGOS.items() if r.janela_dias} == {"atendente_n1"}
    assert regras.CARGOS["atendente_n1"].janela_dias == gab.JANELA_DIAS_N1


def test_hoje_do_mock_e_o_do_gabarito():
    assert regras.HOJE_DO_MOCK == gab.HOJE_DO_MOCK
    assert motor.MAX_PASSOS == gab.MAX_ETAPAS_POR_TURNO and motor.MAX_REPETICOES == gab.MAX_REPETICOES_SEGUIDAS
    assert governanca.LIMITE_LINHAS == gab.LIMITE_DE_LINHAS


# ---------- todo cargo tem teste de acesso ao agente geral ----------


def nomes_vistos_pelo_cargo(usuario):
    """Nomes de ferramenta que a pessoa consegue ler pelo catálogo (índice, áreas e fichas).

    Só propriedades: o formato do texto do índice pode mudar sem quebrar este teste.
    """
    lista = geral.FERRAMENTAS_DO_AGENTE
    textos = [catalogo.ler("", usuario, lista)]
    for area in sorted({f.area for f in FERRAMENTAS.values()}):
        textos.append(catalogo.ler(area, usuario, lista))
    visiveis = {n for n in FERRAMENTAS if catalogo.ler(f"{FERRAMENTAS[n].area}/{n}", usuario, lista) != gab.MENSAGEM_CAMINHO_NAO_LIBERADO}
    return {n for n in FERRAMENTAS if any(n in texto for texto in textos)} | visiveis


def test_ha_um_caso_de_acesso_ao_agente_geral_para_cada_um_dos_10_cargos():
    assert [c for c in gab.CARGOS] == list(gab.FERRAMENTAS_DO_CARGO)
    assert len(gab.CARGOS) == 10


@pytest.mark.parametrize("cargo", gab.CARGOS)
def test_agente_geral_cada_cargo_alcanca_so_o_que_o_gabarito_diz(cargo):
    usuario = apoio.usuario_do_cargo(cargo)
    esperado = gab.FERRAMENTAS_DO_CARGO[cargo]
    assert set(catalogo.ferramentas_liberadas(usuario, geral.FERRAMENTAS_DO_AGENTE)) == esperado
    assert nomes_vistos_pelo_cargo(usuario) == esperado  # o que lê é o que pode usar, nem mais nem menos
    for nome in sorted(set(FERRAMENTAS) - esperado):
        resposta = catalogo.executar(nome, {}, usuario, geral.FERRAMENTAS_DO_AGENTE)
        assert resposta == NEGADO_PELO_CATALOGO, nome
    for nome in sorted(esperado):  # as liberadas respondem de verdade (parâmetro faltando, não bloqueio)
        resposta = catalogo.executar(nome, {}, usuario, geral.FERRAMENTAS_DO_AGENTE)
        assert resposta["tipo_erro"] != gab.TIPO_ERRO_FERRAMENTA_BLOQUEADA, nome


@pytest.mark.parametrize("cargo", gab.CARGOS)
def test_agente_geral_o_turno_de_cada_cargo_so_enxerga_o_que_o_cargo_libera(cargo):
    from . import apoio_regressao as reg

    roteiro = reg.Roteiro([reg.ler(), reg.final("ok")])
    usuario = apoio.usuario_do_cargo(cargo)
    turno = geral.rodar_turno_geral("oi", usuario, roteiro)
    assert turno.tipo == "final"
    indice = roteiro.prompts[1]
    for nome in set(FERRAMENTAS) - gab.FERRAMENTAS_DO_CARGO[cargo]:
        assert nome not in indice, f"{cargo} viu {nome} no índice"


# ---------- todo ataque da KAN-69 tem teste (executável ou skip) ----------


def test_todo_ataque_da_kan69_tem_pelo_menos_um_teste():
    prefixos = {n.split("_")[1] for n in dir(ataques) if re.match(r"test_a\d\d_", n)}
    esperados = {i.replace("-", "").lower() for i in gab.ATAQUES}
    assert esperados == prefixos
    assert len(gab.ATAQUES) == 26


# ---------- LGPD: nenhum dado pessoal real nos arquivos rastreados ----------

# Exceções conhecidas da varredura (arquivo, tipo). Vazia: nenhum arquivo rastreado tem exceção.
PENDENTES_DE_OUTRAS_ETAPAS = set()
CANDIDATO_A_CPF = re.compile(r"(?<![\d.])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d])")
CANDIDATO_A_CARTAO = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
# (?<![...]) evita casar "senha@servidor" dentro de uma URL com usuário:senha, que não é e-mail
CANDIDATO_A_EMAIL = re.compile(r"(?<![\w.+:/-])[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")


def cpf_valido(texto: str) -> bool:
    d = [int(c) for c in texto if c.isdigit()]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        if (sum(d[i] * (n + 1 - i) for i in range(n)) * 10) % 11 % 10 != d[n]:
            return False
    return True


def luhn_valido(texto: str) -> bool:
    d = [int(c) for c in texto if c.isdigit()][::-1]
    total = sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d))
    return len(d) >= 13 and total % 10 == 0


def achados_de_lgpd(texto: str) -> set[tuple[int, str]]:
    achados = set()
    for numero, linha in enumerate(texto.splitlines(), start=1):
        for casou in CANDIDATO_A_CPF.finditer(linha):
            digitos = re.sub(r"\D", "", casou.group())
            if cpf_valido(digitos) and digitos != gab.CPF_VALIDO_PERMITIDO:
                achados.add((numero, "cpf válido"))
        for casou in CANDIDATO_A_CARTAO.finditer(linha):
            digitos = re.sub(r"\D", "", casou.group())
            if luhn_valido(digitos) and digitos != gab.CARTAO_DE_TESTE_PERMITIDO:
                achados.add((numero, "cartão válido"))
        for casou in CANDIDATO_A_EMAIL.finditer(linha):
            if not casou.group(1).endswith(gab.DOMINIOS_DE_EMAIL_PERMITIDOS):
                achados.add((numero, "e-mail fora de .example/.test"))
    return achados


def varrer_repositorio():
    achados = {}
    for arquivo in arquivos_rastreados():
        try:
            texto = arquivo.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binário
        for numero, tipo in sorted(achados_de_lgpd(texto)):
            achados.setdefault((arquivo.relative_to(RAIZ).as_posix(), tipo), []).append(numero)
    return achados


def cpf_valido_de(nove_digitos: str) -> str:
    """CPF com dígitos verificadores certos, montado na hora: o repositório não guarda nenhum."""
    d = [int(c) for c in nove_digitos]
    for n in (9, 10):
        d.append((sum(d[i] * (n + 1 - i) for i in range(n)) * 10) % 11 % 10)
    return "".join(map(str, d))


def test_o_detector_de_lgpd_acha_cada_tipo_e_respeita_o_que_e_permitido():
    cpf = cpf_valido_de("111444777")  # valor montado em tempo de teste, nunca escrito no arquivo
    assert cpf_valido(cpf) and cpf != gab.CPF_VALIDO_PERMITIDO
    formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    assert achados_de_lgpd(f"cpf {formatado}") == {(1, "cpf válido")}
    assert achados_de_lgpd(f"cpf {cpf}") == {(1, "cpf válido")}
    assert achados_de_lgpd("cartão " + " ".join(["4242"] * 4)) == {(1, "cartão válido")}
    assert achados_de_lgpd("fulano@" + "gmail.com") == {(1, "e-mail fora de .example/.test")}
    permitidos = (
        "123.456.789-09",
        "4111 1111 1111 1111",
        "4111111111111111",
        "a@b.example",
        "a@b.test",
        "111.444.777-00",  # dígito verificador errado de propósito
    )
    for texto in permitidos:
        assert achados_de_lgpd(texto) == set(), texto


def test_a_marca_armadilha_permitida_nao_desliga_a_varredura_da_linha():
    """BAIXO-9 da auditoria C: a marca antiga pulava a linha inteira; agora não pula nada."""
    cpf = cpf_valido_de("111444777")
    linha = f"4111 1111 1111 1111 e {cpf} e fulano@" + "gmail.com  # armadilha-permitida"
    assert achados_de_lgpd(linha) == {(1, "cpf válido"), (1, "e-mail fora de .example/.test")}
    assert achados_de_lgpd("4111 1111 1111 1111 e 111.444.777-00  # armadilha-permitida") == set()


def test_nenhum_arquivo_rastreado_tem_cpf_cartao_ou_email_real():
    novos = {chave: linhas for chave, linhas in varrer_repositorio().items() if chave not in PENDENTES_DE_OUTRAS_ETAPAS}
    assert novos == {}, "arquivo, tipo e linhas (o valor não é mostrado)"


def test_repositorio_limpo_sem_nenhuma_excecao_pendente():
    assert varrer_repositorio() == {}
