import contextlib
import io
import json
import unittest

from agentes.agente_atendimento import agente
from ferramentas import governanca
from testes import apoio

MULTA = 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}'
CLIENTE_FORA = 'USAR: consultar_cliente | {"id_cliente": "CLI-0002"}'


def modelo_roteirizado(linhas):
    respostas = iter(linhas)

    def chamar(historico):
        return next(respostas)

    return chamar


def rodar(linhas, usuario):
    with contextlib.redirect_stdout(io.StringIO()):
        return agente.agente("pergunta de teste", usuario, modelo_roteirizado(linhas))


class TestLoopDoAgente(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_caminho_feliz_gera_registro_com_agente_e_passo(self):
        linhas = [
            "LER:",
            "LER: financeiro",
            "LER: financeiro/calcular_multa_atraso",
            MULTA,
            "FINAL: R$ 1030,00.",
        ]
        final, trajetoria = rodar(linhas, apoio.n2_financeiro())
        self.assertEqual(final, "R$ 1030,00.")
        self.assertEqual(len(trajetoria), 5)
        registro = governanca.REGISTROS[-1]
        self.assertEqual(registro["agente_id"], agente.AGENTE_ID)
        self.assertEqual(registro["ferramenta"], "calcular_multa_atraso")
        self.assertEqual(registro["passo"], 4)
        self.assertIsNone(registro["tipo_erro"])
        self.assertTrue(registro["execucao_id"])

    def test_usar_sem_ler_a_ferramenta_e_bloqueado(self):
        _, trajetoria = rodar(["LER:", MULTA, "FINAL: ok"], apoio.n2_financeiro())
        self.assertIn("ferramenta não lida", trajetoria[1])
        self.assertEqual(governanca.REGISTROS, [])

    def test_ler_caminho_antes_do_indice_e_bloqueado(self):
        _, trajetoria = rodar(["LER: financeiro", "LER:", "FINAL: ok"], apoio.n2_financeiro())
        self.assertIn("índice não lido", trajetoria[0])

    def test_final_sem_consultar_o_indice_e_recusado(self):
        final, trajetoria = rodar(["FINAL: oi", "LER:", "FINAL: ok"], apoio.n2_financeiro())
        self.assertEqual(final, "ok")
        self.assertIn("FINAL sem consultar", trajetoria[0])

    def test_ferramenta_bloqueada_se_comporta_como_inexistente(self):
        def passos(caminho):
            linhas = [
                "LER:",
                f"LER: {caminho}",
                "USAR: " + caminho.split("/")[-1] + " | {}",
                "FINAL: x",
            ]
            return rodar(linhas, apoio.n1_dados())[1]

        bloqueada = passos("financeiro/consultar_transacoes_cliente")
        inexistente = passos("financeiro/ferramenta_que_nao_existe")
        self.assertIn("não encontrado", bloqueada[1])
        self.assertEqual(
            [p.partition("->")[2] for p in bloqueada], [p.partition("->")[2] for p in inexistente]
        )

    def test_cliente_fora_da_carteira_volta_permissao_negada(self):
        linhas = [
            "LER:",
            "LER: atendimento",
            "LER: atendimento/consultar_cliente",
            CLIENTE_FORA,
            "FINAL: sem acesso",
        ]
        _, trajetoria = rodar(linhas, apoio.n1_atendimento())
        self.assertIn("permissao_negada", trajetoria[3])
        registro = governanca.REGISTROS[-1]
        self.assertEqual(registro["tipo_erro"], "permissao_negada")
        self.assertNotIn("CLI-0002", json.dumps(registro))

    def test_usar_aceita_o_nome_com_ou_sem_a_area(self):
        for nome in ("calcular_multa_atraso", "financeiro/calcular_multa_atraso"):
            apoio.limpar()
            args = '{"valor_fatura": 1000, "dias_atraso": 30}'
            linhas = [
                "LER:",
                "LER: financeiro/calcular_multa_atraso",
                f"USAR: {nome} | {args}",
                "FINAL: ok",
            ]
            _, trajetoria = rodar(linhas, apoio.n2_financeiro())
            self.assertIn("executada: ok", trajetoria[2])

    def test_pedido_de_ferramenta_ausente_funciona_pelo_caminho_do_prompt(self):
        self.assertIn("plataforma/solicitar_ferramenta_ausente", agente.SISTEMA)
        args = (
            '{"nome_sugerido": "consultar_saldo_conta", "descricao": "Saldo da conta do cliente"}'
        )
        linhas = [
            "LER:",
            "LER: plataforma/solicitar_ferramenta_ausente",
            f"USAR: solicitar_ferramenta_ausente | {args}",
            "FINAL: pedido registrado",
        ]
        final, trajetoria = rodar(linhas, apoio.n2_financeiro())
        self.assertEqual(final, "pedido registrado")
        self.assertIn("executada: ok", trajetoria[2])
        self.assertEqual(len(apoio.pedidos()), 1)

    def test_argumentos_que_nao_sao_json_sao_recusados(self):
        linhas = [
            "LER:",
            "LER: financeiro/calcular_multa_atraso",
            "USAR: calcular_multa_atraso | {x",
            "FINAL: ok",
        ]
        _, trajetoria = rodar(linhas, apoio.n2_financeiro())
        self.assertIn("argumentos inválidos", trajetoria[2])

    def test_resposta_fora_do_formato_nao_derruba_o_loop(self):
        final, trajetoria = rodar(["blá blá", "LER:", "FINAL: ok"], apoio.n2_financeiro())
        self.assertEqual(final, "ok")
        self.assertIn("fora do formato", trajetoria[0])

    def test_texto_na_linha_de_baixo_nao_vira_caminho(self):
        final, _ = rodar(["LER:\ntexto solto", "FINAL: ok"], apoio.n2_financeiro())
        self.assertEqual(final, "ok")

    def test_estouro_de_passos_devolve_mensagem_padrao(self):
        with contextlib.redirect_stdout(io.StringIO()):
            final, trajetoria = agente.agente(
                "pergunta", apoio.n2_financeiro(), lambda historico: "LER:"
            )
        self.assertIn("Não consegui concluir", final)
        self.assertEqual(len(trajetoria), agente.MAX_PASSOS)


class TestUsuarioDoAmbiente(unittest.TestCase):
    def setUp(self):
        self.base = {
            "ID_USUARIO": "USR-9",
            "NIVEL": "n1",
            "AREA": "Atendimento",
            "CARTEIRA": "CLI-1, CLI-2",
        }

    def test_monta_o_usuario_e_normaliza_os_campos(self):
        usuario = agente.usuario_do_ambiente(self.base)
        self.assertEqual(
            (usuario.id_usuario, usuario.nivel, usuario.area, usuario.carteira),
            ("USR-9", "N1", "atendimento", ("CLI-1", "CLI-2")),
        )

    def test_carteira_e_opcional(self):
        base = {k: v for k, v in self.base.items() if k != "CARTEIRA"}
        self.assertEqual(agente.usuario_do_ambiente(base).carteira, ())

    def test_falta_de_dado_ou_valor_invalido_nao_sobe(self):
        for campo, valor in (("ID_USUARIO", ""), ("NIVEL", "N9"), ("AREA", "rh")):
            ambiente = dict(self.base, **{campo: valor})
            with self.assertRaises(ValueError):
                agente.usuario_do_ambiente(ambiente)
        with self.assertRaises(ValueError):
            agente.usuario_do_ambiente({})


if __name__ == "__main__":
    unittest.main()
