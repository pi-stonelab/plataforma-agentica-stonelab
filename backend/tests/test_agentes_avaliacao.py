"""A avaliação de uso de ferramentas (agentes/avaliacao.py), com modelos roteirizados."""

import json
import os
import unittest
from unittest import mock

import requests
from agentes import avaliacao, terminal
from agentes.agente_atendimento import agente as motor
from ferramentas import catalogo, confirmacoes, diretorio, governanca
from mock.modelos import Chamado
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import apoio_agente as apoio
from .apoio_agente import modelo_roteirizado
from .apoio_ferramentas import limpar_estado, mundo_do_mock, usuario_do_diretorio

USO = {
    "consultar_cliente": 'USAR: consultar_cliente | {"id_cliente": "M00001"}',
    "consultar_transacoes_cliente": 'USAR: consultar_transacoes_cliente | {"id_cliente": "M00001"}',
    "calcular_multa_atraso": 'USAR: calcular_multa_atraso | {"valor_fatura": 1000, "dias_atraso": 30}',
    "consultar_endereco_cep": 'USAR: consultar_endereco_cep | {"cep": "01310-100"}',
    "consultar_liquidacoes_cliente": 'USAR: consultar_liquidacoes_cliente | {"id_cliente": "M00001"}',
    "listar_chamados_cliente": 'USAR: listar_chamados_cliente | {"id_cliente": "M00009"}',
    "consultar_historico_contato": (
        'USAR: consultar_historico_contato | {"id_cliente": "M00009", "id_chamado": "CH000062"}'
    ),
    "listar_faturas_em_atraso": 'USAR: listar_faturas_em_atraso | {"id_cliente": "M00003"}',
    "calcular_parcelas": 'USAR: calcular_parcelas | {"valor_total": 330.67, "numero_parcelas": 4}',
    # bloco F
    "buscar_clientes": 'USAR: buscar_clientes | {"nome": "Padaria Pão da Vila"}',
    "consultar_base_conhecimento": 'USAR: consultar_base_conhecimento | {"termo": "crédito parcelado"}',
    "consultar_chamado": 'USAR: consultar_chamado | {"id_cliente": "M00001", "id_chamado": "CH000061"}',
    "verificar_identidade_contato": (
        'USAR: verificar_identidade_contato | {"id_cliente": "M00001", "telefone": "(21) 90000-0101"}'
    ),
    "simular_antecipacao": 'USAR: simular_antecipacao | {"id_cliente": "M00001"}',
    "consultar_saldo_agenda": 'USAR: consultar_saldo_agenda | {"id_cliente": "M00003"}',
    "listar_contestacoes_cliente": 'USAR: listar_contestacoes_cliente | {"id_cliente": "M00002"}',
    "conferir_liquidacoes": 'USAR: conferir_liquidacoes | {"id_cliente": "M00001"}',
    "listar_acordos": "USAR: listar_acordos | {}",
    "consultar_cotacao_moeda": 'USAR: consultar_cotacao_moeda | {"moeda": "USD"}',
    "abrir_chamado": (
        'USAR: abrir_chamado | {"id_cliente": "M00001", "categoria": "Maquininha", "impede_vender": "sim", '
        '"resumo": "A maquininha não liga e o lojista não consegue vender."}'
    ),
    "adicionar_nota_chamado": (
        'USAR: adicionar_nota_chamado | {"id_cliente": "M00001", "id_chamado": "CH000061", '
        '"texto": "Lojista avisado sobre a conta de recebimento inválida."}'
    ),
    "atualizar_situacao_chamado": (
        'USAR: atualizar_situacao_chamado | {"id_cliente": "M00001", "id_chamado": "CH000061", '
        '"nova_situacao": "em_atendimento"}'
    ),
    "enviar_email": (
        'USAR: enviar_email | {"id_cliente": "M00001", "assunto": "Depósito de 14/10/2026", '
        '"corpo": "O depósito de 14/10/2026 não caiu porque a conta de recebimento está inválida."}'
    ),
    "registrar_pedido_antecipacao": (
        'USAR: registrar_pedido_antecipacao | {"id_cliente": "M00004", "resumo": "Lojista pede para antecipar a agenda."}'
    ),
    "registrar_acordo": 'USAR: registrar_acordo | {"id_cliente": "M00003", "numero_parcelas": 4}',
}
# A mesma ferramenta com outro lojista, quando o cenário pede.
USO_DO_CENARIO = {
    ("pedido_de_antecipacao_com_previa", "simular_antecipacao"): 'USAR: simular_antecipacao | {"id_cliente": "M00004"}',
}
RESPOSTA = (
    "FINAL: Padaria Pão da Vila (M00001), T0000625, R$ 1.030,00, Avenida Paulista, R$ 1.842,30 na conta, "
    "R$ 330,67 em 4 parcelas, chamado CH000062 sobre a maquininha. Crédito parcelado: cada parcela cai em 30 dias. "
    "O chamado CH000061 está com o prazo vencido. O contato não confere com o cadastro. Não dá para antecipar: a "
    "conta de recebimento está inválida, e quem executa é o especialista N2. Saldo da agenda de R$ 303,36. "
    "Chargeback de R$ 459,90 com prazo até 16/10/2026. O acordo AC0001 espera aprovação. O dólar (USD) está em "
    "R$ 5,3249 em 15/10/2026. A prévia do chamado crítico, da nota, do e-mail, do pedido e do acordo espera a sua "
    "confirmação na tela."
)


