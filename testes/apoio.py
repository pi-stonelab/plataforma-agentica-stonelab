import importlib
import json

from ferramentas import catalogo, governanca
from ferramentas.base import TIPOS_ERRO, Ferramenta

AGENTE_COMPLETO = (
    "consultar_cliente",
    "consultar_transacoes_cliente",
    "calcular_multa_atraso",
    "consultar_endereco_cep",
    "solicitar_ferramenta_ausente",
)


def n1_atendimento():
    return governanca.Usuario("USR-0001", "N1", "atendimento", ("CLI-0001",))


def n1_dados():
    return governanca.Usuario("USR-0002", "N1", "dados", ())


def n2_financeiro():
    return governanca.Usuario("USR-0003", "N2", "financeiro", ())


def pedidos():
    nome = "ferramentas.plataforma.solicitar_ferramenta_ausente.func"
    return importlib.import_module(nome).PEDIDOS


def limpar():
    del governanca.REGISTROS[:]
    pedidos().clear()


def uma_inativa():
    return next(nome for nome, f in catalogo.carregar().items() if f.status != "ativa")


def confere_forma(teste, resposta):
    teste.assertEqual(set(resposta), {"status", "dados", "mensagem", "tipo_erro"})
    if resposta["status"] == "ok":
        teste.assertIsNone(resposta["tipo_erro"])
    else:
        teste.assertIsNone(resposta["dados"])
        teste.assertIn(resposta["tipo_erro"], TIPOS_ERRO)


class FerramentaFalsa(Ferramenta):
    nome = "falsa"
    area = "plataforma"
    acesso = "calculo"
    nivel_minimo = "N1"
    areas_permitidas = (governanca.TODAS_AS_AREAS,)
    sensibilidade = "publica"
    status = "ativa"
    erro = None

    def __init__(self):
        opcional = {"obrigatorio": False}
        self.parametros = {"obrig": {"tipo": "texto", "obrigatorio": True}}
        for nome, tipo in (("numero", "inteiro"), ("valor", "decimal"), ("dia", "data")):
            self.parametros[nome] = {"tipo": tipo, **opcional}

    def rodar(self, argumentos, usuario):
        if self.erro is not None:
            raise self.erro
        return {"ok": True}


def falsa(**ficha):
    ferramenta = FerramentaFalsa()
    for campo, valor in ficha.items():
        setattr(ferramenta, campo, valor)
    return ferramenta


class ModeloRoteirizado:
    def __init__(self, linhas):
        self.linhas = list(linhas)

    def proxima_resposta(self, observacao):
        return self.linhas.pop(0)


def rodar_loop(modelo, usuario, ferramentas_do_agente, maximo_passos=8):
    """Loop mínimo (protocolo 2.8). Devolve (resposta_final, observações)."""
    observacoes, observacao = [], ""
    for _ in range(maximo_passos):
        linha = modelo.proxima_resposta(observacao)
        if linha.startswith("FINAL: "):
            return linha[7:], observacoes
        if linha.startswith("LER: "):
            observacao = catalogo.ler(linha[5:].strip(), usuario, ferramentas_do_agente)
        else:
            nome, _, texto = linha[6:].partition(" ")
            resultado = catalogo.executar(nome, json.loads(texto), usuario, ferramentas_do_agente)
            observacao = json.dumps(resultado, ensure_ascii=False)
        observacoes.append(observacao)
    return None, observacoes
