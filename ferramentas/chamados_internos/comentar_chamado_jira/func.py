"""Prepara um comentário num chamado interno do Jira (projeto liberado); grava só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.integracoes.jira.conector import FONTE_REAL, FONTE_SIMULADA
from ferramentas.mensagens_internas import exigir_integracao, texto_mascarado

TAMANHO_DO_COMENTARIO = 2000


class ComentarChamadoJira(FerramentaComConfirmacao):
    nome = "comentar_chamado_jira"
    area = "chamados_internos"
    integracoes = ("jira",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("chamado_interno",)
    campos_liberados = FerramentaComConfirmacao.campos_liberados
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Comentar chamado no Jira"
    descricao_para_pessoa = "Prepara um comentário num chamado interno do Jira; ele só é gravado depois que você confirma."
    rotulos_da_previa = {"chave_jira": "Chamado", "resumo": "Resumo do chamado", "texto": "Comentário"}
    parametros = {
        "chave": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 20},
        "texto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_COMENTARIO},
    }

    def montar(self, argumentos, usuario):
        exigir_integracao(JIRA)
        chave = JIRA.chave_para_ferramenta(argumentos["chave"])
        texto = texto_mascarado(argumentos["texto"], "O comentário")
        chamado = JIRA.chamado(chave)  # a prévia mostra de qual chamado se trata, para conferir antes de gravar
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira.")
        conteudo = {"chave": chave, "texto": texto}
        return conteudo, {"chave_jira": chave, "resumo": chamado["resumo"], "texto": texto}

    def efetivar(self, conteudo, usuario):
        simulado = JIRA.modo() == "simulado"
        try:
            JIRA.comentar(conteudo["chave"], conteudo["texto"])
        except DestinoNaoPermitido:  # o projeto saiu da lista do .env depois da prévia
            raise ErroFerramenta("parametro_invalido", "Esse projeto não está mais liberado. Nada foi gravado.") from None
        return {"chave_jira": conteudo["chave"], "fonte": FONTE_SIMULADA if simulado else FONTE_REAL}


FERRAMENTA = ComentarChamadoJira()
