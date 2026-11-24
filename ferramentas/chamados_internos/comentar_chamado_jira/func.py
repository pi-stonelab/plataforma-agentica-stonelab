"""Prepara um comentário num chamado interno do Jira (projeto liberado); grava só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.integracoes.jira.conector import FONTE_REAL, FONTE_SIMULADA
from ferramentas.mensagens_internas import (
    ASSINATURA_DO_CHAMADO,
    assinado,
    exigir_integracao,
    liberados_para_o_agente,
    texto_mascarado,
)

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
    sai_da_plataforma = True
    titulo = "Comentar chamado no Jira"
    descricao_para_pessoa = "Prepara um comentário num chamado interno do Jira; ele só é gravado depois que você confirma."
    rotulos_da_previa = {"chave_jira": "Chamado", "resumo": "Resumo do chamado", "texto": "Comentário"}
    # O resumo vem do Jira (texto de terceiro): a pessoa confere no cartão de qual chamado se trata, mas ele não
    # volta ao modelo (seria uma porta para instrução escondida na resposta de uma ferramenta de escrita).
    campos_so_da_interface = ("resumo",)
    parametros = {
        "chave": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 20},
        "texto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_COMENTARIO},
    }

    def situacao_para_o_agente(self):
        return liberados_para_o_agente(JIRA, "Projetos", JIRA.destinos()[0])

    def montar(self, argumentos, usuario):
        exigir_integracao(JIRA)
        chave = JIRA.chave_para_ferramenta(argumentos["chave"])
        texto = assinado(texto_mascarado(argumentos["texto"], "O comentário"), usuario, ASSINATURA_DO_CHAMADO)
        chamado = JIRA.chamado(chave)
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado no Jira.")
        conteudo = {"chave": chave, "texto": texto}
        return conteudo, {"chave_jira": chave, "resumo": chamado["resumo"], "texto": texto}

    def efetivar(self, conteudo, usuario):
        simulado = JIRA.demonstracao()
        try:
            JIRA.comentar(conteudo["chave"], conteudo["texto"])
        except DestinoNaoPermitido:  # o projeto saiu da lista do .env depois da prévia
            raise ErroFerramenta("parametro_invalido", "Esse projeto não está mais liberado. Nada foi gravado.") from None
        return {"chave_jira": conteudo["chave"], "fonte": FONTE_SIMULADA if simulado else FONTE_REAL}

    def mensagem_ao_confirmar(self, dados):
        frase = f"Comentário gravado no {dados['chave_jira']}."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if dados["fonte"] == FONTE_SIMULADA else frase

    def referencia_do_resultado(self, dados):
        return dados["chave_jira"]


FERRAMENTA = ComentarChamadoJira()
