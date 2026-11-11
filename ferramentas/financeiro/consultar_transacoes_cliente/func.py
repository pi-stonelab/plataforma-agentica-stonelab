import re

from ferramentas import dados_sinteticos, governanca
from ferramentas.base import ErroFerramenta, Ferramenta

PADRAO_ID_CLIENTE = re.compile(r"CLI-[0-9]{4}")
LIMITE_PADRAO = 20


class ConsultarTransacoesCliente(Ferramenta):
    nome = "consultar_transacoes_cliente"
    area = "financeiro"
    acesso = "leitura"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("financeiro",)
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        id_cliente = argumentos["id_cliente"]
        data_inicio = argumentos.get("data_inicio")
        data_fim = argumentos.get("data_fim")
        limite = argumentos.get("limite", LIMITE_PADRAO)
        if not PADRAO_ID_CLIENTE.fullmatch(id_cliente):
            raise ErroFerramenta("parametro_invalido", "O id_cliente deve ser como CLI-0001.")
        if not 1 <= limite <= governanca.LIMITE_LINHAS:
            raise ErroFerramenta("parametro_invalido", "O limite deve ficar entre 1 e 50.")
        if data_inicio and data_fim and data_inicio > data_fim:
            raise ErroFerramenta("parametro_invalido", "A data_inicio vem depois da data_fim.")
        if not governanca.cliente_no_escopo(usuario, id_cliente):
            raise ErroFerramenta("permissao_negada", "Cliente fora da sua carteira.")
        # [aqui conectamos com sql: banco simulado do back-end (KAN-32, Marcelo e Isabel)]
        if dados_sinteticos.buscar_cliente(id_cliente) is None:
            raise ErroFerramenta("nao_encontrado", "Cliente não encontrado.")
        transacoes, total = dados_sinteticos.buscar_transacoes(
            id_cliente, data_inicio, data_fim, limite
        )
        return {
            "id_cliente": id_cliente,
            "transacoes": transacoes,
            "total_encontrado": total,
            "truncado": total > len(transacoes),
        }


FERRAMENTA = ConsultarTransacoesCliente()
