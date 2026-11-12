"""Modo terminal: diretório de funcionários, chamada direta ao modelo e a conversa (agentes/terminal.py)."""

import ast
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from agentes import terminal
from agentes.agente_atendimento import agente as motor
from mock.banco import criar_engine
from mock.falhas import desligar_todas, ligar

from . import apoio_agente as apoio
from .apoio_agente import modelo_roteirizado
from .test_agente_atendimento import INDICE, LER_MULTA, MULTA, turno

URL_DO_MODELO = "https://modelo-secreto.exemplo.invalid"
AMBIENTE_DO_MODELO = {"CF_ACCESS_CLIENT_ID": "id", "CF_ACCESS_CLIENT_SECRET": "segredo"}
RAIZ = Path(__file__).resolve().parents[2]


def resposta_http(erro_http=None, erro_json=None, corpo=None):
    resposta = mock.Mock()
    resposta.raise_for_status.side_effect = erro_http
    resposta.json.side_effect = erro_json
    if corpo is not None:
        resposta.json.return_value = corpo
    return resposta


class TestModoTerminal(unittest.TestCase):
    def test_pergunta_vira_input_e_o_turno_seguinte_continua(self):
        apoio.limpar()
        modelo = modelo_roteirizado(
            INDICE + [LER_MULTA, "PERGUNTAR: Qual a fatura?", MULTA, "FINAL: R$ 1030,00."]
        )
        digitado = iter(["quanto fica a multa?", "1000 e 30 dias", "sair"])
        saida = io.StringIO()
        with (
            mock.patch.object(terminal, "chamar_llm", modelo),
            mock.patch("builtins.input", lambda *_: next(digitado)),
            contextlib.redirect_stdout(saida),
        ):
            terminal.conversar_no_terminal(apoio.coordenador_financeiro())
        self.assertIn("Agente: Qual a fatura?", saida.getvalue())
        self.assertIn("Agente: R$ 1030,00.", saida.getvalue())
        self.assertIn("PERGUNTAR -> aguardando o funcionário", saida.getvalue())



class TestUsuarioDoAmbiente(unittest.TestCase):
    """O12: o modo terminal lê só ID_USUARIO; o perfil vem do diretório."""

    def setUp(self):
        apoio.limpar()

    def test_so_o_id_vai_para_a_busca_no_diretorio(self):
        pedidos = []

        def diretorio(id_usuario):
            pedidos.append(id_usuario)
            return apoio.coordenador_financeiro()

        ambiente = {"ID_USUARIO": " USR-9 ", "NIVEL": "N2", "AREA": "tecnologia", "CARTEIRA": "CLI-1"}
        usuario = terminal.usuario_do_ambiente(ambiente, diretorio)
        self.assertEqual(pedidos, ["USR-9"])
        self.assertEqual((usuario.nivel, usuario.area, usuario.carteiras), ("N2", "financeiro", ()))

    def test_nivel_area_e_carteira_do_ambiente_sao_ignorados(self):
        apenas_id = terminal.usuario_do_ambiente({"ID_USUARIO": "USR-9"}, lambda _: apoio.atendente_n1())
        com_extras = terminal.usuario_do_ambiente(
            {"ID_USUARIO": "USR-9", "NIVEL": "N2", "AREA": "financeiro", "CARTEIRA": "CLI-9"},
            lambda _: apoio.atendente_n1(),
        )
        self.assertEqual(
            (apenas_id.nivel, apenas_id.area, apenas_id.carteiras),
            (com_extras.nivel, com_extras.area, com_extras.carteiras),
        )

    def test_id_ausente_invalido_ou_desconhecido_nao_sobe(self):
        for ambiente in ({}, {"ID_USUARIO": ""}, {"ID_USUARIO": "a b"}, {"ID_USUARIO": "x\ny"}):
            with self.assertRaises(ValueError):
                terminal.usuario_do_ambiente(ambiente, lambda _: apoio.coordenador_financeiro())
        with self.assertRaises(ValueError):
            terminal.usuario_do_ambiente({"ID_USUARIO": "USR-404"}, lambda _: None)



