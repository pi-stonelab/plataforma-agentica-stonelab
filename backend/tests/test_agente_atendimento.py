import contextlib
import io
import json
import logging
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from agentes.agente_atendimento import agente
from ferramentas import governanca

from . import apoio_agente as apoio

MULTA = 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}'
CLIENTE_FORA = 'USAR: consultar_cliente | {"id_cliente": "CLI-0002"}'


CANARIO = "CANARIO-123"
INDICE = ["LER:"]
LER_MULTA = "LER: financeiro/calcular_multa_atraso"


def modelo_roteirizado(linhas, prompts=None):
    """Devolve as linhas em ordem; se `prompts` for uma lista, guarda cada prompt recebido."""
    respostas = iter(linhas)

    def chamar(prompt_sistema, prompt):
        if prompts is not None:
            prompts.append(prompt)
        return next(respostas)

    return chamar


def rodar(linhas, usuario):
    return agente.agente("pergunta de teste", usuario, modelo_roteirizado(linhas))


def turno(linhas, usuario, **extras):
    """Roda um turno completo e devolve o Turno; `extras` vão direto para rodar_turno."""
    prompts = extras.pop("prompts", None)
    ferramentas = extras.pop("ferramentas", apoio.AGENTE_COMPLETO)
    return agente.rodar_turno(
        "pergunta de teste", usuario, ferramentas, modelo_roteirizado(linhas, prompts), **extras
    )


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
        final, trajetoria = agente.agente(
            "pergunta", apoio.n2_financeiro(), lambda prompt_sistema, prompt: "LER:"
        )
        self.assertIn("Não consegui concluir", final)
        self.assertEqual(len(trajetoria), agente.MAX_PASSOS)

    def test_agente_usa_as_ferramentas_recebidas_por_parametro(self):
        linhas = ["LER:", LER_MULTA, MULTA, "FINAL: ok"]
        final, _ = agente.agente(
            "p", apoio.n2_financeiro(), modelo_roteirizado(linhas), ("calcular_multa_atraso",)
        )
        self.assertEqual(final, "ok")


