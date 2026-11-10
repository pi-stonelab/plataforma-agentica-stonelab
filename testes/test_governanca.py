import json
import unittest
from types import SimpleNamespace

from ferramentas import governanca
from testes import apoio

TODAS = (governanca.TODAS_AS_AREAS,)
CAMPOS = set(governanca.CAMPOS_REGISTRO)


def ficha(**mudancas):
    campos = {"nivel_minimo": "N1", "areas_permitidas": ("atendimento", "financeiro")}
    campos |= {"categorias_dados": ("cadastral",), "sensibilidade": "pessoal"}
    campos |= {"acesso": "leitura", "status": "ativa", **mudancas}
    return SimpleNamespace(**campos)


def func(**mudancas):
    campos = {"id_usuario": "USR-9", "nivel": "N1", "area": "atendimento", "carteira": ()}
    return SimpleNamespace(**{**campos, **mudancas})


def motivo(f, usuario):
    return governanca.motivo_bloqueio(f, usuario)


class TestMotivoBloqueio(unittest.TestCase):
    def test_matriz_de_nivel_e_area(self):
        for nivel in governanca.NIVEIS:
            for area in governanca.AREAS_USUARIO:
                liberado = area in ("atendimento", "financeiro")
                self.assertEqual(motivo(ficha(), func(nivel=nivel, area=area)) is None, liberado)

    def test_nivel_minimo_todas_as_areas_e_lista_vazia(self):
        self.assertIsInstance(motivo(ficha(nivel_minimo="N2"), func()), str)
        self.assertIsNone(motivo(ficha(nivel_minimo="N2"), func(nivel="N2")))
        for area in governanca.AREAS_USUARIO:
            self.assertIsNone(motivo(ficha(areas_permitidas=TODAS), func(area=area)))
            self.assertIsInstance(motivo(ficha(areas_permitidas=()), func(area=area)), str)

    def test_usuario_invalido_falha_fechado(self):
        invalidos = [None, "N2", SimpleNamespace(), func(nivel="N3"), func(nivel="n2")]
        invalidos += [func(nivel=None), func(area="marketing"), func(area=None)]
        invalidos += [SimpleNamespace(nivel="N2", area="dados"), func(id_usuario="")]
        invalidos += [func(id_usuario=None), func(id_usuario=7)]
        invalidos += [SimpleNamespace(id_usuario="U", area="dados")]
        invalidos += [SimpleNamespace(id_usuario="U", nivel="N2")]
        for usuario in invalidos:
            with self.subTest(usuario=usuario):
                self.assertIsInstance(motivo(ficha(areas_permitidas=TODAS), usuario), str)

    def test_ficha_invalida_falha_fechado(self):
        sem_nivel = ficha()
        del sem_nivel.nivel_minimo
        invalidas = [None, sem_nivel, ficha(sensibilidade="secreta"), ficha(sensibilidade=None)]
        invalidas += [ficha(categorias_dados=("cadastral", "inventada")), ficha(nivel_minimo="N9")]
        for invalida in invalidas:
            with self.subTest(ficha=invalida):
                self.assertIsInstance(motivo(invalida, func(nivel="N2")), str)

    def test_motivo_nao_leva_dados_do_usuario(self):
        self.assertNotIn(
            "USR-SECRETO", motivo(ficha(), func(id_usuario="USR-SECRETO", area="dados"))
        )


class TestEscopoDeCarteira(unittest.TestCase):
    def test_n2_ve_qualquer_cliente_e_n1_so_a_carteira(self):
        escopo = governanca.cliente_no_escopo
        self.assertIs(escopo(func(nivel="N2"), "CLI-0005"), True)
        self.assertIs(escopo(func(carteira=("CLI-0001", "CLI-0002")), "CLI-0002"), True)
        self.assertIs(escopo(func(carteira=("CLI-0001",)), "CLI-0003"), False)
        self.assertIs(escopo(func(), "CLI-0001"), False)

    def test_usuario_guarda_os_quatro_atributos(self):
        u = governanca.Usuario("USR-1", "N2", "dados", ("CLI-0001",))
        self.assertEqual(
            (u.id_usuario, u.nivel, u.area, u.carteira), ("USR-1", "N2", "dados", ("CLI-0001",))
        )
        self.assertEqual(len(governanca.Usuario("USR-1", "N1", "dados").carteira), 0)


class TestRegistrar(unittest.TestCase):
    def setUp(self):
        apoio.limpar()

    def test_descarta_chaves_fora_do_contrato(self):
        governanca.registrar({"ferramenta": "x", "argumentos": {"a": 1}, "segredo": "s"})
        self.assertLessEqual(set(governanca.REGISTROS[-1]), CAMPOS)
        self.assertEqual(governanca.REGISTROS[-1]["ferramenta"], "x")
        self.assertNotIn("segredo", json.dumps(governanca.REGISTROS))

    def test_mantem_so_os_ultimos_mil(self):
        for numero in range(1005):
            governanca.registrar({"execucao_id": numero})
        self.assertEqual(len(governanca.REGISTROS), 1000)
        self.assertEqual(governanca.REGISTROS[0]["execucao_id"], 5)

    def test_destino_recebe_so_campos_do_contrato_e_destino_que_falha_nao_derruba(self):
        def destino_que_falha(registro):
            raise RuntimeError("destino fora do ar")

        recebidos = []
        governanca.adicionar_destino(destino_que_falha)
        governanca.adicionar_destino(recebidos.append)
        governanca.registrar({"ferramenta": "w", "extra": "z"})
        self.assertLessEqual(set(recebidos[-1]), CAMPOS)
        self.assertEqual(governanca.REGISTROS[-1]["ferramenta"], "w")
        self.assertEqual(
            apoio.falsa().executar({"obrig": "a"}, apoio.n1_atendimento())["status"], "ok"
        )

    def test_entrada_invalida_em_registrar_e_destino_nao_levanta(self):
        for registro in (None, "texto", 5, ["a"]):
            governanca.registrar(registro)
        governanca.adicionar_destino("nao_chamavel")
        self.assertEqual(len(governanca.REGISTROS), 0)