def buscar_usuario(id_funcionario):
    return usuario_do_diretorio(apoio.mundo(), id_funcionario)


def roteiro_certo(cenario):
    """O que um modelo que acerta diria: ler o índice, ler cada ficha, usar, responder."""
    if cenario.negadas:
        return ["LER:", "LER: atendimento/consultar_cliente", 'USAR: consultar_cliente | {"id_cliente": "M00002"}',
                "FINAL: não tenho acesso a esse lojista."]
    fichas = [f"LER: {catalogo.carregar()[nome].area}/{nome}" for nome in cenario.esperadas]
    usos = [USO_DO_CENARIO.get((cenario.nome, nome), USO[nome]) for nome in cenario.esperadas]
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
                for nome in catalogo.nomes():
                    self.assertNotIn(nome, c.pergunta)


# `executar_antecipacao` não tem cenário fixo: precisa de um pedido já registrado e confirmado antes (dois turnos
# de pessoas diferentes). Fica coberto por test_ferramentas_escritas_mock.py.
SEM_CENARIO_FIXO = {"executar_antecipacao"}


class TestCenariosDoBlocoF(unittest.TestCase):
    """Os cenários das ferramentas novas e das escritas com confirmação (decisão F4)."""

    def setUp(self):
        apoio.limpar()

    def test_a_ferramenta_esperada_esta_ao_alcance_do_cargo_de_quem_pergunta(self):
        for c in avaliacao.CENARIOS:
            with self.subTest(c.nome):
                usuario = buscar_usuario(c.funcionario)
                alcance = catalogo.ferramentas_liberadas(usuario, motor.FERRAMENTAS_DO_AGENTE)
                self.assertLessEqual(set(c.esperadas), set(alcance), usuario.cargo)

    def test_previas_esperadas_sao_escritas_em_duas_fases_e_foram_pedidas_pelo_cenario(self):
        for c in avaliacao.CENARIOS:
            with self.subTest(c.nome):
                self.assertLessEqual(set(c.previas), set(c.esperadas))
                self.assertLessEqual(set(c.previas), set(governanca.ESCRITA_COM_CONFIRMACAO))

    def test_toda_escrita_em_duas_fases_do_agente_tem_cenario_ou_motivo(self):
        no_agente = set(motor.FERRAMENTAS_DO_AGENTE) & set(governanca.ESCRITA_COM_CONFIRMACAO)
        cobertas = {nome for c in avaliacao.CENARIOS for nome in c.previas}
        self.assertEqual(no_agente - cobertas, SEM_CENARIO_FIXO)

    def test_toda_ferramenta_nova_de_leitura_ou_calculo_tem_cenario(self):
        esperadas = {nome for c in avaliacao.CENARIOS for nome in c.esperadas}
        for nome in ("buscar_clientes", "consultar_base_conhecimento", "consultar_chamado",
                     "verificar_identidade_contato", "simular_antecipacao", "consultar_saldo_agenda",
                     "listar_contestacoes_cliente", "conferir_liquidacoes", "listar_acordos",
                     "consultar_cotacao_moeda"):
            self.assertIn(nome, esperadas)

    def test_a_cotacao_exige_a_data_na_resposta(self):
        padroes = cenario("cotacao_do_dolar_com_a_data").padroes
        self.assertTrue(any("d{4}-" in p for p in padroes))

    def test_o_n1_que_pede_a_execucao_nao_executa_e_ouve_que_e_do_n2(self):
        c = cenario("n1_pede_para_executar_antecipacao")
        r = avaliar(c, roteiro_certo(c))
        self.assertEqual(r.executadas, ("simular_antecipacao",))
        self.assertNotIn("executar_antecipacao", r.executadas)
        self.assertTrue(r.aprovado)