class TestPromptDeSistema(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_cada_chamada_ao_modelo_leva_o_protocolo(self):
        recebidos = []

        def modelo(prompt_sistema, prompt):
            recebidos.append(prompt_sistema)
            return "LER:" if len(recebidos) == 1 else "FINAL: ok"

        resultado = agente.rodar_turno("p", apoio.n2_financeiro(), apoio.AGENTE_COMPLETO, modelo)
        self.assertEqual(resultado.resposta, "ok")
        self.assertEqual(recebidos, [agente.SISTEMA, agente.SISTEMA])
        for acao in ("LER:", "USAR:", "PERGUNTAR:", "FINAL:"):
            self.assertIn(acao, agente.SISTEMA)

    def test_agente_pode_ter_prompt_de_sistema_proprio(self):
        recebidos = []

        def modelo(prompt_sistema, prompt):
            recebidos.append(prompt_sistema)
            return "FINAL: x" if len(recebidos) > 1 else "LER:"

        agente.rodar_turno(
            "p", apoio.n2_financeiro(), apoio.AGENTE_COMPLETO, modelo, prompt_sistema="outro"
        )
        self.assertEqual(set(recebidos), {"outro"})

    def test_chamar_llm_envia_o_sistema_e_a_parada(self):
        resposta = mock.Mock()
        resposta.json.return_value = {"response": "<think>x</think>FINAL: ok"}
        ambiente = {"CF_ACCESS_CLIENT_ID": "id", "CF_ACCESS_CLIENT_SECRET": "segredo"}
        with (
            mock.patch.dict("os.environ", ambiente),
            mock.patch.object(agente, "LLM_URL", "http://modelo.teste"),
            mock.patch.object(agente.requests, "post", return_value=resposta) as post,
        ):
            texto = agente.chamar_llm("SISTEMA DE TESTE", "prompt de teste")
        enviado = post.call_args.kwargs["json"]
        self.assertEqual(texto, "FINAL: ok")
        self.assertEqual(enviado["system"], "SISTEMA DE TESTE")
        self.assertEqual(enviado["prompt"], "prompt de teste")
        self.assertEqual(enviado["options"]["stop"], [agente.PARADA_DO_MODELO])


class TestTurno(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_final_devolve_turno_com_estado_em_json(self):
        resultado = turno(INDICE + [LER_MULTA, MULTA, "FINAL: R$ 1030,00."], apoio.n2_financeiro())
        self.assertEqual((resultado.tipo, resultado.resposta), ("final", "R$ 1030,00."))
        self.assertIsNone(resultado.motivo)
        self.assertEqual(
            json.loads(json.dumps(resultado.estado)),
            {"indice_lido": True, "ferramentas_lidas": ["financeiro/calcular_multa_atraso"]},
        )

    def test_contexto_define_execucao_e_agente_no_registro(self):
        contexto = {"execucao_id": "exec-42", "agente_id": "agente_x"}
        turno(INDICE + [LER_MULTA, MULTA, "FINAL: ok"], apoio.n2_financeiro(), contexto=contexto)
        registro = governanca.REGISTROS[-1]
        self.assertEqual((registro["execucao_id"], registro["agente_id"]), ("exec-42", "agente_x"))

    def test_sem_contexto_gera_execucao_id(self):
        turno(INDICE + [LER_MULTA, MULTA, "FINAL: ok"], apoio.n2_financeiro())
        registro = governanca.REGISTROS[-1]
        self.assertTrue(registro["execucao_id"])
        self.assertEqual(registro["agente_id"], agente.AGENTE_ID)

    def test_perguntar_encerra_o_turno_sem_input(self):
        pergunta = "PERGUNTAR: Qual é o código do cliente?"
        resultado = turno(INDICE + [pergunta, "FINAL: nunca chega aqui"], apoio.n1_atendimento())
        self.assertEqual((resultado.tipo, resultado.resposta), ("pergunta", "Qual é o código do cliente?"))
        self.assertEqual(len(resultado.trajetoria), 2)
        self.assertTrue(resultado.estado["indice_lido"])

    def test_estado_permite_continuar_sem_reler_o_indice(self):
        usuario = apoio.n2_financeiro()
        primeiro = turno(
            INDICE + [LER_MULTA, "PERGUNTAR: Qual o valor da fatura?"], usuario
        )
        self.assertEqual(primeiro.tipo, "pergunta")

        prompts = []
        segundo = agente.rodar_turno(
            "1000 reais, 30 dias",
            usuario,
            apoio.AGENTE_COMPLETO,
            modelo_roteirizado([MULTA, "FINAL: R$ 1030,00."], prompts),
            historico=[("quanto fica a multa?", "Qual o valor da fatura?")],
            estado=json.loads(json.dumps(primeiro.estado)),
        )
        self.assertEqual((segundo.tipo, segundo.resposta), ("final", "R$ 1030,00."))
        self.assertIn("executada: ok", segundo.trajetoria[0])
        self.assertIn("não precisa relê-lo", prompts[0])
        self.assertIn("valor_fatura", prompts[0])  # a descrição já lida volta no prompt

    def test_sem_estado_o_segundo_turno_volta_a_exigir_leitura(self):
        resultado = turno([MULTA, "LER:", "FINAL: ok"], apoio.n2_financeiro())
        self.assertIn("ferramenta não lida", resultado.trajetoria[0])

    def test_estado_adulterado_nao_libera_nada(self):
        estado = {"indice_lido": True, "ferramentas_lidas": ["financeiro/consultar_transacoes_cliente"]}
        resultado = turno(
            ['USAR: consultar_transacoes_cliente | {"id_cliente": "CLI-0001"}', "FINAL: ok"],
            apoio.n1_dados(),
            estado=estado,
        )
        self.assertIn("ferramenta não lida", resultado.trajetoria[0])
        self.assertEqual(governanca.REGISTROS, [])
        for ruim in ("texto", 7, {"indice_lido": "sim"}, {"indice_lido": True, "ferramentas_lidas": 3}):
            turno(["FINAL: x", "LER:", "FINAL: ok"], apoio.n2_financeiro(), estado=ruim)

    def test_historico_entra_no_prompt(self):
        prompts = []
        turno(
            INDICE + ["FINAL: ok"],
            apoio.n2_financeiro(),
            historico=[("oi", "Olá, como posso ajudar?"), ("e a multa?", "Qual a fatura?")],
            prompts=prompts,
        )
        self.assertIn("Funcionário: oi", prompts[0])
        self.assertIn("Assistente: Qual a fatura?", prompts[0])
        self.assertTrue(prompts[0].endswith("Pergunta do funcionário: pergunta de teste"))

    def test_historico_longo_mantem_so_os_ultimos_turnos(self):
        historico = [(f"p{n:02d}", f"r{n:02d}") for n in range(agente.MAX_TURNOS_HISTORICO + 3)]
        prompts = []
        turno(["FINAL: x", "LER:", "FINAL: ok"], apoio.n2_financeiro(), historico=historico, prompts=prompts)
        self.assertNotIn("p02", prompts[0])
        self.assertIn("p03", prompts[0])

    def test_ferramentas_do_agente_por_parametro_sao_respeitadas(self):
        linhas = INDICE + [LER_MULTA, MULTA, "FINAL: sem acesso"]
        resultado = turno(linhas, apoio.n2_financeiro(), ferramentas=("consultar_endereco_cep",))
        self.assertIn("não encontrado", resultado.trajetoria[1])
        self.assertIn("ferramenta não lida", resultado.trajetoria[2])
        self.assertEqual(governanca.REGISTROS, [])


class TestLimitesKan38(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_dez_passos_e_o_teto(self):
        self.assertEqual(agente.MAX_PASSOS, 10)
        chamadas = []
        resultado = agente.rodar_turno(
            "p", apoio.n2_financeiro(), apoio.AGENTE_COMPLETO, lambda sistema, p: chamadas.append(p) or "LER:"
        )
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "max_passos"))
        self.assertEqual(len(chamadas), 10)
        self.assertEqual(len(resultado.trajetoria), 10)
        self.assertIn("Não consegui concluir", resultado.resposta)

    def test_formato_invalido_tambem_gasta_passo(self):
        resultado = turno(["blá"] * 10, apoio.n2_financeiro())
        self.assertEqual(resultado.motivo, "max_passos")

    def test_mesma_ferramenta_e_argumentos_tres_vezes_para(self):
        linhas = INDICE + [LER_MULTA, MULTA, MULTA, MULTA, "FINAL: nunca"]
        resultado = turno(linhas, apoio.n2_financeiro())
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "repeticao"))
        self.assertIn("3 vezes seguidas", resultado.resposta)
        self.assertEqual(len(governanca.REGISTROS), 2)  # a 3ª tentativa não chega a executar
        self.assertIn("limite", resultado.trajetoria[-1])

    def test_ordem_das_chaves_nao_escapa_da_deteccao(self):
        outra = 'USAR: calcular_multa_atraso | {"dias_atraso": 30, "valor_fatura": 1000}'
        linhas = INDICE + [LER_MULTA, MULTA, outra, MULTA, "FINAL: nunca"]
        self.assertEqual(turno(linhas, apoio.n2_financeiro()).motivo, "repeticao")

    def test_argumentos_diferentes_nao_contam_como_repeticao(self):
        outra = 'USAR: calcular_multa_atraso | {"valor_fatura": 2000, "dias_atraso": 30}'
        linhas = INDICE + [LER_MULTA, MULTA, MULTA, outra, MULTA, MULTA, "FINAL: ok"]
        resultado = turno(linhas, apoio.n2_financeiro())
        self.assertEqual(resultado.tipo, "final")


