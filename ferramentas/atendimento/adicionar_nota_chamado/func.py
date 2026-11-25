"""Prepara uma nota interna ou uma resposta ao lojista num chamado; grava só quando quem pediu confirma."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.mascara import mascarar_valor

TAMANHO_TEXTO = 2000
LIVRE = "texto_livre"
TIPO_PADRAO = "nota_interna"
ROTULOS_DO_TIPO = {"nota_interna": "Nota interna (só a equipe vê)", "resposta_ao_lojista": "Resposta ao lojista"}
NOMES_DO_CANAL = {"whatsapp": "WhatsApp", "telefone": "telefone", "chat": "chat", "email": "e-mail"}


class AdicionarNotaChamado(FerramentaComConfirmacao):
    nome = "adicionar_nota_chamado"
    area = "atendimento"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("chamado", "interacao")
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "tipo_da_nota", "destino")
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "no histórico do chamado"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Escrever no chamado"
    mensagem_feito = "Gravado no chamado."
    descricao_para_pessoa = (
        "Prepara uma nota interna ou uma resposta ao lojista num chamado; ela só entra no histórico depois que "
        "você revisa e confirma."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_chamado": "Chamado",
        "tipo_da_nota": "Tipo",
        "destino": "Quem recebe",
        "texto": "Texto",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
        "texto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_TEXTO},
        "tipo": {"tipo": "texto", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo, id_chamado = argumentos["id_cliente"], argumentos["id_chamado"]
        tipo = argumentos.get("tipo") or TIPO_PADRAO
        if tipo not in escritas_sinteticas.TIPOS_DE_NOTA:
            raise ErroFerramenta("parametro_invalido", "O tipo é nota_interna ou resposta_ao_lojista.")
        texto = mascarar_valor(LIVRE, argumentos["texto"])
        if not texto:
            raise ErroFerramenta("parametro_invalido", "O texto não pode ficar vazio.")
        lojista.exigir_acesso(usuario, codigo)
        if not dados_sinteticos.chamado_e_do_lojista(codigo, id_chamado):
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado para este lojista.")
        conteudo = {"codigo": codigo, "id_chamado": id_chamado, "texto": texto, "tipo": tipo}
        ensaio = escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        previa = {
            "id_cliente": codigo,
            "id_chamado": id_chamado,
            "tipo_da_nota": ROTULOS_DO_TIPO[tipo],
            "destino": _destino(ensaio),
            "texto": texto,
        }
        return conteudo, previa

    def mensagem_ao_confirmar(self, dados):
        if dados["tipo"] == "nota_interna":
            return "Nota interna gravada no chamado."
        return f"Resposta registrada no chamado, para sair ao lojista por {NOMES_DO_CANAL[dados['canal']]}."

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado que recebeu a nota: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        gravado = escritas_sinteticas.adicionar_nota(
            conteudo["codigo"], conteudo["id_chamado"], conteudo["texto"], conteudo["tipo"], usuario.id_usuario
        )
        return {"id_chamado": gravado["id_chamado"], "tipo": gravado["tipo"], "canal": gravado["canal"]}


def _destino(gravado):
    """Para onde a nota vai: só a equipe, ou o lojista pelo canal em que ele falou por último."""
    if gravado["tipo"] == "nota_interna":
        return "Só a equipe vê"
    return f"Vai ao lojista por {NOMES_DO_CANAL[gravado['canal']]}"


FERRAMENTA = AdicionarNotaChamado()
