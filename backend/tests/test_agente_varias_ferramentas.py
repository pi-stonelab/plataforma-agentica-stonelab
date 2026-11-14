"""Um pedido que precisa de mais de uma ferramenta: o agente encadeia, e cada uma passa pelas suas portas.

O modelo é roteirizado (sem rede). O que se testa é o motor: a observação de uma ferramenta chega ao
modelo antes da próxima, cada USAR é conferido sozinho (cargo, carteira, leitura prévia) e uma recusa no
meio do caminho não derruba as outras. O teste com o modelo real fica para a avaliação com credenciais.
"""

import re
import unittest

from agentes.agente_atendimento import agente
from ferramentas import governanca

from . import apoio_agente as apoio
from .apoio_agente import modelo_roteirizado

LER_CLIENTE = "LER: atendimento/consultar_cliente"
LER_TRANSACOES = "LER: financeiro/consultar_transacoes_cliente"
LER_MULTA = "LER: financeiro/calcular_multa_atraso"
LER_CEP = "LER: consultas_publicas/consultar_endereco_cep"

CLIENTE = 'USAR: consultar_cliente | {"id_cliente": "M00001"}'
TRANSACOES = 'USAR: consultar_transacoes_cliente | {"id_cliente": "M00001"}'
TRANSACOES_OUTRA_CARTEIRA = 'USAR: consultar_transacoes_cliente | {"id_cliente": "M00002"}'
MULTA = 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}'
CEP = 'USAR: consultar_endereco_cep | {"cep": "01310-100"}'

FERRAMENTAS_USADAS = ("consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso")


def turno(linhas, usuario, **extras):
    prompts = extras.pop("prompts", None)
    return agente.rodar_turno(
        "pergunta de teste", usuario, apoio.AGENTE_COMPLETO, modelo_roteirizado(linhas, prompts), **extras
    )


def roteiro_de_tres():
    return [
        "LER:", LER_CLIENTE, LER_TRANSACOES, LER_MULTA,
        CLIENTE, TRANSACOES, MULTA, "FINAL: pronto.",
    ]


