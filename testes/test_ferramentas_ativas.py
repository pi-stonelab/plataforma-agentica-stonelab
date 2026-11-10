import importlib
import unittest
from datetime import date

from ferramentas import catalogo, governanca
from testes import apoio


def chamar(nome, argumentos, usuario=None):
    usuario = usuario or apoio.n2_financeiro()
    return catalogo.executar(nome, argumentos, usuario, apoio.AGENTE_COMPLETO)


class Base(unittest.TestCase):
    ferramenta = ""

    def setUp(self):
        apoio.limpar()

    def chamar(self, usuario=None, **argumentos):
        resposta = chamar(self.ferramenta, argumentos, usuario)
        apoio.confere_forma(self, resposta)
        return resposta

    def recusa(self, tipo_erro, casos, **fixos):
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertEqual(self.chamar(**{**fixos, **caso})["tipo_erro"], tipo_erro)


class TestConsultarCliente(Base):
    ferramenta = "consultar_cliente"

    def test_sucesso_com_os_campos_do_contrato_para_os_oito_clientes(self):
        campos = [
            "id_cliente",
            "nome_fantasia",
            "segmento",
            "cidade",
            "uf",
            "situacao",
            "cliente_desde",
        ]
        for numero in range(1, 9):
            dados = self.chamar(id_cliente=f"CLI-000{numero}")["dados"]
            self.assertEqual(sorted(dados), sorted(campos))

    def test_formato_invalido_ou_ausente(self):
        ids = ["CLI-12", "cli-0001", "CLI-00011", "0001", "CLI-0001; DROP TABLE x", "", 1]
        self.recusa("parametro_invalido", [{"id_cliente": i} for i in ids] + [{}])

    def test_inexistente_para_n2(self):
        self.assertEqual(self.chamar(id_cliente="CLI-0099")["tipo_erro"], "nao_encontrado")

    def test_n1_na_carteira_acessa_e_fora_recebe_permissao_negada(self):
        n1 = apoio.n1_atendimento()
        self.assertEqual(self.chamar(n1, id_cliente="CLI-0001")["status"], "ok")
        existente = self.chamar(n1, id_cliente="CLI-0002")
        inexistente = self.chamar(n1, id_cliente="CLI-0099")
        self.assertEqual(existente["tipo_erro"], "permissao_negada")
        self.assertEqual(existente, inexistente)

    def test_n1_com_cliente_da_carteira_que_nao_existe(self):
        usuario = governanca.Usuario("USR-5", "N1", "atendimento", ("CLI-0099",))
        self.assertEqual(self.chamar(usuario, id_cliente="CLI-0099")["tipo_erro"], "nao_encontrado")


