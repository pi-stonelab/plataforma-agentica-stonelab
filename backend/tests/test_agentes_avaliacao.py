"""A avaliação de uso de ferramentas (agentes/avaliacao.py), com modelos roteirizados."""

import json
import unittest
from unittest import mock

from agentes import avaliacao, terminal
from agentes.agente_atendimento import agente as motor
from ferramentas import diretorio

from . import apoio_agente as apoio
from .apoio_agente import modelo_roteirizado
from .apoio_ferramentas import usuario_do_diretorio

AREA = {
    "consultar_cliente": "atendimento",
    "consultar_transacoes_cliente": "financeiro",
    "calcular_multa_atraso": "financeiro",
    "consultar_endereco_cep": "consultas_publicas",
}
USO = {
    "consultar_cliente": 'USAR: consultar_cliente | {"id_cliente": "M00001"}',
    "consultar_transacoes_cliente": 'USAR: consultar_transacoes_cliente | {"id_cliente": "M00001"}',
    "calcular_multa_atraso": 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}',
    "consultar_endereco_cep": 'USAR: consultar_endereco_cep | {"cep": "01310-100"}',
}
RESPOSTA = "FINAL: Padaria Pão da Vila, T0000625, R$ 1.030,00, Avenida Paulista."


def buscar_usuario(id_funcionario):
    return usuario_do_diretorio(apoio.mundo(), id_funcionario)


def roteiro_certo(cenario):
    """O que um modelo que acerta diria: ler o índice, ler cada ficha, usar, responder."""
    if cenario.negadas:
        return ["LER:", "LER: atendimento/consultar_cliente", 'USAR: consultar_cliente | {"id_cliente": "M00002"}',
                "FINAL: não tenho acesso a esse lojista."]
    fichas = [f"LER: {AREA[nome]}/{nome}" for nome in cenario.esperadas]
    usos = [USO[nome] for nome in cenario.esperadas]
    return ["LER:", *fichas, *usos, RESPOSTA]


def avaliar(cenario, linhas):
    return avaliacao.avaliar_cenario(cenario, modelo_roteirizado(linhas), buscar_usuario)


def cenario(nome):
    return next(c for c in avaliacao.CENARIOS if c.nome == nome)


class TestCenarios(unittest.TestCase):
    def test_nomes_unicos_e_ferramentas_do_agente(self):
        nomes = [c.nome for c in avaliacao.CENARIOS]
        self.assertEqual(len(nomes), len(set(nomes)))
        for c in avaliacao.CENARIOS:
            with self.subTest(c.nome):
                self.assertLessEqual(set(c.esperadas) | set(c.negadas), set(motor.FERRAMENTAS_DO_AGENTE))
                self.assertTrue(c.esperadas or c.negadas)

    def test_as_perguntas_dos_cenarios_nao_citam_nome_de_ferramenta(self):
        for c in avaliacao.CENARIOS:
            with self.subTest(c.nome):
                for nome in AREA:
                    self.assertNotIn(nome, c.pergunta)