class TestDiretorioDoMock(unittest.TestCase):
    """O ponto único de ligação com o diretório (DOC-MOCK §8.4): ativo entra; o resto, não."""

    def setUp(self):
        apoio.limpar()
        self.engine = apoio.mundo()

    def buscar(self, id_usuario):
        return terminal.buscar_usuario_no_diretorio(id_usuario, self.engine)

    def usuario(self, id_usuario, ambiente_extra=None):
        ambiente = {"ID_USUARIO": id_usuario, **(ambiente_extra or {})}
        return terminal.usuario_do_ambiente(ambiente, self.buscar)

    def test_ana_vira_atendente_n1_com_a_carteira_do_time(self):
        ana = self.usuario("F0001")
        self.assertEqual(
            (ana.id_usuario, ana.cargo, ana.nivel, ana.area, ana.carteiras),
            ("F0001", "atendente_n1", "N1", "atendimento", ("varejo",)),
        )

    def test_o_perfil_vem_do_cargo_e_nao_do_ambiente(self):
        extras = {"NIVEL": "N1", "AREA": "atendimento", "CARTEIRA": "varejo"}
        renata = self.usuario("F0011", extras)
        self.assertEqual(
            (renata.cargo, renata.nivel, renata.area, renata.carteiras),
            ("coordenador_financeiro", "N2", "financeiro", ()),
        )

    def test_funcionario_desligado_ou_afastado_e_usuario_invalido(self):
        for id_usuario in ("F0014", "F0015"):  # desligado, afastado
            self.assertIsNone(self.buscar(id_usuario))
            with self.assertRaises(ValueError):
                self.usuario(id_usuario)

    def test_id_bem_formado_que_nao_existe_e_usuario_invalido(self):
        self.assertIsNone(self.buscar("F9999"))
        with self.assertRaises(ValueError):
            self.usuario("F9999")

    def test_diretorio_fora_do_ar_nao_sobe_e_nao_vira_nao_encontrado(self):
        ligar("diretorio")
        self.addCleanup(desligar_todas)
        with self.assertRaisesRegex(ValueError, "indisponível"):
            self.usuario("F0001")

    def test_banco_sem_as_tabelas_do_mock_nao_sobe(self):
        vazio = criar_engine("sqlite://")
        with self.assertRaisesRegex(ValueError, "indisponível"):
            terminal.buscar_usuario_no_diretorio("F0001", vazio)

    def test_usuario_do_diretorio_so_usa_o_que_o_catalogo_libera_para_o_cargo(self):
        ana = self.usuario("F0001")
        linhas = INDICE + [
            "LER: atendimento/consultar_cliente",
            'USAR: consultar_cliente | {"id_cliente": "M00002"}',
            "FINAL: sem acesso",
        ]
        resultado = turno(linhas, ana)
        self.assertIn("permissao_negada", resultado.trajetoria[2])  # M00002 é da carteira pme



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