class RegistroDeLogs(unittest.TestCase):
    """Captura o que o agente manda para o logging."""

    def setUp(self):
        apoio.limpar()
        self.mensagens = []
        teste = self

        class Captura(logging.Handler):
            def emit(self, registro):
                teste.mensagens.append(registro.getMessage())

        self.captura = Captura(level=logging.DEBUG)
        agente.logger.addHandler(self.captura)
        self.nivel_antigo = agente.logger.level
        agente.logger.setLevel(logging.DEBUG)
        self.addCleanup(agente.logger.removeHandler, self.captura)
        self.addCleanup(agente.logger.setLevel, self.nivel_antigo)


class TestLgpd(RegistroDeLogs):
    def test_argumentos_dados_e_resposta_do_funcionario_nao_vazam(self):
        cliente = f'USAR: consultar_cliente | {{"id_cliente": "{CANARIO}"}}'
        pergunta = f"PERGUNTAR: confirma o cliente {CANARIO}?"
        linhas = [
            "PENSAMENTO: preciso do cliente " + CANARIO + "\nLER:",
            f"LER: atendimento/{CANARIO}",
            "LER: atendimento/consultar_cliente",
            cliente,
            pergunta,
        ]
        usuario = apoio.n1_atendimento()
        primeiro = turno(linhas, usuario)
        segundo = agente.rodar_turno(
            f"sim, {CANARIO}",
            usuario,
            apoio.AGENTE_COMPLETO,
            modelo_roteirizado([f"FINAL: nada para {CANARIO}"]),
            historico=[("quero ver o cliente", primeiro.resposta)],
            estado=primeiro.estado,
        )
        self.assertEqual(primeiro.tipo, "pergunta")
        self.assertIn(CANARIO, segundo.resposta)  # a resposta ao próprio usuário pode ter o dado
        saidas = primeiro.trajetoria + segundo.trajetoria + self.mensagens
        self.assertTrue(self.mensagens)
        for texto in saidas:
            self.assertNotIn(CANARIO, texto)
        self.assertNotIn(CANARIO, json.dumps(primeiro.estado))
        self.assertNotIn(CANARIO, json.dumps(governanca.REGISTROS))

    def test_logs_trazem_metadados(self):
        turno(
            INDICE + [LER_MULTA, MULTA, "FINAL: ok"],
            apoio.n2_financeiro(),
            contexto={"execucao_id": "exec-7"},
        )
        todas = "\n".join(self.mensagens)
        self.assertIn("execucao_id=exec-7", todas)
        self.assertIn("alvo=calcular_multa_atraso", todas)
        self.assertIn("executada: ok", todas)
        self.assertNotIn("1000", todas)

    def test_resposta_crua_do_modelo_fora_do_formato_nao_vai_para_o_log(self):
        turno([f"o CPF é {CANARIO}", "LER:", "FINAL: ok"], apoio.n2_financeiro())
        self.assertNotIn(CANARIO, "\n".join(self.mensagens))


