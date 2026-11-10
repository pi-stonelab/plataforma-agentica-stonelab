import contextlib
import io
import json
import unittest

from ferramentas import base, catalogo, dados_sinteticos, governanca
from testes import apoio

AGENTE, MENSAGEM = apoio.AGENTE_COMPLETO, catalogo.MENSAGEM_INDISPONIVEL
N1, N2, ND = apoio.n1_atendimento, apoio.n2_financeiro, apoio.n1_dados
MARCADORES = ("[aqui conectamos", "[preencher", "Para quem mantém", "Situação:")
MALICIOSOS = [
    "..",
    "../",
    "../..",
    "/etc/passwd",
    "/",
    ".",
    "financeiro/..",
    "financeiro/../../",
    "../ferramentas/agents.md",
    "agents.md",
    "atendimento/agents.md",
    "consultar_cliente/agents.md",
    "integracoes",
    "integracoes/crm",
    "atendimento/consultar_cliente/agents.md",
    "integracoes/crm/README.md",
    "nao_existe",
    "atendimento/../financeiro/calcular_multa_atraso",
    "financeiro/calcular_multa_atraso/func.py",
    "C:\\Windows\\win.ini",
    "..\\..\\x",
    "atendimento\\consultar_cliente",
] + ["consultar_cliente\x00"]
NEGADO = base.resposta(
    "erro", mensagem="Ferramenta não encontrada.", tipo_erro="ferramenta_inexistente"
)
CLIENTE = {"id_cliente": "CLI-0001"}
SEM_ACESSO = ("calcular_multa_atraso",)


def ler(caminho, usuario=None, agente=AGENTE):
    return catalogo.ler(caminho, usuario or N1(), agente)


def executar(nome, argumentos, usuario=None, agente=AGENTE):
    return catalogo.executar(nome, argumentos, usuario or N1(), agente)


class TestFerramentasLiberadas(unittest.TestCase):
    def test_duas_camadas_e_ordem(self):
        liberadas = catalogo.ferramentas_liberadas
        self.assertEqual(liberadas(N1(), AGENTE), sorted(AGENTE))
        self.assertEqual(
            liberadas(ND(), AGENTE),
            sorted(set(AGENTE) - {"consultar_cliente", "consultar_transacoes_cliente"}),
        )
        self.assertEqual(liberadas(N2(), ("consultar_cliente",)), ["consultar_cliente"])
        self.assertEqual(liberadas(ND(), ("consultar_cliente",)), [])

    def test_inativa_e_entradas_invalidas_liberam_nada(self):
        liberadas = catalogo.ferramentas_liberadas
        self.assertEqual(liberadas(N2(), AGENTE + (apoio.uma_inativa(),)), sorted(AGENTE))
        for usuario, agente in ((N2(), ()), (N2(), None), (None, AGENTE), (object(), AGENTE)):
            self.assertEqual(liberadas(usuario, agente), [])

    def test_carregar_devolve_as_mesmas_instancias(self):
        self.assertIs(
            catalogo.carregar()["consultar_cliente"], catalogo.carregar()["consultar_cliente"]
        )


class TestLer(unittest.TestCase):
    def test_raiz_e_area_listam_so_o_liberado(self):
        raiz = ler("")
        for area in ["atendimento", "financeiro", "consultas_publicas", "plataforma"]:
            self.assertIn(f"- `{area}`:", raiz)
        for area in [
            "comunicacao",
            "dados_e_indicadores",
            "chamados_internos",
            "documentos_e_agenda",
        ]:
            self.assertNotIn(f"`{area}`", raiz)
        self.assertTrue(
            all(x.split(":", 1)[1].strip() for x in raiz.splitlines() if x[:3] == "- `")
        )
        area = ler("financeiro")
        self.assertIn("- `calcular_multa_atraso`:", area)
        self.assertNotIn("calcular_parcelas", area)

    def test_ferramenta_com_e_sem_area(self):
        self.assertEqual(ler("financeiro/calcular_multa_atraso"), ler("calcular_multa_atraso"))
        self.assertIn("valor_fatura", ler("calcular_multa_atraso"))
        self.assertEqual(ler("atendimento/calcular_multa_atraso"), MENSAGEM)

    def test_texto_sem_marcador_nem_parte_de_quem_mantem(self):
        for caminho in [
            "",
            "atendimento",
            "financeiro",
            "consultas_publicas",
            "plataforma",
            *AGENTE,
        ]:
            texto = ler(caminho, N2())
            self.assertNotEqual(texto, MENSAGEM, caminho)
            for marcador in MARCADORES:
                self.assertNotIn(marcador, texto, caminho)

    def test_caminhos_maliciosos_dao_a_mensagem_fixa(self):
        for usuario in (N1(), N2()):
            for caminho in MALICIOSOS:
                self.assertEqual(ler(caminho, usuario), MENSAGEM, caminho)

    def test_bloqueada_inativa_e_inexistente_respondem_igual(self):
        inativa = apoio.uma_inativa()
        respostas = [ler("consultar_cliente", agente=SEM_ACESSO), ler("consultar_cliente", ND())]
        respostas += [ler("consultar_cliente", ND(), ()), ler(inativa, N2(), (inativa,))]
        respostas += [ler("atendimento", ND()), ler("ferramenta_que_nao_existe")]
        self.assertEqual(set(respostas), {MENSAGEM})

    def test_entradas_estranhas_nunca_levantam(self):
        casos = [(None, N1(), AGENTE), (123, N1(), ()), ([], N1(), ()), ({}, N1(), ())]
        casos += [("", None, ()), ("consultar_cliente", object(), None), ("", N1(), 5)]
        for caminho, usuario, agente in casos:
            self.assertIsInstance(catalogo.ler(caminho, usuario, agente), str)