class TestConsultarTransacoes(Base):
    ferramenta = "consultar_transacoes_cliente"

    def transacoes(self, **extra):
        return self.chamar(id_cliente="CLI-0001", **extra)["dados"]

    def test_forma_total_e_limite_padrao(self):
        dados = self.transacoes()
        self.assertEqual(
            sorted(dados), ["id_cliente", "total_encontrado", "transacoes", "truncado"]
        )
        campos = ["data", "id_transacao", "situacao", "tipo", "valor"]
        self.assertEqual(sorted(dados["transacoes"][0]), campos)
        self.assertEqual((dados["total_encontrado"], len(dados["transacoes"])), (60, 20))
        self.assertTrue(dados["truncado"])

    def test_limites_aceitos_e_recusados(self):
        self.assertEqual(len(self.transacoes(limite=governanca.LIMITE_LINHAS)["transacoes"]), 50)
        self.assertEqual(len(self.transacoes(limite=1)["transacoes"]), 1)
        ruins = [0, -1, 51, 1000, "20", 2.5, True]
        self.recusa("parametro_invalido", [{"limite": n} for n in ruins], id_cliente="CLI-0001")

    def test_formato_dos_valores_e_ordem(self):
        itens = self.transacoes(limite=50)["transacoes"]
        self.assertEqual(
            [i["data"] for i in itens], sorted((i["data"] for i in itens), reverse=True)
        )
        for item in itens:
            self.assertEqual(round(item["valor"], 2), item["valor"])
            self.assertIsInstance(item["valor"], float)
            self.assertIn(item["tipo"], ("credito", "debito", "pix"))
            self.assertIn(item["situacao"], ("aprovada", "estornada", "contestada"))
            self.assertEqual(date.fromisoformat(item["data"]).year, 2026)

    def test_filtro_de_periodo_e_periodo_vazio(self):
        dados = self.transacoes(data_inicio="2026-03-01", data_fim="2026-03-31", limite=50)
        self.assertTrue(all("2026-03-01" <= t["data"] <= "2026-03-31" for t in dados["transacoes"]))
        self.assertEqual(dados["truncado"], dados["total_encontrado"] > len(dados["transacoes"]))
        vazio = self.transacoes(data_inicio="2020-01-01", data_fim="2020-01-31")
        self.assertEqual(
            (vazio["transacoes"], vazio["total_encontrado"], vazio["truncado"]), ([], 0, False)
        )

    def test_datas_invalidas(self):
        casos = [{"data_inicio": "2026-05-01", "data_fim": "2026-04-01"}]
        casos += [{"data_inicio": d} for d in ("01/03/2026", "2026-13-01", "ontem", 20260301)]
        self.recusa("parametro_invalido", casos, id_cliente="CLI-0001")

    def test_cli_0002_tem_transacao_contestada(self):
        itens = self.chamar(id_cliente="CLI-0002", limite=50)["dados"]["transacoes"]
        self.assertIn("contestada", {i["situacao"] for i in itens})

    def test_cliente_inexistente_e_id_malicioso(self):
        self.assertEqual(self.chamar(id_cliente="CLI-0099")["tipo_erro"], "nao_encontrado")
        self.recusa("parametro_invalido", [{"id_cliente": "x' OR '1'='1"}])

    def test_n1_so_a_carteira_e_area_sem_permissao_nao_ve_a_ferramenta(self):
        n1 = apoio.n1_atendimento()
        self.assertEqual(self.chamar(n1, id_cliente="CLI-0001")["status"], "ok")
        self.assertEqual(self.chamar(n1, id_cliente="CLI-0002")["tipo_erro"], "permissao_negada")
        dados = apoio.n1_dados()
        self.assertEqual(
            self.chamar(dados, id_cliente="CLI-0001")["tipo_erro"], "ferramenta_inexistente"
        )


class TestCalcularMulta(Base):
    ferramenta = "calcular_multa_atraso"

    def valores(self, valor, dias):
        dados = self.chamar(valor_fatura=valor, dias_atraso=dias)["dados"]
        return dados["multa"], dados["juros"], dados["valor_total"]

    def test_exemplos_do_contrato(self):
        self.assertEqual(self.valores(1000, 30), (20.0, 10.0, 1030.0))
        self.assertEqual(self.valores(1000, 15), (20.0, 5.0, 1025.0))
        self.assertEqual(self.valores(1000, 0), (0.0, 0.0, 1000.0))

    def test_forma_dos_dados(self):
        dados = self.chamar(valor_fatura=1000, dias_atraso=30)["dados"]
        campos = ["valor_fatura", "dias_atraso", "multa", "juros", "valor_total", "regra"]
        self.assertEqual(sorted(dados), sorted(campos))
        self.assertTrue(all(isinstance(dados[c], float) for c in campos[:1] + campos[2:5]))
        self.assertTrue(dados["regra"])

    def test_arredondamento_meio_para_cima_e_juros_pro_rata(self):
        self.assertEqual(self.valores(0.25, 1)[0], 0.01)
        self.assertEqual(self.valores(0.75, 1)[0], 0.02)
        self.assertEqual(self.valores(1000, 1)[1], 0.33)
        self.assertEqual(self.valores(1000, 3650)[1], 1216.67)

    def test_limites_aceitos_e_texto_numerico(self):
        self.assertEqual(self.chamar(valor_fatura=1000000, dias_atraso=3650)["status"], "ok")
        self.assertEqual(self.chamar(valor_fatura=0.01, dias_atraso=0)["status"], "ok")
        self.assertEqual(self.valores("1000.00", 30)[2], 1030.0)

    def test_valores_fora_da_faixa_ou_de_tipo_errado(self):
        casos = [(0, 10), (-5, 10), (1000000.01, 10), (10**12, 10), (1000, -1), (1000, 3651)]
        casos += [("abc", 1), (True, 1), (None, 1), (1000, True), (1000, "x"), (1000, None)]
        casos += [(float("nan"), 1), (float("inf"), 1), ("NaN", 1), ("1e999", 1)]
        self.recusa("parametro_invalido", [{"valor_fatura": v, "dias_atraso": d} for v, d in casos])

    def test_qualquer_area_e_nivel_calcula(self):
        for usuario in (apoio.n1_atendimento(), apoio.n1_dados(), apoio.n2_financeiro()):
            self.assertEqual(self.chamar(usuario, valor_fatura=100, dias_atraso=1)["status"], "ok")


