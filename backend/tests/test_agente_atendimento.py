import json
import logging
import unittest
from uuid import uuid4

import requests
from agentes.agente_atendimento import agente
from ferramentas import governanca

from . import apoio_agente as apoio
from .apoio_agente import modelo_roteirizado

MULTA = 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}'
CLIENTE_FORA = 'USAR: consultar_cliente | {"id_cliente": "M00002"}'


CANARIO = "CANARIO-123"
INDICE = ["LER:"]
LER_MULTA = "LER: financeiro/calcular_multa_atraso"


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
        final, trajetoria = rodar(linhas, apoio.coordenador_financeiro())
        self.assertEqual(final, "R$ 1030,00.")
        self.assertEqual(len(trajetoria), 5)
        registro = governanca.REGISTROS[-1]
        self.assertEqual(registro["agente_id"], agente.AGENTE_ID)
        self.assertEqual(registro["ferramenta"], "calcular_multa_atraso")
        self.assertEqual(registro["passo"], 4)
        self.assertIsNone(registro["tipo_erro"])
        self.assertTrue(registro["execucao_id"])

    def test_usar_sem_ler_a_ferramenta_e_bloqueado(self):
        _, trajetoria = rodar(["LER:", MULTA, "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertIn("ferramenta não lida", trajetoria[1])
        self.assertTrue(apoio.so_recusas_do_agente())

    def test_usar_sem_ler_deixa_registro_da_recusa_sem_argumentos(self):
        """MED-2 da auditoria B: a tentativa barrada pelo agente também fica no registro."""
        _, trajetoria = rodar(
            ["LER:", 'USAR: calcular_multa_atraso | {"valor_fatura": 987654}', "FINAL: ok"],
            apoio.coordenador_financeiro(),
        )
        self.assertIn("ferramenta não lida", trajetoria[1])  # a resposta à pessoa não mudou
        self.assertEqual(len(governanca.REGISTROS), 1)
        registro = governanca.REGISTROS[0]
        self.assertEqual(
            (registro["ferramenta"], registro["status"], registro["camada_bloqueio"], registro["passo"]),
            ("calcular_multa_atraso", "erro", "agente", 2),
        )
        self.assertEqual(registro["agente_id"], agente.AGENTE_ID)
        self.assertNotIn("987654", json.dumps(governanca.REGISTROS))

    def test_usar_nome_inexistente_sem_ler_registra_sem_expor_o_nome(self):
        rodar(["LER:", "USAR: nome_inventado | {}", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertEqual([r["ferramenta"] for r in governanca.REGISTROS], ["inexistente"])

    def test_registro_indisponivel_nao_muda_a_recusa(self):
        governanca.adicionar_destino(lambda registro: 1 / 0)
        _, trajetoria = rodar(["LER:", MULTA, "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertIn("ferramenta não lida", trajetoria[1])

    def test_ler_caminho_antes_do_indice_e_bloqueado(self):
        _, trajetoria = rodar(["LER: financeiro", "LER:", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertIn("índice não lido", trajetoria[0])

    def test_final_sem_consultar_o_indice_e_recusado(self):
        final, trajetoria = rodar(["FINAL: oi", "LER:", "FINAL: ok"], apoio.coordenador_financeiro())
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
            return rodar(linhas, apoio.analista_cobranca())[1]

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
        _, trajetoria = rodar(linhas, apoio.atendente_n1())
        self.assertIn("permissao_negada", trajetoria[3])
        registro = governanca.REGISTROS[-1]
        self.assertEqual(registro["tipo_erro"], "permissao_negada")
        self.assertNotIn("M00002", json.dumps(registro))

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
            _, trajetoria = rodar(linhas, apoio.coordenador_financeiro())
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
        final, trajetoria = rodar(linhas, apoio.coordenador_financeiro())
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
        _, trajetoria = rodar(linhas, apoio.coordenador_financeiro())
        self.assertIn("argumentos inválidos", trajetoria[2])

    def test_resposta_fora_do_formato_nao_derruba_o_loop(self):
        final, trajetoria = rodar(["blá blá", "LER:", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertEqual(final, "ok")
        self.assertIn("fora do formato", trajetoria[0])

    def test_texto_na_linha_de_baixo_nao_vira_caminho(self):
        final, _ = rodar(["LER:\ntexto solto", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertEqual(final, "ok")

    def test_estouro_de_passos_devolve_mensagem_padrao(self):
        final, trajetoria = agente.agente(
            "pergunta", apoio.coordenador_financeiro(), lambda prompt_sistema, prompt: "LER:"
        )
        self.assertIn("Não consegui concluir", final)
        self.assertEqual(len(trajetoria), agente.MAX_PASSOS)

    def test_agente_usa_as_ferramentas_recebidas_por_parametro(self):
        linhas = ["LER:", LER_MULTA, MULTA, "FINAL: ok"]
        final, _ = agente.agente(
            "p", apoio.coordenador_financeiro(), modelo_roteirizado(linhas), ("calcular_multa_atraso",)
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

        resultado = agente.rodar_turno("p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo)
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
            "p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo, prompt_sistema="outro"
        )
        self.assertEqual(set(recebidos), {"outro"})

class TestTurno(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_final_devolve_turno_com_estado_em_json(self):
        resultado = turno(INDICE + [LER_MULTA, MULTA, "FINAL: R$ 1030,00."], apoio.coordenador_financeiro())
        self.assertEqual((resultado.tipo, resultado.resposta), ("final", "R$ 1030,00."))
        self.assertIsNone(resultado.motivo)
        self.assertEqual(
            json.loads(json.dumps(resultado.estado)),
            {"indice_lido": True, "ferramentas_lidas": ["financeiro/calcular_multa_atraso"]},
        )

    def test_contexto_define_execucao_e_agente_no_registro(self):
        contexto = {"execucao_id": "exec-42", "agente_id": "agente_x"}
        turno(INDICE + [LER_MULTA, MULTA, "FINAL: ok"], apoio.coordenador_financeiro(), contexto=contexto)
        registro = governanca.REGISTROS[-1]
        self.assertEqual((registro["execucao_id"], registro["agente_id"]), ("exec-42", "agente_x"))

    def test_sem_contexto_gera_execucao_id(self):
        turno(INDICE + [LER_MULTA, MULTA, "FINAL: ok"], apoio.coordenador_financeiro())
        registro = governanca.REGISTROS[-1]
        self.assertTrue(registro["execucao_id"])
        self.assertEqual(registro["agente_id"], agente.AGENTE_ID)

    def test_perguntar_encerra_o_turno_sem_input(self):
        pergunta = "PERGUNTAR: Qual é o código do cliente?"
        resultado = turno(INDICE + [pergunta, "FINAL: nunca chega aqui"], apoio.atendente_n1())
        self.assertEqual((resultado.tipo, resultado.resposta), ("pergunta", "Qual é o código do cliente?"))
        self.assertEqual(len(resultado.trajetoria), 2)
        self.assertTrue(resultado.estado["indice_lido"])

    def test_estado_permite_continuar_sem_reler_o_indice(self):
        usuario = apoio.coordenador_financeiro()
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
        resultado = turno([MULTA, "LER:", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertIn("ferramenta não lida", resultado.trajetoria[0])

    def test_estado_adulterado_nao_libera_nada(self):
        estado = {"indice_lido": True, "ferramentas_lidas": ["financeiro/consultar_transacoes_cliente"]}
        resultado = turno(
            ['USAR: consultar_transacoes_cliente | {"id_cliente": "M00001"}', "FINAL: ok"],
            apoio.analista_cobranca(),
            estado=estado,
        )
        self.assertIn("ferramenta não lida", resultado.trajetoria[0])
        self.assertTrue(apoio.so_recusas_do_agente())
        for ruim in ("texto", 7, {"indice_lido": "sim"}, {"indice_lido": True, "ferramentas_lidas": 3}):
            turno(["FINAL: x", "LER:", "FINAL: ok"], apoio.coordenador_financeiro(), estado=ruim)

    def test_historico_entra_no_prompt(self):
        prompts = []
        turno(
            INDICE + ["FINAL: ok"],
            apoio.coordenador_financeiro(),
            historico=[("oi", "Olá, como posso ajudar?"), ("e a multa?", "Qual a fatura?")],
            prompts=prompts,
        )
        self.assertIn("Funcionário: oi", prompts[0])
        self.assertIn("Assistente: Qual a fatura?", prompts[0])
        self.assertTrue(prompts[0].endswith("Pergunta do funcionário: pergunta de teste"))

    def test_historico_longo_mantem_so_os_ultimos_turnos(self):
        historico = [(f"p{n:02d}", f"r{n:02d}") for n in range(agente.MAX_TURNOS_HISTORICO + 3)]
        prompts = []
        turno(["FINAL: x", "LER:", "FINAL: ok"], apoio.coordenador_financeiro(), historico=historico, prompts=prompts)
        self.assertNotIn("p02", prompts[0])
        self.assertIn("p03", prompts[0])

    def test_ferramentas_do_agente_por_parametro_sao_respeitadas(self):
        linhas = INDICE + [LER_MULTA, MULTA, "FINAL: sem acesso"]
        resultado = turno(linhas, apoio.coordenador_financeiro(), ferramentas=("consultar_endereco_cep",))
        self.assertIn("não encontrado", resultado.trajetoria[1])
        self.assertIn("ferramenta não lida", resultado.trajetoria[2])
        self.assertTrue(apoio.so_recusas_do_agente())


class TestLimitesKan38(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_dez_passos_e_o_teto(self):
        self.assertEqual(agente.MAX_PASSOS, 10)
        chamadas = []
        resultado = agente.rodar_turno(
            "p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, lambda sistema, p: chamadas.append(p) or "LER:"
        )
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "max_passos"))
        self.assertEqual(len(chamadas), 10)
        self.assertEqual(len(resultado.trajetoria), 10)
        self.assertIn("Não consegui concluir", resultado.resposta)

    def test_formato_invalido_tambem_gasta_passo(self):
        resultado = turno(["blá"] * 10, apoio.coordenador_financeiro())
        self.assertEqual(resultado.motivo, "max_passos")

    def test_mesma_ferramenta_e_argumentos_tres_vezes_para(self):
        linhas = INDICE + [LER_MULTA, MULTA, MULTA, MULTA, "FINAL: nunca"]
        resultado = turno(linhas, apoio.coordenador_financeiro())
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "repeticao"))
        self.assertIn("3 vezes seguidas", resultado.resposta)
        self.assertEqual(len(governanca.REGISTROS), 2)  # a 3ª tentativa não chega a executar
        self.assertIn("limite", resultado.trajetoria[-1])

    def test_ordem_das_chaves_nao_escapa_da_deteccao(self):
        outra = 'USAR: calcular_multa_atraso | {"dias_atraso": 30, "valor_fatura": 1000}'
        linhas = INDICE + [LER_MULTA, MULTA, outra, MULTA, "FINAL: nunca"]
        self.assertEqual(turno(linhas, apoio.coordenador_financeiro()).motivo, "repeticao")

    def test_argumentos_diferentes_nao_contam_como_repeticao(self):
        outra = 'USAR: calcular_multa_atraso | {"valor_fatura": 2000, "dias_atraso": 30}'
        linhas = INDICE + [LER_MULTA, MULTA, MULTA, outra, MULTA, MULTA, "FINAL: ok"]
        resultado = turno(linhas, apoio.coordenador_financeiro())
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


def modelo_lento(linhas, relogio, segundos_por_chamada, tempos=None):
    """Modelo roteirizado que gasta `segundos_por_chamada` do relógio falso e anota o `tempo_limite`."""
    respostas = iter(linhas)

    def chamar(prompt_sistema, prompt, tempo_limite=None):
        if tempos is not None:
            tempos.append(tempo_limite)
        relogio.passar(segundos_por_chamada)
        return next(respostas)

    return chamar


class TestLimiteDeTempo(RegistroDeLogs):
    """P1 da crítica B: prazo total por turno, com relógio injetado (sem sleep)."""

    def setUp(self):
        super().setUp()
        self.relogio = apoio.RelogioFalso()

    def rodar(self, linhas, segundos_por_chamada, contexto=None, pergunta="pergunta de teste", tempos=None):
        modelo = modelo_lento(linhas, self.relogio, segundos_por_chamada, tempos)
        return agente.rodar_turno(
            pergunta, apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo,
            contexto=contexto, relogio=self.relogio,
        )

    def test_o_prazo_padrao_e_uma_constante_nomeada(self):
        self.assertEqual(agente.SEGUNDOS_POR_TURNO, 120)

    def test_estourar_o_prazo_termina_em_limite_tempo(self):
        resultado = self.rodar(["LER:"] * 10, segundos_por_chamada=50)
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "tempo"))
        self.assertEqual(resultado.resposta, agente.MENSAGEM_LIMITE_TEMPO)
        self.assertIn("tempo do turno esgotado", resultado.trajetoria[-1])
        self.assertEqual(len(resultado.trajetoria), 3)  # 2 passos de 50 s e o 3º, que passou de 120 s

    def test_o_motivo_de_tempo_nao_se_confunde_com_o_de_passos(self):
        resultado = self.rodar(["LER:"] * 10, segundos_por_chamada=1)
        self.assertEqual(resultado.motivo, "max_passos")

    def test_prazo_de_contexto_vale_no_lugar_do_padrao(self):
        resultado = self.rodar(["LER:"] * 10, 5, contexto={"segundos_por_turno": 12})
        self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "tempo"))

    def test_prazo_invalido_no_contexto_volta_ao_padrao(self):
        for valor in (0, -5, True, "30", None, float("inf"), float("nan")):
            with self.subTest(valor=valor):
                self.assertEqual(agente._segundos_do_turno({"segundos_por_turno": valor}), 120)
        self.assertEqual(agente._segundos_do_turno({"segundos_por_turno": 7.5}), 7.5)

    def test_prazo_acima_do_teto_volta_ao_padrao(self):
        self.assertEqual(agente.SEGUNDOS_MAXIMOS_POR_TURNO, 600)
        for valor in (601, 1e308, 10**12):
            with self.subTest(valor=valor):
                self.assertEqual(agente._segundos_do_turno({"segundos_por_turno": valor}), 120)
        self.assertEqual(agente._segundos_do_turno({"segundos_por_turno": 600}), 600)

    def test_o_modelo_recebe_o_tempo_que_sobra_como_timeout(self):
        tempos = []
        self.rodar(["LER:"] * 10, 50, tempos=tempos)
        self.assertEqual(tempos, [120, 70, 20])

    def test_modelo_sem_o_parametro_tempo_limite_continua_funcionando(self):
        chamadas = []

        def modelo(prompt_sistema, prompt):
            chamadas.append(prompt)
            self.relogio.passar(60)
            return "LER:"

        resultado = agente.rodar_turno(
            "p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo, relogio=self.relogio
        )
        self.assertEqual(resultado.motivo, "tempo")
        self.assertEqual(len(chamadas), 2)

    def test_resposta_que_chega_depois_do_prazo_nao_vira_acao(self):
        linhas = ["LER:", LER_MULTA, MULTA, "FINAL: nunca"]
        resultado = self.rodar(linhas, 40)  # a 3ª chamada termina em 120 s: a ferramenta não roda
        self.assertEqual(resultado.motivo, "tempo")
        self.assertEqual(governanca.REGISTROS, [])

    def test_o_limite_de_tempo_nao_expoe_conteudo(self):
        resultado = self.rodar(["LER:"] * 10, 50, pergunta=f"{CANARIO} do lojista")
        saidas = [resultado.resposta, *resultado.trajetoria, *self.mensagens]
        self.assertTrue(any("tempo" in saida for saida in self.mensagens))
        self.assertNotIn(CANARIO, "\n".join(saidas))


URL_DO_MODELO = "https://modelo-secreto.exemplo.invalid"


def modelo_que_falha(erro):
    def chamar(prompt_sistema, prompt):
        raise erro

    return chamar


class TestModeloIndisponivel(RegistroDeLogs):
    """BAIXO-2 da auditoria B: falha do modelo não sobe, e a URL dele nunca aparece."""

    def rodar_com_falha(self, erro):
        modelo = modelo_que_falha(erro)
        return agente.rodar_turno(
            "pergunta de teste", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo
        )

    def test_excecao_do_modelo_vira_limite_sem_subir(self):
        for erro in (
            ConnectionError(f"falha ao conectar em {URL_DO_MODELO}/api/generate"),
            TimeoutError(URL_DO_MODELO),
            requests.exceptions.ReadTimeout(f"{URL_DO_MODELO} demorou"),
            RuntimeError("qualquer outra falha"),
        ):
            with self.subTest(erro=type(erro).__name__):
                resultado = self.rodar_com_falha(erro)
                self.assertEqual((resultado.tipo, resultado.motivo), ("limite", "modelo_indisponivel"))
                self.assertEqual(resultado.resposta, agente.MENSAGEM_MODELO_INDISPONIVEL)
                self.assertIn("modelo indisponível", resultado.trajetoria[-1])

    def test_a_url_nao_aparece_em_resposta_trajetoria_nem_log_e_o_log_so_tem_o_tipo(self):
        erro = ConnectionError(f"Max retries exceeded with url: {URL_DO_MODELO}/api/generate")
        resultado = self.rodar_com_falha(erro)
        saidas = "\n".join([resultado.resposta, *resultado.trajetoria, *self.mensagens])
        self.assertNotIn("modelo-secreto", saidas)
        self.assertNotIn("Max retries", saidas)
        self.assertTrue(any("tipo_erro=ConnectionError" in linha for linha in self.mensagens))

    def test_falha_depois_do_prazo_conta_como_tempo(self):
        relogio = apoio.RelogioFalso()

        def modelo(prompt_sistema, prompt):
            relogio.passar(130)
            raise TimeoutError(URL_DO_MODELO)

        resultado = agente.rodar_turno(
            "p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, modelo, relogio=relogio
        )
        self.assertEqual(resultado.motivo, "tempo")

class TestLimitacoesConhecidas(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_alternar_duas_chamadas_nao_aciona_a_regra_de_repeticao(self):
        """KAN-69 A-11 (aceita): só o teto de passos para o laço A, B, A, B."""
        outra = 'USAR: calcular_multa_atraso | {"valor_fatura": 2000, "dias_atraso": 30}'
        linhas = INDICE + [LER_MULTA] + [MULTA, outra] * 4
        resultado = turno(linhas, apoio.coordenador_financeiro())
        self.assertEqual(resultado.motivo, "max_passos")

    def test_indice_lido_forjado_so_economiza_o_passo_e_nao_libera_nada(self):
        forjado = {"indice_lido": True, "ferramentas_lidas": ["financeiro/consultar_transacoes_cliente"]}
        linhas = [
            'USAR: consultar_transacoes_cliente | {"id_cliente": "M00001"}',
            "FINAL: sem acesso",
        ]
        resultado = turno(linhas, apoio.analista_cobranca(), estado=forjado)
        self.assertEqual(resultado.tipo, "final")  # pulou o índice
        self.assertIn("ferramenta não lida", resultado.trajetoria[0])
        self.assertTrue(apoio.so_recusas_do_agente())
        self.assertEqual(resultado.estado["ferramentas_lidas"], [])


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
        usuario = apoio.atendente_n1()
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
            apoio.coordenador_financeiro(),
            contexto={"execucao_id": "exec-7"},
        )
        todas = "\n".join(self.mensagens)
        self.assertIn("execucao_id=exec-7", todas)
        self.assertIn("alvo=calcular_multa_atraso", todas)
        self.assertIn("executada: ok", todas)
        self.assertNotIn("1000", todas)

    def test_resposta_crua_do_modelo_fora_do_formato_nao_vai_para_o_log(self):
        turno([f"o CPF é {CANARIO}", "LER:", "FINAL: ok"], apoio.coordenador_financeiro())
        self.assertNotIn(CANARIO, "\n".join(self.mensagens))


class TestEntradasHostis(RegistroDeLogs):
    """Auditoria A1-A3: MED-2, MED-3, BAIXO-4, BAIXO-5 e BAIXO-6."""

    def test_json_aninhado_demais_vira_argumento_invalido_e_o_turno_termina(self):
        fundo = "[" * 100_000
        linhas = INDICE + [LER_MULTA, f"USAR: calcular_multa_atraso | {fundo}", "FINAL: ok"]
        resultado = turno(linhas, apoio.coordenador_financeiro())
        self.assertEqual((resultado.tipo, resultado.resposta), ("final", "ok"))
        self.assertIn("argumentos inválidos", resultado.trajetoria[2])
        self.assertTrue(apoio.so_recusas_do_agente())
        self.assertIn("turno encerrado", self.mensagens[-1])

    def test_json_aninhado_demais_sem_ler_a_ferramenta_tambem_nao_derruba(self):
        linhas = INDICE + [f"USAR: calcular_multa_atraso | {'[' * 100_000}", "FINAL: ok"]
        resultado = turno(linhas, apoio.coordenador_financeiro())
        self.assertEqual(resultado.tipo, "final")
        self.assertIn("ferramenta não lida", resultado.trajetoria[1])

    def test_alvo_do_log_so_aceita_nome_do_catalogo(self):
        cpf = "12345678909"
        linhas = INDICE + [f"LER: {cpf}", f"LER: atendimento/{cpf}", f"USAR: cpf_{cpf} | {{}}", "FINAL: ok"]
        resultado = turno(linhas, apoio.coordenador_financeiro())
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
        resultado = turno(INDICE + [inventada] * 3 + ["FINAL: nunca"], apoio.coordenador_financeiro())
        self.assertEqual(resultado.motivo, "repeticao")
        self.assertNotIn("12345678909", "\n".join(self.mensagens))

    def test_pergunta_gigante_e_cortada_no_limite(self):
        prompts = []
        enorme = "x" * (agente.MAX_CHARS_PERGUNTA * 50)
        agente.rodar_turno(
            enorme, apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO,
            modelo_roteirizado(["FINAL: x", "LER:", "FINAL: ok"], prompts),
        )
        self.assertLess(len(prompts[0]), agente.MAX_CHARS_PERGUNTA + 200)
        self.assertIn("pergunta cortada pelo sistema", prompts[0])
        self.assertIn("pergunta cortada", "\n".join(self.mensagens))

    def test_pergunta_dentro_do_limite_vai_inteira(self):
        prompts = []
        texto = "y" * agente.MAX_CHARS_PERGUNTA
        agente.rodar_turno(
            texto, apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO,
            modelo_roteirizado(["FINAL: x", "LER:", "FINAL: ok"], prompts),
        )
        self.assertIn(texto, prompts[0])
        self.assertNotIn("cortada", prompts[0])

    def test_resposta_do_modelo_que_nao_e_texto_e_resposta_invalida(self):
        for estranha in (None, 123, ["FINAL: x"], b"FINAL: x"):
            apoio.limpar()
            resultado = agente.rodar_turno(
                "p",
                apoio.coordenador_financeiro(),
                apoio.AGENTE_COMPLETO,
                modelo_roteirizado([estranha, "LER:", "FINAL: ok"]),
            )
            self.assertEqual((resultado.tipo, resultado.resposta), ("final", "ok"))
            self.assertIn("fora do formato", resultado.trajetoria[0])

    def test_execucao_id_com_quebra_de_linha_nao_chega_ao_log(self):
        falso = "abc\nFAKE LINHA passo=9 acao=FINAL"
        resultado = turno(
            INDICE + [LER_MULTA, MULTA, "FINAL: ok"],
            apoio.coordenador_financeiro(),
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


if __name__ == "__main__":
    unittest.main()