class TestChamarLlm(unittest.TestCase):
    def chamar_com(self, **configuracao):
        with (
            mock.patch.dict("os.environ", AMBIENTE_DO_MODELO),
            mock.patch.object(terminal, "LLM_URL", URL_DO_MODELO),
            mock.patch.object(terminal.requests, "post", **configuracao),
        ):
            return terminal.chamar_llm("sistema", "prompt")

    def test_envia_o_sistema_e_a_parada(self):
        resposta = resposta_http(corpo={"response": "<think>x</think>FINAL: ok"})
        with (
            mock.patch.dict("os.environ", AMBIENTE_DO_MODELO),
            mock.patch.object(terminal, "LLM_URL", "http://modelo.teste"),
            mock.patch.object(terminal.requests, "post", return_value=resposta) as post,
        ):
            texto = terminal.chamar_llm("SISTEMA DE TESTE", "prompt de teste")
        enviado = post.call_args.kwargs["json"]
        self.assertEqual(texto, "FINAL: ok")
        self.assertEqual(enviado["system"], "SISTEMA DE TESTE")
        self.assertEqual(enviado["prompt"], "prompt de teste")
        self.assertEqual(enviado["options"]["stop"], [motor.PARADA_DO_MODELO])

    def test_url_do_modelo_nao_tem_valor_no_codigo(self):
        with mock.patch.object(terminal, "LLM_URL", ""), self.assertRaises(RuntimeError):
            terminal.chamar_llm("sistema", "prompt")
        for arquivo in (terminal.__file__, motor.__file__):
            self.assertNotIn("https://", Path(arquivo).read_text(encoding="utf-8"))

    def test_troca_o_erro_de_rede_por_mensagem_generica(self):
        rede = terminal.requests.exceptions
        falhas = (
            {"side_effect": rede.ConnectionError(f"HTTPSConnectionPool(host='{URL_DO_MODELO}')")},
            {"side_effect": rede.ReadTimeout(f"{URL_DO_MODELO} Read timed out")},
            {"return_value": resposta_http(erro_http=rede.HTTPError(f"502 para url: {URL_DO_MODELO}"))},
            {"return_value": resposta_http(erro_json=ValueError(URL_DO_MODELO))},
            {"return_value": resposta_http(corpo={"sem_resposta": 1})},
            {"return_value": resposta_http(corpo={"response": 123})},
        )
        for configuracao in falhas:
            with self.subTest(configuracao=list(configuracao)):
                with self.assertRaises(motor.ModeloIndisponivel) as contexto:
                    self.chamar_com(**configuracao)
                erro = contexto.exception
                self.assertNotIn("modelo-secreto", str(erro))
                self.assertIsNone(erro.__cause__)
                self.assertTrue(erro.__suppress_context__ or erro.__context__ is None)

    def test_usa_o_tempo_recebido_como_timeout(self):
        resposta = resposta_http(corpo={"response": "FINAL: ok"})
        with (
            mock.patch.dict("os.environ", AMBIENTE_DO_MODELO),
            mock.patch.object(terminal, "LLM_URL", URL_DO_MODELO),
            mock.patch.object(terminal.requests, "post", return_value=resposta) as post,
        ):
            terminal.chamar_llm("sistema", "prompt", tempo_limite=17.5)
        self.assertEqual(post.call_args.kwargs["timeout"], 17.5)

    def test_turno_reaproveita_o_tempo_que_sobra_como_timeout(self):
        apoio.limpar()
        relogio = apoio.RelogioFalso()
        tempos = []

        def post(*_, **kwargs):
            tempos.append(kwargs["timeout"])
            relogio.passar(40)
            return resposta_http(corpo={"response": "LER:"})

        with (
            mock.patch.dict("os.environ", AMBIENTE_DO_MODELO),
            mock.patch.object(terminal, "LLM_URL", URL_DO_MODELO),
            mock.patch.object(terminal.requests, "post", side_effect=post),
        ):
            resultado = motor.rodar_turno(
                "p", apoio.coordenador_financeiro(), apoio.AGENTE_COMPLETO, terminal.chamar_llm,
                relogio=relogio,
            )
        self.assertEqual(tempos, [120, 80, 40])
        self.assertEqual(resultado.motivo, "tempo")


