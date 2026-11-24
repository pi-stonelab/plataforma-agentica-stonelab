"""Prepara o registro do pedido de antecipação do lojista num chamado para o N2 executar; abre o chamado só
quando quem pediu confirma (duas fases). Não antecipa nada."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.mascara import mascarar_valor

CATEGORIA = escritas_sinteticas.CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO
NIVEL_QUE_EXECUTA = "N2"  # o N1 só simula e registra o pedido; quem executa é o N2 (DOC-MOCK §7.4)
TAMANHO_RESUMO = 1000
LIVRE = "texto_livre"
CANAL_PADRAO = "whatsapp"


class RegistrarPedidoAntecipacao(FerramentaComConfirmacao):
    nome = "registrar_pedido_antecipacao"
    area = "atendimento"
    integracoes = ("crm", "sql")
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("cadastral", "chamado", "agenda_recebiveis")
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "nivel_atendimento", "valor_antecipado", "desconto", "data_credito",
    )
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Registrar pedido de antecipação"
    mensagem_feito = "Pedido registrado para o N2."
    descricao_para_pessoa = (
        "Registra num chamado o pedido de antecipação do lojista, com a simulação, para o N2 executar; nada é "
        "antecipado aqui, e o chamado só é aberto depois que você confirma."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "resumo": "Pedido do lojista",
        "canal": "Canal",
        "valor_antecipado": "Valor a antecipar",
        "desconto": "Desconto",
        "valor_liquido": "Valor líquido",
        "data_credito": "Crédito em",
        "nivel_atendimento": "Vai para",
        "prazo_em": "Prazo do chamado",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "resumo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_RESUMO},
        "canal": {"tipo": "texto", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        canal = argumentos.get("canal") or CANAL_PADRAO
        if canal not in escritas_sinteticas.CANAIS:
            raise ErroFerramenta("parametro_invalido", f"Canal desconhecido. Use: {', '.join(escritas_sinteticas.CANAIS)}.")
        resumo = mascarar_valor(LIVRE, argumentos["resumo"])
        if not resumo:
            raise ErroFerramenta("parametro_invalido", "Escreva o pedido do lojista no resumo.")
        lojista.exigir_acesso(usuario, codigo)
        motivos = dados_sinteticos.motivos_de_recusa_da_antecipacao(codigo)
        if motivos:  # pedido que o N2 teria de recusar não vira chamado: o lojista ouve o motivo agora
            raise ErroFerramenta("parametro_invalido", f"Antecipação recusada: {', '.join(motivos)}.")
        simulacao = dados_sinteticos.simulacao_de_antecipacao(codigo)
        if not simulacao or not simulacao["quantidade_de_parcelas"]:
            raise ErroFerramenta("parametro_invalido", "Não há parcelas para antecipar.")
        classe = escritas_sinteticas.classificar_chamado(
            CATEGORIA, dados_sinteticos.carteira_do_lojista(codigo)["carteira"], False, None, NIVEL_QUE_EXECUTA
        )
        conteudo = {"codigo": codigo, "resumo": resumo, "canal": canal}
        previa = {
            "id_cliente": codigo,
            "resumo": resumo,
            "canal": canal,
            "valor_antecipado": simulacao["valor_antecipado"],
            "desconto": simulacao["desconto"],
            "valor_liquido": simulacao["valor_liquido"],
            "data_credito": simulacao["data_credito"],
            "nivel_atendimento": classe["nivel_atendimento"],
            "prazo_em": classe["prazo_em"],
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado do pedido: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        chamado = escritas_sinteticas.abrir_chamado(
            conteudo["codigo"], CATEGORIA, conteudo["resumo"], conteudo["canal"], usuario.id_usuario, False, None,
            NIVEL_QUE_EXECUTA,
        )
        return {
            "id_chamado": chamado["codigo"],
            "protocolo": chamado["protocolo"],
            "nivel_atendimento": chamado["nivel_atendimento"],
            "prazo_em": chamado["prazo_em"],
        }


FERRAMENTA = RegistrarPedidoAntecipacao()