class TestPreviasDoAgente(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_escrita_deixa_uma_previa_e_a_avaliacao_a_descarta_sem_gravar_nada(self):
        c = cenario("abrir_chamado_com_previa")
        r = avaliar(c, roteiro_certo(c))
        self.assertEqual(r.executadas, ("abrir_chamado",))
        self.assertTrue(r.previas_certas and r.aprovado)
        self.assertEqual(confirmacoes.pendentes(buscar_usuario(c.funcionario)), [])

    def test_modelo_que_nao_chama_a_escrita_reprova(self):
        c = cenario("abrir_chamado_com_previa")
        r = avaliar(c, ["LER:", "FINAL: a prévia do chamado crítico espera a confirmação."])
        self.assertFalse(r.ferramentas_certas)
        self.assertFalse(r.previas_certas)
        self.assertFalse(r.aprovado)

    def test_previa_que_sobra_num_cenario_sem_escrita_reprova(self):
        c = cenario("cadastro")
        usuario = buscar_usuario(c.funcionario)
        linhas = ["LER:", "LER: comunicacao/enviar_email", USO["enviar_email"], "LER: atendimento/consultar_cliente",
                  USO["consultar_cliente"], RESPOSTA]
        r = avaliar(c, linhas)
        self.assertEqual(r.executadas, ("enviar_email", "consultar_cliente"))
        self.assertFalse(r.previas_certas)
        self.assertEqual(confirmacoes.pendentes(usuario), [])

    def test_o_resumo_mostra_a_coluna_das_previas(self):
        c = cenario("email_ao_lojista_com_previa")
        self.assertIn("prév.", avaliacao.resumir([avaliar(c, roteiro_certo(c))]))

    def test_a_previa_confirmada_pela_pessoa_grava_uma_vez_no_mock(self):
        engine = mundo_do_mock()
        limpar_estado()
        c = cenario("abrir_chamado_com_previa")

        def usuario(id_funcionario):
            return usuario_do_diretorio(engine, id_funcionario)

        antes = _quantos_chamados(engine)
        r = avaliacao.avaliar_cenario(c, modelo_roteirizado(roteiro_certo(c)), usuario, limpar_previas=False)
        self.assertTrue(r.aprovado)
        self.assertEqual(_quantos_chamados(engine), antes)  # a prévia não gravou
        pessoa = usuario(c.funcionario)
        (previa,) = confirmacoes.pendentes(pessoa)
        feito = confirmacoes.confirmar(previa["confirmacao_id"], pessoa)  # quem confirma é a pessoa
        self.assertEqual(feito["status"], "ok", feito)
        self.assertEqual(_quantos_chamados(engine), antes + 1)
        self.assertEqual(confirmacoes.confirmar(previa["confirmacao_id"], pessoa)["status"], "erro")  # uso único


def _quantos_chamados(engine):
    with Session(engine) as sessao:
        return sessao.scalar(select(func.count()).select_from(Chamado))


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


class TestPrazoDoTurno(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_a_avaliacao_mede_com_o_teto_do_motor_por_padrao(self):
        self.assertEqual(avaliacao.PRAZO_DA_AVALIACAO, motor.SEGUNDOS_MAXIMOS_POR_TURNO)

    def test_o_prazo_escolhido_chega_ao_motor_como_tempo_limite(self):
        recebidos = []

        def modelo(prompt_sistema, prompt, tempo_limite):
            recebidos.append(tempo_limite)
            return "FINAL: x" if len(recebidos) > 1 else "LER:"

        avaliacao.avaliar_cenario(cenario("cep"), modelo, buscar_usuario, segundos_por_turno=500)
        self.assertTrue(all(450 < t <= 500 for t in recebidos), recebidos)

    def test_sem_prazo_escolhido_vale_o_padrao_do_motor(self):
        recebidos = []

        def modelo(prompt_sistema, prompt, tempo_limite):
            recebidos.append(tempo_limite)
            return "LER:" if len(recebidos) == 1 else "FINAL: x"

        avaliacao.avaliar_cenario(cenario("cep"), modelo, buscar_usuario)
        self.assertTrue(all(motor.SEGUNDOS_POR_TURNO - 30 < t <= motor.SEGUNDOS_POR_TURNO for t in recebidos))

    def test_o_resumo_lista_o_tempo_de_cada_chamada(self):
        r = avaliar(cenario("cep"), roteiro_certo(cenario("cep")))
        self.assertEqual(len(r.segundos_por_chamada), r.chamadas_ao_modelo)
        self.assertIn("chamadas ao modelo (s):", avaliacao.resumir([r]))


class TestMedidor(unittest.TestCase):
    def test_conta_chamadas_e_soma_o_tempo(self):
        medidor = avaliacao.Medidor(modelo_roteirizado(["a", "b"]))
        medidor("sistema", "p1")
        medidor("sistema", "p2")
        self.assertEqual(medidor.chamadas, 2)
        self.assertGreaterEqual(medidor.segundos, 0)

    def test_guarda_o_tempo_de_cada_chamada(self):
        medidor = avaliacao.Medidor(modelo_roteirizado(["a", "b", "c"]))
        for _ in range(3):
            medidor("sistema", "p")
        self.assertEqual(len(medidor.por_chamada), 3)

    def test_prefere_a_causa_que_o_modelo_informa(self):
        def quebrado(prompt_sistema, prompt):
            erro = RuntimeError("fora")
            erro.causa = "HTTP 524"
            raise erro

        medidor = avaliacao.Medidor(quebrado)
        with self.assertRaises(RuntimeError):
            medidor("sistema", "p")
        self.assertEqual(medidor.tipo_do_ultimo_erro, "HTTP 524")

    def test_conta_a_chamada_que_falha(self):
        def quebrado(prompt_sistema, prompt):
            raise RuntimeError("fora")

        medidor = avaliacao.Medidor(quebrado)
        with self.assertRaises(RuntimeError):
            medidor("sistema", "p")
        self.assertEqual(medidor.chamadas, 1)

    def test_guarda_so_o_tipo_da_falha_do_modelo(self):
        def quebrado(prompt_sistema, prompt):
            raise KeyError("CF_ACCESS_CLIENT_ID")

        medidor = avaliacao.Medidor(quebrado)
        with self.assertRaises(KeyError):
            medidor("sistema", "p")
        self.assertEqual(medidor.tipo_do_ultimo_erro, "KeyError")

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

    def test_modelo_que_falha_mostra_o_tipo_da_falha(self):
        def quebrado(prompt_sistema, prompt):
            raise KeyError("CF_ACCESS_CLIENT_ID")

        r = avaliacao.avaliar_cenario(cenario("cep"), quebrado, buscar_usuario)
        self.assertEqual((r.tipo, r.motivo, r.erro_do_modelo), ("limite", "modelo_indisponivel", "KeyError"))
        self.assertIn("falha: KeyError", avaliacao.resumir([r]))
        self.assertNotIn("CF_ACCESS", avaliacao.resumir([r]))

    def test_resumo_marca_o_que_falhou(self):
        ruim = avaliar(cenario("cadastro"), ["LER:", RESPOSTA])
        self.assertIn("NÃO", avaliacao.resumir([ruim]))

    def test_o_json_nao_leva_pergunta_resposta_nem_dado_de_lojista(self):
        texto = avaliacao.para_json(self.resultados)
        self.assertEqual(len(json.loads(texto)), len(avaliacao.CENARIOS))
        for proibido in ("Padaria", "M00001", "M00002", "T0000625", "Avenida", "Quem é"):
            self.assertNotIn(proibido, texto)


URL = "https://modelo.exemplo.dev"
CABECALHOS = {"CF-Access-Client-Id": "id-secreto", "CF-Access-Client-Secret": "segredo-123"}


class RespostaFalsa:
    def __init__(self, codigo, corpo=None):
        self.status_code = codigo
        self._corpo = corpo

    def json(self):
        if self._corpo is None:
            raise ValueError("sem json")
        return self._corpo


def obter_que_responde(codigo, corpo=None):
    return lambda url, headers, timeout: RespostaFalsa(codigo, corpo)


def obter_que_falha(erro):
    def obter(url, headers, timeout):
        raise erro

    return obter


def diagnostico(url=URL, obter=None, modelo="qwen3.8:27b"):
    return "\n".join(avaliacao.diagnosticar(url, CABECALHOS, modelo, obter=obter))


class TestDiagnostico(unittest.TestCase):
    def test_tudo_certo_lista_os_modelos_e_confere_o_nome(self):
        corpo = {"models": [{"name": "qwen3.8:27b"}, {"name": "llama3:8b"}]}
        texto = diagnostico(obter=obter_que_responde(200, corpo))
        self.assertIn("Conectou", texto)
        self.assertIn("'qwen3.8:27b' (LLM_MODELO) está", texto)
        self.assertIn("llama3:8b", texto)

    def test_modelo_com_nome_diferente_do_servidor_e_avisado(self):
        texto = diagnostico(obter=obter_que_responde(200, {"models": [{"name": "outro:7b"}]}))
        self.assertIn("NÃO está", texto)

    def test_cloudflare_recusando_as_credenciais(self):
        for codigo in (401, 403):
            with self.subTest(codigo):
                self.assertIn("recusou as credenciais", diagnostico(obter=obter_que_responde(codigo)))

    def test_caminho_inexistente_e_resposta_de_outro_servico(self):
        self.assertIn("404", diagnostico(obter=obter_que_responde(404)))
        self.assertIn("não é a lista de modelos", diagnostico(obter=obter_que_responde(200)))
        self.assertIn("HTTP 500", diagnostico(obter=obter_que_responde(500)))

    def test_falhas_de_rede_viram_um_parecer_por_tipo(self):
        casos = {
            requests.exceptions.ConnectionError("x"): "Não conectou",
            requests.exceptions.Timeout("x"): "Sem resposta",
            requests.exceptions.SSLError("x"): "certificado",
            requests.exceptions.MissingSchema("x"): "MissingSchema",
        }
        for erro, esperado in casos.items():
            with self.subTest(type(erro).__name__):
                self.assertIn(esperado, diagnostico(obter=obter_que_falha(erro)))

    def test_url_mal_escrita_e_apontada_antes_da_chamada(self):
        texto = diagnostico(url='"modelo.exemplo.dev/api/', obter=obter_que_responde(404))
        for trecho in ("não começa com https://", "termina com '/'", "tem '/api'", "tem aspas"):
            self.assertIn(trecho, texto)

    def test_o_parecer_nunca_leva_a_url_nem_as_credenciais(self):
        erro = requests.exceptions.ConnectionError(f"falhou em {URL} com segredo-123")
        casos = [obter_que_falha(erro), obter_que_responde(403), obter_que_responde(200, {"models": []})]
        for obter in casos:
            texto = diagnostico(obter=obter)
            for proibido in (URL, "modelo.exemplo", "segredo-123", "id-secreto"):
                self.assertNotIn(proibido, texto)


class TestPrincipal(unittest.TestCase):
    def test_sem_llm_url_nao_roda(self):
        with mock.patch.object(terminal, "LLM_URL", ""), self.assertRaises(SystemExit):
            avaliacao.principal([])

    def test_faltando_credencial_avisa_so_o_nome_da_variavel(self):
        ambiente = {"LLM_URL": "http://x", "CF_ACCESS_CLIENT_ID": "", "CF_ACCESS_CLIENT_SECRET": "segredo"}
        with (
            mock.patch.dict(os.environ, ambiente),
            mock.patch.object(terminal, "LLM_URL", "http://x"),
            self.assertRaises(SystemExit) as erro,
        ):
            avaliacao.principal([])
        self.assertIn("CF_ACCESS_CLIENT_ID", str(erro.exception))
        self.assertNotIn("segredo", str(erro.exception))

    def test_modelo_escolhido_troca_o_do_terminal(self):
        antes = terminal.LLM_MODELO
        try:
            with (
                mock.patch.dict(os.environ, {"LLM_URL": "http://x", "CF_ACCESS_CLIENT_ID": "i", "CF_ACCESS_CLIENT_SECRET": "s"}),
                mock.patch.object(terminal, "LLM_URL", "http://x"),
                mock.patch.object(avaliacao, "diagnosticar", return_value=[]),
                mock.patch.object(terminal, "montar_headers", return_value={}),
            ):
                avaliacao.principal(["--diagnosticar", "--modelo", " qwen3:14b "])
                self.assertEqual(terminal.LLM_MODELO, "qwen3:14b")
        finally:
            terminal.LLM_MODELO = antes

    def test_diagnosticar_avisa_o_que_falta_no_env(self):
        with (
            mock.patch.dict(os.environ, {"LLM_URL": "http://x", "CF_ACCESS_CLIENT_ID": "", "CF_ACCESS_CLIENT_SECRET": "s"}),
            mock.patch.object(terminal, "LLM_URL", "http://x"),
            self.assertRaises(SystemExit) as erro,
        ):
            avaliacao.principal(["--diagnosticar"])
        self.assertIn("CF_ACCESS_CLIENT_ID", str(erro.exception))

    def test_mock_local_zera_a_url_do_banco_do_mock_antes_do_terminal(self):
        with (
            mock.patch.dict(os.environ, {"MOCK_DATABASE_URL": "postgresql+psycopg://x/y"}),
            mock.patch.object(terminal, "LLM_URL", ""),
        ):
            with self.assertRaises(SystemExit):
                avaliacao.principal(["--mock-local"])
            self.assertEqual(os.environ["MOCK_DATABASE_URL"], "")

    def test_cenario_desconhecido_e_recusado_pelo_analisador(self):
        with self.assertRaises(SystemExit):
            avaliacao.principal(["--cenario", "nao_existe"])


if __name__ == "__main__":
    unittest.main()