class TestAgenteEscolhidoNoTerminal(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def conversar(self, nome, digitado, linhas, usuario):
        entradas = iter(digitado)
        saida = io.StringIO()
        with (
            mock.patch("builtins.input", lambda *_: next(entradas)),
            contextlib.redirect_stdout(saida),
        ):
            terminal.conversar_no_terminal(usuario, terminal.AGENTES[nome], modelo_roteirizado(linhas))
        return saida.getvalue()

    def test_os_dois_agentes_estao_disponiveis(self):
        self.assertEqual(set(terminal.AGENTES), {"atendimento", "geral"})
        self.assertEqual(terminal.AGENTES["atendimento"].agente_id, "agente_atendimento")
        self.assertEqual(terminal.AGENTES["geral"].agente_id, "agente_geral")

    def test_o_agente_geral_conversa_pelo_terminal_com_o_proprio_id_no_registro(self):
        from ferramentas import governanca

        saida = self.conversar(
            "geral", ["quanto fica a multa?", "sair"],
            INDICE + [LER_MULTA, MULTA, "FINAL: R$ 1030,00."], apoio.coordenador_financeiro(),
        )
        self.assertIn("Agente: R$ 1030,00.", saida)
        self.assertEqual(governanca.REGISTROS[-1]["agente_id"], "agente_geral")

    def test_o_argumento_de_linha_de_comando_escolhe_o_agente(self):
        escolhidos = []
        ambiente = {"MODO_TERMINAL": "1"}
        for argumentos, esperado in (([], "atendimento"), (["geral"], "geral")):
            with (
                mock.patch.dict("os.environ", ambiente),
                mock.patch.object(terminal, "LLM_URL", URL_DO_MODELO),
                mock.patch.object(terminal, "usuario_do_ambiente", return_value=apoio.atendente_n1()),
                mock.patch.object(
                    terminal, "conversar_no_terminal", lambda _, agente: escolhidos.append(agente)
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                terminal.principal(argumentos)
            self.assertIs(escolhidos[-1], terminal.AGENTES[esperado])

    def test_agente_desconhecido_e_modo_desligado_nao_sobem(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            terminal.principal(["outro"])
        with mock.patch.dict("os.environ", {"MODO_TERMINAL": "0"}), self.assertRaises(SystemExit):
            terminal.principal([])


class TestMotorSemMockNemBanco(unittest.TestCase):
    """I6: o motor não importa mock/, SQLAlchemy, requests nem dotenv; isso é do terminal."""

    PROIBIDOS = ("mock", "sqlalchemy", "requests", "dotenv")

    def modulos_importados(self, caminho):
        arvore = ast.parse(Path(caminho).read_text(encoding="utf-8"))
        nomes = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes |= {alias.name for alias in no.names}
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes.add(no.module)
        return nomes

    def test_o_motor_e_o_agente_geral_nao_importam_mock_nem_banco(self):
        for caminho in (motor.__file__, RAIZ / "agentes" / "agente_geral" / "agente.py"):
            importados = self.modulos_importados(caminho)
            for nome in importados:
                with self.subTest(arquivo=Path(caminho).parent.name, importado=nome):
                    self.assertNotIn(nome.split(".")[0], self.PROIBIDOS)

    def test_o_terminal_e_o_unico_arquivo_de_agentes_que_importa_mock(self):
        com_mock = [
            str(caminho.relative_to(RAIZ))
            for caminho in (RAIZ / "agentes").rglob("*.py")
            if any(nome.split(".")[0] == "mock" for nome in self.modulos_importados(caminho))
        ]
        self.assertEqual(com_mock, ["agentes/terminal.py"])

    def test_o_motor_nao_tem_mais_o_modo_terminal(self):
        for nome in ("conversar_no_terminal", "usuario_do_ambiente", "buscar_usuario_no_diretorio", "chamar_llm"):
            self.assertFalse(hasattr(motor, nome), nome)

    def test_python_dash_m_do_motor_continua_mostrando_o_aviso_de_modo_desligado(self):
        ambiente = {k: v for k, v in os.environ.items() if k != "MODO_TERMINAL"}
        resultado = subprocess.run(
            [sys.executable, "-m", "agentes.agente_atendimento.agente"],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("MODO_TERMINAL=1", resultado.stderr)

    def test_python_dash_m_terminal_aceita_o_argumento_geral(self):
        ambiente = {k: v for k, v in os.environ.items() if k != "MODO_TERMINAL"}
        resultado = subprocess.run(
            [sys.executable, "-m", "agentes.terminal", "geral"],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertIn("MODO_TERMINAL=1", resultado.stderr)


if __name__ == "__main__":
    unittest.main()