class TestEncadeamento(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_tres_ferramentas_no_mesmo_turno_deixam_tres_registros_em_ordem(self):
        resultado = turno(roteiro_de_tres(), apoio.coordenador_financeiro())
        self.assertEqual(resultado.tipo, "final")
        self.assertEqual(len(resultado.trajetoria), 8)
        usadas = [r for r in governanca.REGISTROS if r["status"] == "ok"]
        self.assertEqual(tuple(r["ferramenta"] for r in usadas), FERRAMENTAS_USADAS)
        self.assertEqual([r["passo"] for r in usadas], [5, 6, 7])
        self.assertEqual(len({r["execucao_id"] for r in usadas}), 1)
        self.assertEqual({r["agente_id"] for r in usadas}, {agente.AGENTE_ID})

    def test_a_observacao_de_uma_ferramenta_chega_ao_modelo_antes_da_proxima(self):
        prompts = []
        turno(roteiro_de_tres(), apoio.coordenador_financeiro(), prompts=prompts)
        antes_do_cliente, antes_das_transacoes, antes_da_multa, antes_do_final = (
            prompts[4], prompts[5], prompts[6], prompts[7],
        )
        self.assertNotIn("Padaria Pão da Vila", antes_do_cliente)
        self.assertIn("Padaria Pão da Vila", antes_das_transacoes)
        self.assertIn("T0000625", antes_da_multa)
        self.assertIn('"valor_total": 1030.0', antes_do_final)

    def test_modelo_que_usa_o_resultado_da_primeira_para_chamar_a_segunda(self):
        """O código do cliente sai da observação do cadastro e vira o argumento das transações."""
        passos = iter(["LER:", LER_CLIENTE, LER_TRANSACOES, CLIENTE])

        def chamar(prompt_sistema, prompt):
            proximo = next(passos, None)
            if proximo is not None:
                return proximo
            codigo = re.findall(r'"codigo": "(M\d+)"', prompt)[-1]  # falha se a observação não chegou
            if "T0000625" in prompt:
                return f"FINAL: transações de {codigo} consultadas."
            return f'USAR: consultar_transacoes_cliente | {{"id_cliente": "{codigo}"}}'

        resultado = agente.rodar_turno(
            "pergunta de teste", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, chamar
        )
        self.assertEqual(resultado.tipo, "final")
        self.assertEqual(
            [r["ferramenta"] for r in governanca.REGISTROS if r["status"] == "ok"],
            ["consultar_cliente", "consultar_transacoes_cliente"],
        )


class TestCadaFerramentaTemSuasPortas(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_recusa_de_carteira_no_meio_nao_derruba_as_outras(self):
        # Ana é do varejo: M00001 é dela, M00002 (pme) não.
        linhas = [
            "LER:", LER_CLIENTE, LER_TRANSACOES, LER_MULTA,
            CLIENTE, TRANSACOES_OUTRA_CARTEIRA, MULTA, "FINAL: consultei o que pude.",
        ]
        resultado = turno(linhas, apoio.atendente_n1())
        self.assertEqual(resultado.tipo, "final")
        situacao = [(r["ferramenta"], r["status"], r["tipo_erro"]) for r in governanca.REGISTROS]
        self.assertEqual(
            situacao,
            [
                ("consultar_cliente", "ok", None),
                ("consultar_transacoes_cliente", "erro", "permissao_negada"),
                ("calcular_multa_atraso", "ok", None),
            ],
        )

    def test_ferramenta_fora_do_cargo_some_e_as_do_cargo_seguem(self):
        # A analista de cobrança não tem a categoria de dado "venda": as transações não existem para ela.
        linhas = [
            "LER:", LER_CLIENTE, LER_TRANSACOES, LER_MULTA,
            CLIENTE, TRANSACOES, MULTA, "FINAL: sem acesso às transações.",
        ]
        resultado = turno(linhas, apoio.analista_cobranca())
        self.assertEqual(resultado.tipo, "final")
        self.assertIn("não encontrado", resultado.trajetoria[2])
        self.assertIn("ferramenta não lida", resultado.trajetoria[5])
        executadas = [r["ferramenta"] for r in governanca.REGISTROS if r["camada_bloqueio"] != "agente"]
        self.assertEqual(executadas, ["consultar_cliente", "calcular_multa_atraso"])
        self.assertNotIn("consultar_transacoes_cliente", resultado.estado["ferramentas_lidas"][-1])


class TestLimiteDePassosComVariasFerramentas(unittest.TestCase):
    """Cada ferramenta gasta 2 passos (ler a ficha, usar), mais o índice e o FINAL."""

    def setUp(self):
        apoio.limpar()

    def roteiro_de_quatro(self):
        return [
            "LER:", LER_CLIENTE, LER_TRANSACOES, LER_MULTA, LER_CEP,
            CLIENTE, TRANSACOES, MULTA, CEP, "FINAL: pronto.",
        ]

    def test_quatro_ferramentas_cabem_exatamente_nos_dez_passos(self):
        roteiro = self.roteiro_de_quatro()
        self.assertEqual(len(roteiro), agente.MAX_PASSOS)
        resultado = turno(roteiro, apoio.coordenador_financeiro())
        self.assertEqual(resultado.tipo, "final")
        self.assertEqual(len([r for r in governanca.REGISTROS if r["status"] == "ok"]), 4)

    def test_um_passo_a_mais_executa_as_quatro_mas_a_resposta_nao_sai(self):
        roteiro = self.roteiro_de_quatro()
        roteiro.insert(1, "LER: financeiro")  # ler a área é opcional, mas gasta um passo
        resultado = turno(roteiro, apoio.coordenador_financeiro())
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "max_passos"))
        self.assertEqual(resultado.resposta, agente.MENSAGEM_LIMITE_PASSOS)
        self.assertEqual(len([r for r in governanca.REGISTROS if r["status"] == "ok"]), 4)


if __name__ == "__main__":
    unittest.main()
