import re
import threading

from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.mascara import mascarar_valor

PADRAO_NOME = re.compile(r"(?!.*[0-9]{6})[a-z][a-z0-9_]{2,59}")  # MED-2: sem 6+ dígitos seguidos
LIMITE_PEDIDOS = 1000
LIVRE = "texto_livre"
# [aqui conectamos com o back-end e o Jira: automação semanal que envia os pedidos acumulados a um card único, KAN-27]
PEDIDOS = []
TRAVA_DOS_PEDIDOS = threading.Lock()  # BAIXO-6: id, tamanho e inclusão em um passo só


class SolicitarFerramentaAusente(Ferramenta):
    nome = "solicitar_ferramenta_ausente"
    area = "plataforma"
    acesso = "escrita"
    integracoes = ()
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("pedido_plataforma",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    parametros = {
        "nome_sugerido": {"tipo": "texto", "obrigatorio": True},
        "descricao": {"tipo": "texto", "obrigatorio": True},
    }

    def rodar(self, argumentos, usuario):
        nome, descricao = argumentos["nome_sugerido"], argumentos["descricao"]
        if not PADRAO_NOME.fullmatch(nome) or mascarar_valor(LIVRE, nome) != nome or not descricao:
            raise ErroFerramenta("parametro_invalido", "Nome em minúsculas e descrição, por favor.")
        descricao = mascarar_valor(LIVRE, descricao)  # MED-1: a fila vai ao Jira
        with TRAVA_DOS_PEDIDOS:
            if len(PEDIDOS) >= LIMITE_PEDIDOS:
                raise ErroFerramenta("integracao_indisponivel", "A fila de pedidos está cheia.")
            id_pedido = f"PED-{len(PEDIDOS) + 1:04d}"
            PEDIDOS.append({"id_pedido": id_pedido, "nome_sugerido": nome, "descricao": descricao})
            vezes = sum(pedido["nome_sugerido"] == nome for pedido in PEDIDOS)
        return {"id_pedido": id_pedido, "nome_sugerido": nome, "vezes_pedida": vezes}


FERRAMENTA = SolicitarFerramentaAusente()