class TestExecutar(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_camadas_inativa_e_inexistente_respondem_igual_e_nao_rodam(self):
        inativa = apoio.uma_inativa()
        pedido = {"nome_sugerido": "nova_ferramenta", "descricao": "d"}
        respostas = [executar("consultar_cliente", CLIENTE, agente=SEM_ACESSO)]
        respostas += [executar("consultar_cliente", CLIENTE, ND()), executar("nao_existe", {})]
        respostas += [executar("consultar_cliente", CLIENTE, ND(), ())]
        respostas += [executar(inativa, {}, N2(), (inativa,))]
        respostas += [executar("solicitar_ferramenta_ausente", pedido, agente=())]
        self.assertTrue(all(r == NEGADO for r in respostas))
        self.assertEqual(len(apoio.pedidos()), 0)

    def test_registro_guarda_a_camada_real_e_o_nome_do_catalogo(self):
        inativa = apoio.uma_inativa()
        executar("consultar_cliente", CLIENTE, agente=SEM_ACESSO)
        executar("consultar_cliente", CLIENTE, ND())
        executar(inativa, {}, N2(), (inativa,))
        executar("../../etc/passwd", {})
        registros = governanca.REGISTROS
        self.assertEqual(
            [r["camada_bloqueio"] for r in registros],
            ["agente", "usuario", "inativa", "desconhecida"],
        )
        nomes = ["consultar_cliente", "consultar_cliente", inativa, "inexistente"]
        self.assertEqual([r["ferramenta"] for r in registros], nomes)
        self.assertNotIn("passwd", json.dumps(registros))

    def test_parametro_reservado_e_escalada_de_acesso_nao_funcionam(self):
        for reservado in governanca.PARAMETROS_RESERVADOS:
            argumentos = {"valor_fatura": 100, "dias_atraso": 1, reservado: "N2"}
            self.assertEqual(
                executar("calcular_multa_atraso", argumentos)["tipo_erro"], "parametro_invalido"
            )
        escalada = dict(CLIENTE, nivel="N2", area="atendimento", usuario="USR-0003")
        self.assertEqual(executar("consultar_cliente", escalada, ND()), NEGADO)
        extra = dict(CLIENTE, ferramentas_do_agente=["consultar_cliente"])
        self.assertEqual(executar("consultar_cliente", extra, agente=SEM_ACESSO), NEGADO)
        carteira = {"id_cliente": "CLI-0002", "carteira": ["CLI-0002"]}
        self.assertEqual(executar("consultar_cliente", carteira)["tipo_erro"], "parametro_invalido")

    def test_entradas_estranhas_nunca_levantam_e_mantem_a_forma(self):
        casos = [
            (None, {}, N1(), ()),
            ([], {}, N1(), ()),
            ({}, {}, N1(), ()),
            (5, None, None, None),
        ]
        casos += [("consultar_cliente", texto, N1(), AGENTE) for texto in (None, "texto", ["x"])]
        casos += [("consultar_cliente", CLIENTE, outro, AGENTE) for outro in (None, object())]
        casos += [("consultar_cliente", CLIENTE, N1(), None)]
        for nome, argumentos, usuario, agente in casos:
            apoio.confere_forma(self, catalogo.executar(nome, argumentos, usuario, agente))

    def test_contexto_invalido_nao_derruba_e_valido_vai_para_o_registro(self):
        for contexto in ("texto", 5, [], {"passo": object()}):
            resposta = catalogo.executar("consultar_cliente", CLIENTE, N1(), AGENTE, contexto)
            apoio.confere_forma(self, resposta)
        contexto = {"execucao_id": "EXE-7", "passo": 3, "agente_id": "AGE-2"}
        catalogo.executar("consultar_cliente", CLIENTE, N1(), AGENTE, contexto)
        self.assertEqual(governanca.REGISTROS[-1]["execucao_id"], "EXE-7")


class TestRegistroSemConteudo(unittest.TestCase):
    def test_nenhum_valor_enviado_ou_devolvido_aparece_no_registro(self):
        apoio.limpar()
        pedido = {"nome_sugerido": "nome_unico_9f3", "descricao": "texto-unico-9f3"}
        executar("consultar_cliente", CLIENTE, N2())
        executar("consultar_endereco_cep", {"cep": "01310-100"}, N2())
        executar("solicitar_ferramenta_ausente", pedido, N2())
        executar("consultar_transacoes_cliente", {"id_cliente": "CLI-0002"}, N2())
        executar("calcular_multa_atraso", {"valor_fatura": 4321.55, "dias_atraso": 17}, N2())
        texto = json.dumps(governanca.REGISTROS, ensure_ascii=False)
        nome_loja = dados_sinteticos.buscar_cliente("CLI-0001")["nome_fantasia"]
        for valor in [
            "CLI-000",
            "01310",
            "nome_unico_9f3",
            "texto-unico-9f3",
            "4321",
            "Paulista",
            nome_loja,
        ]:
            self.assertNotIn(valor, texto)
        self.assertEqual(len(governanca.REGISTROS), 5)
        self.assertTrue(
            all(set(r) == set(governanca.CAMPOS_REGISTRO) for r in governanca.REGISTROS)
        )

    def test_nada_vai_para_o_terminal(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            for caminho in ("", "financeiro", "../x", "consultar_cliente"):
                ler(caminho)
            executar("consultar_cliente", CLIENTE)
            catalogo.executar("nao_existe", {}, None, None)
        self.assertEqual(saida.getvalue(), "")
