"""Prepara a antecipação pedida pelo lojista num chamado; executa no core simulado só quando o N2 confirma."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.apresentacao import data_br, decimal_br
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.dados_sinteticos import reais
from ferramentas.mascara import mascarar_valor

LIVRE = "texto_livre"
ALCANCE_TODA_A_AGENDA = "Toda a agenda disponível"


class ExecutarAntecipacao(FerramentaComConfirmacao):
    nome = "executar_antecipacao"
    area = "financeiro"
    integracoes = ("crm", "sql")
    nivel_minimo = "N2"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("cadastral", "chamado", "agenda_recebiveis")
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "valor_antecipado", "desconto", "data_credito", "taxa_mensal_percentual",
        "alcance", "pedido_do_lojista",
    )
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "nas antecipações do lojista"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Executar antecipação"
    mensagem_feito = "Antecipação executada."
    descricao_para_pessoa = (
        "Prepara a antecipação que o lojista pediu num chamado, com o valor líquido e a data do crédito; ela só é "
        "executada depois que você confirma."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_chamado": "Chamado do pedido",
        "pedido_do_lojista": "O que o lojista pediu",
        "alcance": "Quanto antecipar",
        "quantidade_de_parcelas": "Parcelas",
        "valor_antecipado": "Valor antecipado",
        "taxa_mensal_percentual": "Taxa ao mês (%)",
        "desconto": "Desconto",
        "valor_liquido": "Valor líquido",
        "data_credito": "Crédito em",
    }
    campos_so_da_interface = ("pedido_do_lojista",)  # o texto é do chamado: a pessoa lê, o modelo não precisa
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
        "valor_maximo": {"tipo": "decimal", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo, id_chamado = argumentos["id_cliente"], argumentos["id_chamado"]
        valor_maximo = escritas_sinteticas.centavos(argumentos.get("valor_maximo"), "valor_maximo")
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
        conteudo = {"codigo": codigo, "id_chamado": id_chamado, "valor_maximo_centavos": valor_maximo}
        # O ensaio roda a execução inteira e desfaz: os números da prévia são os que a confirmação vai gravar.
        ensaio = escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)
        previa = {
            "id_cliente": codigo,
            "id_chamado": id_chamado,
            "pedido_do_lojista": mascarar_valor(LIVRE, chamado.get("resumo") or ""),
            "alcance": ALCANCE_TODA_A_AGENDA if valor_maximo is None else f"Até {reais(valor_maximo)}, parcelas inteiras",
            "quantidade_de_parcelas": ensaio["quantidade_de_parcelas"],
            "valor_antecipado": ensaio["valor_antecipado"],
            "taxa_mensal_percentual": decimal_br(dados_sinteticos.simulacao_de_antecipacao(codigo)["taxa_mensal_percentual"]),
            "desconto": ensaio["desconto"],
            "valor_liquido": ensaio["valor_liquido"],
            "data_credito": data_br(ensaio["data_credito"]),
        }
        return conteudo, previa

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado do pedido: liga a execução a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        # As recusas do §7.4 e as parcelas são conferidas de novo dentro da transação da execução.
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.executar_antecipacao(
            conteudo["codigo"], conteudo["id_chamado"], usuario.id_usuario, conteudo["valor_maximo_centavos"]
        )


FERRAMENTA = ExecutarAntecipacao()
