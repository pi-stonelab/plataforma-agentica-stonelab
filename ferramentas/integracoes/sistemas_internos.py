"""Os sistemas internos da Stone, que na plataforma são o mock (a Stone simulada, pasta `mock/`).

O modo é sempre `simulado`: não existe sistema real por trás. A saúde vem das falhas simuladas
(`mock.falhas`); o `testar` faz uma leitura de verdade no banco do mock, sem mostrar o resultado.
"""

from mock import falhas

from ferramentas import dados_sinteticos
from ferramentas.integracoes.conector import Conector
from ferramentas.integracoes.registro import registrar

LOJISTA_DO_TESTE = "M00001"


class ConectorInterno(Conector):
    tipo = "interno"
    modo_padrao = "simulado"
    variaveis = ("MOCK_DATABASE_URL", "MOCK_FALHAS")

    def __init__(self, nome, rotulo, sistemas_do_mock):
        self.nome = nome
        self.rotulo = rotulo
        self.sistemas_do_mock = sistemas_do_mock  # nomes de `mock.falhas.SISTEMAS` que esta integração lê
        super().__init__()

    def fora_do_ar(self):
        return any(falhas.fora_do_ar(sistema) for sistema in self.sistemas_do_mock)

    def testar(self, ambiente=None):
        dados_sinteticos.buscar_cliente(LOJISTA_DO_TESTE)  # levanta ConnectionError se o banco não responde
        return "Banco do mock respondeu."


CRM = registrar(ConectorInterno("crm", "CRM de atendimento", ("cadastro", "crm")))
SQL = registrar(
    ConectorInterno("sql", "Core de pagamentos, cadastro, cobrança e disputas", ("cadastro", "core", "cobranca", "disputas"))
)
BIGQUERY = registrar(ConectorInterno("bigquery", "Base analítica", ("analitica",)))
DATAHUB = registrar(ConectorInterno("datahub", "Dicionário de dados", ()))  # lê só a descrição do esquema
