from unittest.mock import patch

from ferramentas import integracoes
from ferramentas.base import ErroDeFerramenta
from ferramentas.integracoes import (
    FALHAS_SEGUIDAS_PARA_PAUSAR,
    SEGUNDOS_DE_PAUSA,
    SEGUNDOS_DE_VALIDADE_DA_SAUDE,
    Integracao,
)
from testes.ferramentas.apoio import (
    FerramentaComIntegracao,
    IntegracaoDeTeste,
    RelogioDeTeste,
    TesteComEstadoLimpo,
)


class TestesDeCadastroDaIntegracao(TesteComEstadoLimpo):
    def test_cadastra_e_nao_aceita_nome_repetido(self):
        self.cadastrar_integracao_de_teste()
        with self.assertRaises(ValueError):
            integracoes.registrar_integracao(IntegracaoDeTeste())

    def test_ficha_incompleta_nao_cadastra(self):
        integracao = Integracao()
        integracao.tipo = "inventado"
        with self.assertRaises(ValueError):
            integracoes.registrar_integracao(integracao)


class TestesDoDisjuntor(TesteComEstadoLimpo):
    def setUp(self):
        super().setUp()
        self.relogio = RelogioDeTeste()
        patcher = patch.object(integracoes, "agora", self.relogio)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.integracao = IntegracaoDeTeste()

    def test_pausa_depois_de_tres_falhas_seguidas(self):
        for _ in range(FALHAS_SEGUIDAS_PARA_PAUSAR - 1):
            self.integracao.registrar_falha()
        self.assertFalse(self.integracao.pausada())
        self.integracao.registrar_falha()
        self.assertTrue(self.integracao.pausada())

    def test_sucesso_zera_a_contagem(self):
        self.integracao.registrar_falha()
        self.integracao.registrar_falha()
        self.integracao.registrar_sucesso()
        self.integracao.registrar_falha()
        self.assertFalse(self.integracao.pausada())

    def test_volta_depois_do_tempo_de_pausa(self):
        for _ in range(FALHAS_SEGUIDAS_PARA_PAUSAR):
            self.integracao.registrar_falha()
        self.relogio.valor += SEGUNDOS_DE_PAUSA + 1
        self.assertFalse(self.integracao.pausada())

    def test_uma_falha_depois_da_pausa_pausa_de_novo(self):
        for _ in range(FALHAS_SEGUIDAS_PARA_PAUSAR):
            self.integracao.registrar_falha()
        self.relogio.valor += SEGUNDOS_DE_PAUSA + 1
        self.integracao.registrar_falha()
        self.assertTrue(self.integracao.pausada())


class TestesDaSaude(TesteComEstadoLimpo):
    def setUp(self):
        super().setUp()
        self.relogio = RelogioDeTeste()
        patcher = patch.object(integracoes, "agora", self.relogio)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.integracao = IntegracaoDeTeste()

    def test_saude_fica_guardada_pelo_tempo_de_validade(self):
        self.integracao.estado()
        self.integracao.estado()
        self.assertEqual(self.integracao.conferencias, 1)
        self.relogio.valor += SEGUNDOS_DE_VALIDADE_DA_SAUDE
        self.integracao.estado()
        self.assertEqual(self.integracao.conferencias, 2)

    def test_conferencia_que_quebra_vira_fora_do_ar(self):
        self.integracao.verificar_saude = lambda: 1 / 0
        self.assertEqual(self.integracao.estado()["estado"], "fora_do_ar")

    def test_estado_desconhecido_vira_fora_do_ar(self):
        self.integracao.saude = {"estado": "tudo_certo", "mensagem": "", "latencia_ms": 1}
        self.assertEqual(self.integracao.estado()["estado"], "fora_do_ar")


class TestesDaFerramentaComIntegracao(TesteComEstadoLimpo):
    def setUp(self):
        super().setUp()
        self.relogio = RelogioDeTeste()
        patcher = patch.object(integracoes, "agora", self.relogio)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.integracao = self.cadastrar_integracao_de_teste()
        self.ferramenta = FerramentaComIntegracao()

    def test_falhas_da_integracao_pausam_e_as_proximas_chamadas_nem_saem(self):
        self.ferramenta.erro_a_levantar = ErroDeFerramenta("integracao_indisponivel", "caiu")
        for _ in range(FALHAS_SEGUIDAS_PARA_PAUSAR):
            self.ferramenta.executar({}, self.usuario)
        self.assertEqual(self.ferramenta.chamadas, FALHAS_SEGUIDAS_PARA_PAUSAR)
        retorno = self.ferramenta.executar({}, self.usuario)
        self.assertEqual(retorno["tipo_erro"], "integracao_indisponivel")
        self.assertEqual(self.ferramenta.chamadas, FALHAS_SEGUIDAS_PARA_PAUSAR)

    def test_chamada_com_sucesso_zera_as_falhas(self):
        self.ferramenta.erro_a_levantar = ErroDeFerramenta("tempo_esgotado", "demorou")
        self.ferramenta.executar({}, self.usuario)
        self.ferramenta.executar({}, self.usuario)
        self.ferramenta.erro_a_levantar = None
        self.ferramenta.executar({}, self.usuario)
        self.assertEqual(self.integracao.falhas_seguidas, 0)

    def test_erro_do_usuario_nao_conta_como_falha_da_integracao(self):
        self.ferramenta.parametros = {"a": {"tipo": "inteiro", "obrigatorio": True, "descricao": "Um número."}}
        for _ in range(FALHAS_SEGUIDAS_PARA_PAUSAR + 1):
            self.ferramenta.executar({}, self.usuario)
        self.assertFalse(self.integracao.pausada())
        self.assertEqual(self.ferramenta.chamadas, 0)

    def test_integracao_nao_cadastrada_deixa_a_ferramenta_indisponivel(self):
        integracoes.INTEGRACOES.clear()
        retorno = self.ferramenta.executar({}, self.usuario)
        self.assertEqual(retorno["tipo_erro"], "integracao_indisponivel")
        self.assertEqual(self.ferramenta.chamadas, 0)
