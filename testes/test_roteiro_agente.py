import json
import unittest

from ferramentas import governanca
from testes import apoio

MULTA = 'USAR: calcular_multa_atraso {"valor_fatura": 1000, "dias_atraso": 30}'
CLIENTE = 'USAR: consultar_cliente {"id_cliente": "CLI-0001"}'


def rodar(linhas, usuario):
    return apoio.rodar_loop(apoio.ModeloRoteirizado(linhas), usuario, apoio.AGENTE_COMPLETO)


class TestRoteiroDoAgente(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_caminho_feliz_ler_ler_usar_final(self):
        linhas = ["LER: ", "LER: financeiro", MULTA, "FINAL: R$ 1030,00."]
        final, obs = rodar(linhas, apoio.n2_financeiro())
        self.assertEqual(final, "R$ 1030,00.")
        self.assertIn("- `financeiro`:", obs[0])
        self.assertIn("- `calcular_multa_atraso`:", obs[1])
        self.assertEqual(json.loads(obs[2])["dados"]["valor_total"], 1030.0)

    def test_ferramenta_bloqueada_volta_como_inexistente(self):
        linhas = [CLIENTE, CLIENTE.replace("consultar_cliente", "nao_existe"), "FINAL: x"]
        bloqueada, inexistente = (json.loads(o) for o in rodar(linhas, apoio.n1_dados())[1])
        self.assertEqual(bloqueada["tipo_erro"], "ferramenta_inexistente")
        self.assertEqual(bloqueada, inexistente)

    def test_cliente_fora_da_carteira_e_registro_sem_conteudo(self):
        linhas = [CLIENTE.replace("0001", "0002"), CLIENTE, "FINAL: x"]
        obs = rodar(linhas, apoio.n1_atendimento())[1]
        self.assertEqual(json.loads(obs[0])["tipo_erro"], "permissao_negada")
        self.assertEqual(json.loads(obs[1])["status"], "ok")
        self.assertEqual(len(governanca.REGISTROS), 2)
        self.assertNotIn("CLI-000", json.dumps(governanca.REGISTROS))