class TestConsultarEnderecoCep(Base):
    ferramenta = "consultar_endereco_cep"

    def test_cep_com_e_sem_hifen(self):
        for texto in ("01310-100", "01310100"):
            dados = self.chamar(cep=texto)["dados"]
            self.assertEqual(sorted(dados), ["bairro", "cep", "cidade", "logradouro", "uf"])
            self.assertEqual(
                (dados["cep"], dados["cidade"], dados["uf"]), ("01310100", "São Paulo", "SP")
            )
            self.assertIn("Paulista", dados["logradouro"])

    def test_ausente_da_base(self):
        self.assertEqual(self.chamar(cep="99999999")["tipo_erro"], "nao_encontrado")

    def test_formato_invalido_tipo_errado_ou_ausente(self):
        ruins = ["1310100", "013101000", "abcdefgh", "01310-10", "0131-0100", "01310 100", ""]
        ruins += ["01310-100; DROP", "../../etc", 1310100]
        self.recusa("parametro_invalido", [{"cep": c} for c in ruins] + [{}])

    def test_qualquer_funcionario_consulta(self):
        for usuario in (apoio.n1_atendimento(), apoio.n1_dados()):
            self.assertEqual(self.chamar(usuario, cep="01310100")["status"], "ok")


class TestSolicitarFerramentaAusente(Base):
    ferramenta = "solicitar_ferramenta_ausente"

    def pedir(self, nome="ferramenta_nova", descricao="Preciso disso.", usuario=None):
        return self.chamar(usuario, nome_sugerido=nome, descricao=descricao)

    def test_sucesso_conta_vezes_e_guarda_o_pedido(self):
        primeiro, segundo = self.pedir()["dados"], self.pedir()["dados"]
        self.assertEqual(sorted(primeiro), ["id_pedido", "nome_sugerido", "vezes_pedida"])
        self.assertRegex(primeiro["id_pedido"], r"^PED-\d{4}$")
        self.assertEqual((primeiro["vezes_pedida"], segundo["vezes_pedida"]), (1, 2))
        self.assertNotEqual(primeiro["id_pedido"], segundo["id_pedido"])
        self.assertEqual(len(apoio.pedidos()), 2)

    def test_nome_fora_do_padrao_e_descricao_ruim(self):
        nomes = ["ab", "1abc", "a b", "UPPER", "com-hifen", "a" * 61, "", "nome;drop", "../x"]
        self.recusa("parametro_invalido", [{"nome_sugerido": n, "descricao": "d"} for n in nomes])
        self.recusa("parametro_invalido", [{"nome_sugerido": "abc", "descricao": "x" * 301}])
        self.recusa("parametro_invalido", [{"nome_sugerido": "abc"}])

    def test_fila_cheia_recusa_sem_crescer(self):
        modulo = importlib.import_module("ferramentas.plataforma.solicitar_ferramenta_ausente.func")
        limite_original = modulo.LIMITE_PEDIDOS
        modulo.LIMITE_PEDIDOS = 2
        try:
            respostas = [self.pedir()["tipo_erro"] for _ in range(3)]
        finally:
            modulo.LIMITE_PEDIDOS = limite_original
        self.assertEqual(respostas, [None, None, "integracao_indisponivel"])
        self.assertEqual(len(apoio.pedidos()), 2)

    def test_nomes_nos_limites_do_padrao(self):
        for nome in ("abc", "a" + "b" * 59):
            self.assertEqual(self.pedir(nome)["status"], "ok")

    def test_escrita_liberada_funciona_em_qualquer_area_sem_deixar_conteudo_no_registro(self):
        for usuario in (apoio.n1_atendimento(), apoio.n1_dados()):
            self.assertEqual(self.pedir(usuario=usuario)["status"], "ok")
        self.pedir("nome_secreto_77", "descricao_secreta_77")
        self.assertNotIn("secreto_77", str(governanca.REGISTROS))