class TestAvaliacao(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_modelo_que_acerta_aprova_todos_os_cenarios(self):
        for c in avaliacao.CENARIOS:
            with self.subTest(c.nome):
                linhas = roteiro_certo(c)
                r = avaliar(c, linhas)
                self.assertTrue(r.aprovado, r)
                self.assertEqual(r.chamadas_ao_modelo, len(linhas))
                self.assertEqual(r.recusas_do_agente, 0)
                self.assertEqual(set(r.executadas), set(c.esperadas))

    def test_ferramenta_errada_reprova(self):
        c = cenario("cadastro")
        r = avaliar(c, ["LER:", "LER: consultas_publicas/consultar_endereco_cep", USO["consultar_endereco_cep"], RESPOSTA])
        self.assertEqual(r.executadas, ("consultar_endereco_cep",))
        self.assertFalse(r.ferramentas_certas)
        self.assertFalse(r.aprovado)

    def test_faltar_uma_das_ferramentas_reprova(self):
        c = cenario("cadastro_e_transacoes")
        r = avaliar(c, ["LER:", "LER: atendimento/consultar_cliente", USO["consultar_cliente"], RESPOSTA])
        self.assertEqual(r.executadas, ("consultar_cliente",))
        self.assertFalse(r.ferramentas_certas)

    def test_ferramenta_a_mais_tambem_reprova(self):
        c = cenario("cadastro")
        extra = roteiro_certo(cenario("cadastro_e_transacoes"))
        r = avaliar(c, extra)
        self.assertFalse(r.ferramentas_certas)

    def test_ferramentas_certas_com_resposta_sem_o_dado_reprova(self):
        c = cenario("cadastro")
        linhas = roteiro_certo(c)[:-1] + ["FINAL: não sei."]
        r = avaliar(c, linhas)
        self.assertTrue(r.ferramentas_certas)
        self.assertFalse(r.resposta_certa)
        self.assertFalse(r.aprovado)

    def test_terminar_em_limite_reprova_mesmo_com_ferramentas_certas(self):
        c = cenario("cadastro")
        linhas = ["LER:", "LER: atendimento/consultar_cliente", USO["consultar_cliente"]]
        linhas += ["LER: financeiro"] * motor.MAX_PASSOS
        r = avaliar(c, linhas)
        self.assertEqual((r.tipo, r.motivo), ("limite", "max_passos"))
        self.assertTrue(r.ferramentas_certas)
        self.assertFalse(r.aprovado)

    def test_usar_sem_ler_conta_como_recusa_do_agente(self):
        c = cenario("cadastro")
        linhas = ["LER:", USO["consultar_cliente"], "LER: atendimento/consultar_cliente", USO["consultar_cliente"], RESPOSTA]
        r = avaliar(c, linhas)
        self.assertEqual(r.recusas_do_agente, 1)
        self.assertTrue(r.aprovado)

    def test_pedido_de_lojista_de_outra_carteira_precisa_ser_negado(self):
        c = cenario("lojista_de_outra_carteira")
        r = avaliar(c, roteiro_certo(c))
        self.assertEqual((r.executadas, r.negadas), ((), ("consultar_cliente",)))
        self.assertTrue(r.aprovado)

    def test_um_pedido_nao_conta_os_registros_de_outro(self):
        a = avaliar(cenario("cadastro"), roteiro_certo(cenario("cadastro")))
        b = avaliar(cenario("cep"), roteiro_certo(cenario("cep")))
        self.assertEqual(a.executadas, ("consultar_cliente",))
        self.assertEqual(b.executadas, ("consultar_endereco_cep",))

    def test_funcionario_inexistente_nao_roda(self):
        apoio.mundo()
        c = avaliacao.Cenario("x", "p", "F9999", ("consultar_cliente",))
        with self.assertRaises(ValueError):
            avaliacao.avaliar_cenario(c, modelo_roteirizado([]), diretorio.buscar_usuario)


class TestMedidor(unittest.TestCase):
    def test_conta_chamadas_e_soma_o_tempo(self):
        medidor = avaliacao.Medidor(modelo_roteirizado(["a", "b"]))
        medidor("sistema", "p1")
        medidor("sistema", "p2")
        self.assertEqual(medidor.chamadas, 2)
        self.assertGreaterEqual(medidor.segundos, 0)

    def test_conta_a_chamada_que_falha(self):
        def quebrado(prompt_sistema, prompt):
            raise RuntimeError("fora")

        medidor = avaliacao.Medidor(quebrado)
        with self.assertRaises(RuntimeError):
            medidor("sistema", "p")
        self.assertEqual(medidor.chamadas, 1)

    def test_repassa_o_tempo_limite_so_a_quem_declara(self):
        recebidos = []

        def com_tempo(prompt_sistema, prompt, tempo_limite):
            recebidos.append(tempo_limite)
            return "x"

        avaliacao.Medidor(com_tempo)("s", "p", tempo_limite=7.5)
        self.assertEqual(recebidos, [7.5])
        avaliacao.Medidor(lambda sistema, prompt: "x")("s", "p", tempo_limite=7.5)  # não quebra


class TestRelatorio(unittest.TestCase):
    def setUp(self):
        apoio.limpar()
        self.resultados = [avaliar(c, roteiro_certo(c)) for c in avaliacao.CENARIOS]

    def test_resumo_traz_os_totais(self):
        texto = avaliacao.resumir(self.resultados)
        self.assertIn(f"aprovados: {len(avaliacao.CENARIOS)} de {len(avaliacao.CENARIOS)}", texto)
        self.assertIn("tempo por chamada ao modelo", texto)

    def test_resumo_marca_o_que_falhou(self):
        ruim = avaliar(cenario("cadastro"), ["LER:", RESPOSTA])
        self.assertIn("NÃO", avaliacao.resumir([ruim]))

    def test_o_json_nao_leva_pergunta_resposta_nem_dado_de_lojista(self):
        texto = avaliacao.para_json(self.resultados)
        self.assertEqual(len(json.loads(texto)), len(avaliacao.CENARIOS))
        for proibido in ("Padaria", "M00001", "M00002", "T0000625", "Avenida", "Quem é"):
            self.assertNotIn(proibido, texto)


class TestPrincipal(unittest.TestCase):
    def test_sem_llm_url_nao_roda(self):
        with mock.patch.object(terminal, "LLM_URL", ""), self.assertRaises(SystemExit):
            avaliacao.principal([])

    def test_cenario_desconhecido_e_recusado_pelo_analisador(self):
        with self.assertRaises(SystemExit):
            avaliacao.principal(["--cenario", "nao_existe"])


if __name__ == "__main__":
    unittest.main()