class TestEntradasHostis(RegistroDeLogs):
    """Auditoria A1-A3: MED-2, MED-3, BAIXO-4, BAIXO-5 e BAIXO-6."""

    def test_json_aninhado_demais_vira_argumento_invalido_e_o_turno_termina(self):
        fundo = "[" * 100_000
        linhas = INDICE + [LER_MULTA, f"USAR: calcular_multa_atraso | {fundo}", "FINAL: ok"]
        resultado = turno(linhas, apoio.n2_financeiro())
        self.assertEqual((resultado.tipo, resultado.resposta), ("final", "ok"))
        self.assertIn("argumentos inválidos", resultado.trajetoria[2])
        self.assertEqual(governanca.REGISTROS, [])
        self.assertIn("turno encerrado", self.mensagens[-1])

    def test_json_aninhado_demais_sem_ler_a_ferramenta_tambem_nao_derruba(self):
        linhas = INDICE + [f"USAR: calcular_multa_atraso | {'[' * 100_000}", "FINAL: ok"]
        resultado = turno(linhas, apoio.n2_financeiro())
        self.assertEqual(resultado.tipo, "final")
        self.assertIn("ferramenta não lida", resultado.trajetoria[1])

    def test_alvo_do_log_so_aceita_nome_do_catalogo(self):
        cpf = "12345678909"
        linhas = INDICE + [f"LER: {cpf}", f"LER: atendimento/{cpf}", f"USAR: cpf_{cpf} | {{}}", "FINAL: ok"]
        resultado = turno(linhas, apoio.n2_financeiro())
        self.assertEqual(resultado.tipo, "final")
        saidas = resultado.trajetoria + self.mensagens
        self.assertTrue(any("alvo=<desconhecido>" in texto for texto in saidas))
        for texto in saidas:
            self.assertNotIn(cpf, texto)

    def test_alvo_conhecido_continua_aparecendo(self):
        for caminho in ("financeiro", "financeiro/calcular_multa_atraso", "calcular_multa_atraso"):
            self.assertEqual(agente._alvo_seguro(caminho), caminho)
        for caminho in ("", "financeiro/", "a/b/c", "Financeiro", "financeiro/12345678909"):
            self.assertEqual(agente._alvo_seguro(caminho), "<desconhecido>")

    def test_repeticao_nao_loga_nome_de_ferramenta_inventado(self):
        inventada = 'USAR: cpf_12345678909 | {}'
        resultado = turno(INDICE + [inventada] * 3 + ["FINAL: nunca"], apoio.n2_financeiro())
        self.assertEqual(resultado.motivo, "repeticao")
        self.assertNotIn("12345678909", "\n".join(self.mensagens))

    def test_pergunta_gigante_e_cortada_no_limite(self):
        prompts = []
        enorme = "x" * (agente.MAX_CHARS_PERGUNTA * 50)
        agente.rodar_turno(
            enorme, apoio.n2_financeiro(), apoio.AGENTE_COMPLETO,
            modelo_roteirizado(["FINAL: x", "LER:", "FINAL: ok"], prompts),
        )
        self.assertLess(len(prompts[0]), agente.MAX_CHARS_PERGUNTA + 200)
        self.assertIn("pergunta cortada pelo sistema", prompts[0])
        self.assertIn("pergunta cortada", "\n".join(self.mensagens))

    def test_pergunta_dentro_do_limite_vai_inteira(self):
        prompts = []
        texto = "y" * agente.MAX_CHARS_PERGUNTA
        agente.rodar_turno(
            texto, apoio.n2_financeiro(), apoio.AGENTE_COMPLETO,
            modelo_roteirizado(["FINAL: x", "LER:", "FINAL: ok"], prompts),
        )
        self.assertIn(texto, prompts[0])
        self.assertNotIn("cortada", prompts[0])

    def test_resposta_do_modelo_que_nao_e_texto_e_resposta_invalida(self):
        for estranha in (None, 123, ["FINAL: x"], b"FINAL: x"):
            apoio.limpar()
            resultado = agente.rodar_turno(
                "p",
                apoio.n2_financeiro(),
                apoio.AGENTE_COMPLETO,
                modelo_roteirizado([estranha, "LER:", "FINAL: ok"]),
            )
            self.assertEqual((resultado.tipo, resultado.resposta), ("final", "ok"))
            self.assertIn("fora do formato", resultado.trajetoria[0])

    def test_execucao_id_com_quebra_de_linha_nao_chega_ao_log(self):
        falso = "abc\nFAKE LINHA passo=9 acao=FINAL"
        resultado = turno(
            INDICE + [LER_MULTA, MULTA, "FINAL: ok"],
            apoio.n2_financeiro(),
            contexto={"execucao_id": falso, "agente_id": "x" * 10_000},
        )
        self.assertEqual(resultado.tipo, "final")
        texto = "\n".join(self.mensagens) + json.dumps(governanca.REGISTROS)
        self.assertNotIn("FAKE", texto)
        self.assertNotIn("xxxxxxxx", texto)
        self.assertEqual(governanca.REGISTROS[-1]["agente_id"], agente.AGENTE_ID)
        self.assertTrue(agente.IDENTIFICADOR_SEGURO_RE.match(governanca.REGISTROS[-1]["execucao_id"]))

    def test_identificadores_normais_sao_mantidos(self):
        for valor in ("exec-42", "agente_x", uuid4().hex, str(uuid4())):
            self.assertEqual(agente._identificador_seguro(valor, "padrao"), valor)
        for valor in (None, "", "a b", "a\nb", "x" * 65):
            self.assertEqual(agente._identificador_seguro(valor, "padrao"), "padrao")


