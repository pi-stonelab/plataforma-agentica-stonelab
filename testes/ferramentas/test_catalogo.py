import ferramentas
from ferramentas import catalogo
from ferramentas.base import validar_ficha
from testes.ferramentas.apoio import (
    FerramentaComIntegracao,
    FerramentaSomar,
    TesteComEstadoLimpo,
    UsuarioDeTeste,
)


class FerramentaFinanceira(FerramentaSomar):
    nome = "somar_para_financeiro"
    areas_permitidas = ("financeiro",)


class FerramentaDesativada(FerramentaSomar):
    nome = "somar_desativada"
    status = "inativa"


class TestesDoCadastro(TesteComEstadoLimpo):
    def test_cadastra_ferramenta_valida(self):
        catalogo.registrar_ferramenta(FerramentaSomar())
        self.assertIn("somar_numeros", catalogo.CATALOGO)

    def test_ficha_invalida_nao_entra(self):
        ferramenta = FerramentaSomar()
        ferramenta.tipo_acesso = "apagar"
        with self.assertRaises(ValueError):
            catalogo.registrar_ferramenta(ferramenta)
        self.assertEqual(catalogo.CATALOGO, {})

    def test_nome_repetido_nao_entra(self):
        catalogo.registrar_ferramenta(FerramentaSomar())
        with self.assertRaises(ValueError):
            catalogo.registrar_ferramenta(FerramentaSomar())

    def test_so_aceita_ferramenta(self):
        with self.assertRaises(TypeError):
            catalogo.registrar_ferramenta("somar_numeros")

    def test_toda_ferramenta_do_catalogo_tem_ficha_completa(self):
        for nome, ferramenta in catalogo.CATALOGO.items():
            with self.subTest(nome):
                self.assertEqual(validar_ficha(ferramenta), [])


class TestesDasFuncoesDoContrato(TesteComEstadoLimpo):
    def setUp(self):
        super().setUp()
        catalogo.registrar_ferramenta(FerramentaSomar())
        catalogo.registrar_ferramenta(FerramentaFinanceira())
        catalogo.registrar_ferramenta(FerramentaDesativada())

    def test_as_quatro_funcoes_estao_na_porta_do_pacote(self):
        for nome in ("listar_para_agente", "executar", "listar_fichas", "estado_integracoes"):
            self.assertTrue(callable(getattr(ferramentas, nome)))

    def test_agente_so_ve_o_que_o_usuario_pode_usar(self):
        nomes = [item["nome"] for item in catalogo.listar_para_agente(self.usuario)]
        self.assertEqual(nomes, ["somar_numeros"])
        nomes = [item["nome"] for item in catalogo.listar_para_agente(UsuarioDeTeste(area="financeiro"))]
        self.assertEqual(nomes, ["somar_para_financeiro"])

    def test_usuario_sem_permissao_em_nada_recebe_lista_vazia(self):
        self.assertEqual(catalogo.listar_para_agente(UsuarioDeTeste(nivel="N9")), [])
        self.assertEqual(catalogo.listar_para_agente(None), [])

    def test_fichas_mostram_liberadas_completas_e_bloqueadas_resumidas(self):
        fichas = {ficha["nome"]: ficha for ficha in catalogo.listar_fichas(self.usuario)}
        self.assertEqual(set(fichas), {"somar_numeros", "somar_para_financeiro"})
        self.assertTrue(fichas["somar_numeros"]["liberada_para_voce"])
        self.assertIn("parametros", fichas["somar_numeros"])
        self.assertFalse(fichas["somar_para_financeiro"]["liberada_para_voce"])
        self.assertNotIn("parametros", fichas["somar_para_financeiro"])

    def test_executar_roda_a_ferramenta(self):
        retorno = catalogo.executar("somar_numeros", {"a": 1, "b": 2}, self.usuario)
        self.assertEqual(retorno["dados"], {"soma": 3})

    def test_executar_ferramenta_inexistente(self):
        retorno = catalogo.executar("nao_existe", {}, self.usuario)
        self.assertEqual(retorno["tipo_erro"], "ferramenta_nao_encontrada")

    def test_executar_com_nome_que_nao_e_texto(self):
        for nome in (None, 5, ["somar_numeros"], {"a": 1}):
            with self.subTest(nome):
                retorno = catalogo.executar(nome, {}, self.usuario)
                self.assertEqual(retorno["tipo_erro"], "ferramenta_nao_encontrada")

    def test_executar_ferramenta_de_outra_area_nega(self):
        retorno = catalogo.executar("somar_para_financeiro", {"a": 1, "b": 2}, self.usuario)
        self.assertEqual(retorno["tipo_erro"], "permissao_negada")

    def test_contexto_chega_ao_registro(self):
        contexto = {"execucao_id": "ex_9", "passo": 3, "agente_id": "ag_7"}
        catalogo.executar("somar_numeros", {"a": 1, "b": 2}, self.usuario, contexto)
        registro = self.registros[-1]
        self.assertEqual((registro["execucao_id"], registro["passo"], registro["agente_id"]), ("ex_9", "3", "ag_7"))


class TestesDoEstadoDasIntegracoes(TesteComEstadoLimpo):
    def test_sem_integracoes_a_lista_e_vazia(self):
        self.assertEqual(catalogo.estado_integracoes(), [])

    def test_estado_junta_ficha_saude_pausa_e_quantas_ferramentas_usam(self):
        self.cadastrar_integracao_de_teste()
        catalogo.registrar_ferramenta(FerramentaComIntegracao())
        estados = catalogo.estado_integracoes()
        self.assertEqual(len(estados), 1)
        estado = estados[0]
        self.assertEqual(estado["nome"], "sistema_de_teste")
        self.assertEqual(estado["estado"], "operando")
        self.assertFalse(estado["pausada"])
        self.assertEqual(estado["ferramentas"], 1)
