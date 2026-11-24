"""Prepara a antecipação pedida pelo lojista num chamado; executa no core simulado só quando o N2 confirma."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao


class ExecutarAntecipacao(FerramentaComConfirmacao):
    nome = "executar_antecipacao"
    area = "financeiro"
    integracoes = ("crm", "sql")
    nivel_minimo = "N2"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral", "chamado", "agenda_recebiveis")
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "valor_antecipado", "desconto", "data_credito", "taxa_mensal_percentual",
    )
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Executar antecipação"
    mensagem_feito = "Antecipação executada."
    descricao_para_pessoa = (
        "Prepara a antecipação que o lojista pediu num chamado, com o valor líquido e a data do crédito; ela só é "
        "executada depois que você confirma."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_chamado": "Chamado do pedido",
        "quantidade_de_parcelas": "Parcelas",
        "valor_antecipado": "Valor antecipado",
        "taxa_mensal_percentual": "Taxa ao mês (%)",
        "desconto": "Desconto",
        "valor_liquido": "Valor líquido",
        "data_credito": "Crédito em",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
    }

    def montar(self, argumentos, usuario):
        codigo, id_chamado = argumentos["id_cliente"], argumentos["id_chamado"]
        lojista.exigir_acesso(usuario, codigo)
        chamado = dados_sinteticos.buscar_chamado(codigo, id_chamado)
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado para este lojista.")
        if chamado["categoria"] != escritas_sinteticas.CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO or chamado["situacao"] == "fechado":
            raise ErroFerramenta(
                "parametro_invalido", "O pedido do lojista precisa estar num chamado de Antecipação ainda aberto."
            )
        motivos = dados_sinteticos.motivos_de_recusa_da_antecipacao(codigo)
        if motivos:
            raise ErroFerramenta("parametro_invalido", f"Antecipação recusada: {', '.join(motivos)}.")
        simulacao = dados_sinteticos.simulacao_de_antecipacao(codigo)
        if not simulacao or not simulacao["quantidade_de_parcelas"]:
            raise ErroFerramenta("parametro_invalido", "Não há parcelas para antecipar.")
        conteudo = {"codigo": codigo, "id_chamado": id_chamado}
        previa = {
            "id_cliente": codigo,
            "id_chamado": id_chamado,
            "quantidade_de_parcelas": simulacao["quantidade_de_parcelas"],
            "valor_antecipado": simulacao["valor_antecipado"],
            "taxa_mensal_percentual": simulacao["taxa_mensal_percentual"],
            "desconto": simulacao["desconto"],
            "valor_liquido": simulacao["valor_liquido"],
            "data_credito": simulacao["data_credito"],
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado que originou a execução: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        # As recusas do §7.4 e as parcelas são conferidas de novo dentro da transação da execução.
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.executar_antecipacao(conteudo["codigo"], conteudo["id_chamado"], usuario.id_usuario)


FERRAMENTA = ExecutarAntecipacao()