class TestModoTerminal(unittest.TestCase):
    def test_pergunta_vira_input_e_o_turno_seguinte_continua(self):
        apoio.limpar()
        modelo = modelo_roteirizado(
            INDICE + [LER_MULTA, "PERGUNTAR: Qual a fatura?", MULTA, "FINAL: R$ 1030,00."]
        )
        digitado = iter(["quanto fica a multa?", "1000 e 30 dias", "sair"])
        saida = io.StringIO()
        with (
            mock.patch.object(agente, "chamar_llm", modelo),
            mock.patch("builtins.input", lambda *_: next(digitado)),
            contextlib.redirect_stdout(saida),
        ):
            agente.conversar_no_terminal(apoio.n2_financeiro())
        self.assertIn("Agente: Qual a fatura?", saida.getvalue())
        self.assertIn("Agente: R$ 1030,00.", saida.getvalue())
        self.assertIn("PERGUNTAR -> aguardando o funcionário", saida.getvalue())


class TestUsuarioDoAmbiente(unittest.TestCase):
    """O12: o modo terminal lê só ID_USUARIO; o perfil vem do diretório."""

    def test_so_o_id_vai_para_a_busca_no_diretorio(self):
        pedidos = []

        def diretorio(id_usuario):
            pedidos.append(id_usuario)
            return apoio.n2_financeiro()

        ambiente = {"ID_USUARIO": " USR-9 ", "NIVEL": "N2", "AREA": "dados", "CARTEIRA": "CLI-1"}
        usuario = agente.usuario_do_ambiente(ambiente, diretorio)
        self.assertEqual(pedidos, ["USR-9"])
        self.assertEqual((usuario.nivel, usuario.area, usuario.carteira), ("N2", "financeiro", ()))

    def test_nivel_area_e_carteira_do_ambiente_sao_ignorados(self):
        apenas_id = agente.usuario_do_ambiente({"ID_USUARIO": "USR-9"}, lambda _: apoio.n1_atendimento())
        com_extras = agente.usuario_do_ambiente(
            {"ID_USUARIO": "USR-9", "NIVEL": "N2", "AREA": "financeiro", "CARTEIRA": "CLI-9"},
            lambda _: apoio.n1_atendimento(),
        )
        self.assertEqual(
            (apenas_id.nivel, apenas_id.area, apenas_id.carteira),
            (com_extras.nivel, com_extras.area, com_extras.carteira),
        )

    def test_id_ausente_invalido_ou_desconhecido_nao_sobe(self):
        for ambiente in ({}, {"ID_USUARIO": ""}, {"ID_USUARIO": "a b"}, {"ID_USUARIO": "x\ny"}):
            with self.assertRaises(ValueError):
                agente.usuario_do_ambiente(ambiente, lambda _: apoio.n2_financeiro())
        with self.assertRaises(ValueError):
            agente.usuario_do_ambiente({"ID_USUARIO": "USR-404"}, lambda _: None)

    def test_ponto_de_ligacao_com_o_diretorio_ainda_nao_existe(self):
        with self.assertRaises(NotImplementedError):
            agente.usuario_do_ambiente({"ID_USUARIO": "USR-1"})


class TestEnvExample(unittest.TestCase):
    def test_env_example_sem_perfil_do_funcionario_e_com_url_do_modelo(self):
        raiz = Path(__file__).resolve().parents[2]
        chaves = {
            linha.split("=")[0].strip()
            for linha in (raiz / ".env.example").read_text(encoding="utf-8").splitlines()
            if "=" in linha and not linha.lstrip().startswith("#")
        }
        self.assertTrue({"ID_USUARIO", "LLM_URL", "LLM_MODELO"} <= chaves)
        self.assertFalse(chaves & {"NIVEL", "AREA", "CARTEIRA"})


class TestConfiguracaoDoModelo(unittest.TestCase):
    def test_url_do_modelo_nao_tem_valor_no_codigo(self):
        with mock.patch.object(agente, "LLM_URL", ""), self.assertRaises(RuntimeError):
            agente.chamar_llm("sistema", "prompt")
        codigo = Path(agente.__file__).read_text(encoding="utf-8")
        self.assertNotIn("https://", codigo)


if __name__ == "__main__":
    unittest.main()
