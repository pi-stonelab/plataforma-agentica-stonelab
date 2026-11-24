"""Prepara a abertura de um chamado no CRM simulado; abre só quando quem pediu confirma (duas fases)."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.apresentacao import (
    ROTULOS_DA_PRIORIDADE,
    ROTULOS_DO_NIVEL,
    data_e_hora_br,
)
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.mascara import mascarar_valor

TAMANHO_RESUMO = 1000
LIVRE = "texto_livre"
CANAL_PADRAO = "whatsapp"
NOMES_DO_CANAL = {"whatsapp": "WhatsApp", "telefone": "Telefone", "chat": "Chat", "email": "E-mail"}
CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO = escritas_sinteticas.CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO
CATEGORIAS = tuple(c for c in escritas_sinteticas.CATEGORIAS_DE_CHAMADO if c != CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO)


class AbrirChamado(FerramentaComConfirmacao):
    nome = "abrir_chamado"
    area = "atendimento"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("cadastral", "chamado")
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "nivel_atendimento", "atencao")
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "na lista de chamados do lojista"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Abrir chamado"
    mensagem_feito = "Chamado aberto."
    descricao_para_pessoa = "Prepara um chamado novo para o lojista; ele só é aberto depois que você confirma."
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "categoria": "Categoria",
        "resumo": "Resumo",
        "canal": "Canal",
        "prioridade": "Prioridade",
        "nivel_atendimento": "Nível",
        "prazo_em": "Prazo",
        "atencao": "Atenção",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "categoria": {"tipo": "texto", "obrigatorio": True},
        "resumo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_RESUMO},
        "canal": {"tipo": "texto", "obrigatorio": False},
        "impede_vender": {"tipo": "texto", "obrigatorio": False},
        "valor_envolvido": {"tipo": "decimal", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo, categoria = argumentos["id_cliente"], argumentos["categoria"]
        canal = argumentos.get("canal") or CANAL_PADRAO
        if categoria == CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO:
            raise ErroFerramenta(
                "parametro_invalido", "Pedido de antecipação se registra com registrar_pedido_antecipacao, não aqui."
            )
        if categoria not in CATEGORIAS:
            raise ErroFerramenta("parametro_invalido", f"Categoria desconhecida. Use uma destas: {', '.join(CATEGORIAS)}.")
        if canal not in escritas_sinteticas.CANAIS:
            raise ErroFerramenta("parametro_invalido", f"Canal desconhecido. Use: {', '.join(escritas_sinteticas.CANAIS)}.")
        resumo = mascarar_valor(LIVRE, argumentos["resumo"])
        if not resumo:
            raise ErroFerramenta("parametro_invalido", "O resumo não pode ficar vazio.")
        impede_vender = escritas_sinteticas.sim_ou_nao(argumentos.get("impede_vender"), "impede_vender")
        valor_envolvido = escritas_sinteticas.centavos(argumentos.get("valor_envolvido"), "valor_envolvido")
        lojista.exigir_acesso(usuario, codigo)
        classe = escritas_sinteticas.classificar_chamado(
            categoria, dados_sinteticos.carteira_do_lojista(codigo)["carteira"], impede_vender, valor_envolvido
        )
        conteudo = {
            "codigo": codigo,
            "categoria": categoria,
            "resumo": resumo,
            "canal": canal,
            "impede_vender": impede_vender,
            "valor_envolvido_centavos": valor_envolvido,
        }
        previa = {
            "id_cliente": codigo,
            "categoria": categoria,
            "resumo": resumo,
            "canal": NOMES_DO_CANAL[canal],
            "prioridade": ROTULOS_DA_PRIORIDADE[classe["prioridade"]],
            "nivel_atendimento": ROTULOS_DO_NIVEL[classe["nivel_atendimento"]],
            "prazo_em": data_e_hora_br(classe["prazo_em"]),
        }
        if (duplicado := escritas_sinteticas.aviso_de_duplicado(codigo, categoria)) is not None:
            previa["atencao"] = duplicado
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado aberto: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])  # a carteira pode ter mudado desde a prévia
        chamado = escritas_sinteticas.abrir_chamado(
            conteudo["codigo"], conteudo["categoria"], conteudo["resumo"], conteudo["canal"], usuario.id_usuario,
            conteudo["impede_vender"], conteudo["valor_envolvido_centavos"],
        )
        return {
            "id_chamado": chamado["codigo"],
            "protocolo": chamado["protocolo"],
            "situacao": chamado["situacao"],
            "nivel_atendimento": chamado["nivel_atendimento"],
            "prazo_em": chamado["prazo_em"],
        }


FERRAMENTA = AbrirChamado()
