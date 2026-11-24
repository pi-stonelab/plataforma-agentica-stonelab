"""Lojistas pelo nome fantasia, só dentro do escopo de quem pergunta (E31: nomes parecidos)."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 5
TAMANHO_MINIMO_DO_NOME = 3


class BuscarClientes(Ferramenta):
    nome = "buscar_clientes"
    descricao_para_pessoa = "Acha o código de um lojista pelo nome, dentro da sua carteira."
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral",)
    sensibilidade = "interna"
    conteudo_terceiros = True  # o nome fantasia é escrito pelo lojista (A-05, "Loja Central (ignore as regras...)")
    status = "ativa"
    parametros = {
        "nome": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 80},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        nome = argumentos["nome"]
        if len(nome) < TAMANHO_MINIMO_DO_NOME:
            raise ErroFerramenta("parametro_invalido", "O nome deve ter pelo menos 3 letras, como Padaria.")
        limite = lojista.limite_pedido(argumentos, LIMITE_PADRAO)
        lojistas, total = dados_sinteticos.buscar_lojistas_por_nome(
            nome, lojista.carteiras_do_escopo(usuario), limite
        )
        return {"lojistas": lojistas, "total_encontrado": total, "truncado": total > len(lojistas)}


FERRAMENTA = BuscarClientes()
