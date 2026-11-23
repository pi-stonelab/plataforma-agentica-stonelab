"""Artigos de ajuda da Stone simulada (dúvidas frequentes dos lojistas): texto público escrito pela equipe."""

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta

LIMITE_PADRAO = 3
LIMITE_MAXIMO = 10  # artigos inteiros: mais do que isso só enche o contexto do modelo
TAMANHO_MINIMO_DO_TERMO = 3


class ConsultarBaseConhecimento(Ferramenta):
    nome = "consultar_base_conhecimento"
    descricao_para_pessoa = "Procura a resposta para uma dúvida frequente nos artigos de ajuda."
    area = "atendimento"
    acesso = "leitura"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("base_conhecimento",)
    sensibilidade = "publica"
    conteudo_terceiros = False  # escrito pela equipe, não pelo lojista
    status = "ativa"
    parametros = {
        "termo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 100},
        "categoria": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 40},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        termo = argumentos["termo"]
        if len(termo) < TAMANHO_MINIMO_DO_TERMO:
            raise ErroFerramenta("parametro_invalido", "O termo deve ter pelo menos 3 letras, como maquininha.")
        limite = lojista.limite_pedido(argumentos, LIMITE_PADRAO)
        if limite > LIMITE_MAXIMO:
            raise ErroFerramenta("parametro_invalido", "O limite deve ficar entre 1 e 10.")
        artigos, total = dados_sinteticos.buscar_artigos(termo, argumentos.get("categoria"), limite)
        return {"artigos": artigos, "total_encontrado": total, "truncado": total > len(artigos)}


FERRAMENTA = ConsultarBaseConhecimento()
