"""Prepara um chamado interno no Jira (projeto e tipo da lista do .env); abre só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.integracoes.jira.conector import FONTE_REAL, FONTE_SIMULADA
from ferramentas.mensagens_internas import exigir_integracao, texto_mascarado

TAMANHO_DO_RESUMO = 200
TAMANHO_DA_DESCRICAO = 4000


def _da_lista(valor, liberados, rotulo):
    """O item da lista do .env que casa com `valor` (sem diferença de maiúsculas), na grafia da lista."""
    por_chave = {item.casefold(): item for item in liberados}
    escolhido = por_chave.get(valor.strip().casefold())
    if escolhido is None:
        lista = ", ".join(liberados) or "nenhum"
        raise ErroFerramenta("parametro_invalido", f"{rotulo} fora da lista desta plataforma. Liberados: {lista}.")
    return escolhido


class AbrirChamadoJira(FerramentaComConfirmacao):
    nome = "abrir_chamado_jira"
    area = "chamados_internos"
    integracoes = ("jira",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("chamado_interno",)
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "projeto")
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Abrir chamado no Jira"
    descricao_para_pessoa = "Prepara um chamado interno no Jira; ele só é aberto depois que você confirma."
    rotulos_da_previa = {"projeto": "Projeto", "tipo": "Tipo", "resumo": "Resumo", "texto": "Descrição"}
    parametros = {
        "resumo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_RESUMO},
        "descricao": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DA_DESCRICAO},
        "projeto": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 10},
        "tipo": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 40},
    }

    def montar(self, argumentos, usuario):
        exigir_integracao(JIRA)
        projetos, tipos = JIRA.destinos()
        projeto = _da_lista(argumentos.get("projeto") or projetos[0], projetos, "Projeto")
        tipo = _da_lista(argumentos.get("tipo") or tipos[0], tipos, "Tipo de chamado")
        resumo = texto_mascarado(argumentos["resumo"], "O resumo", uma_linha=True)
        descricao = texto_mascarado(argumentos["descricao"], "A descrição")
        conteudo = {"projeto": projeto, "tipo": tipo, "resumo": resumo, "texto": descricao}
        return conteudo, dict(conteudo)

    def efetivar(self, conteudo, usuario):
        simulado = JIRA.modo() == "simulado"
        try:
            chave = JIRA.abrir(conteudo["projeto"], conteudo["tipo"], conteudo["resumo"], conteudo["texto"])
        except DestinoNaoPermitido:  # o projeto ou o tipo saiu da lista do .env depois da prévia
            mensagem = "Esse projeto ou tipo não está mais liberado. Nada foi criado."
            raise ErroFerramenta("parametro_invalido", mensagem) from None
        return {"chave_jira": chave, "fonte": FONTE_SIMULADA if simulado else FONTE_REAL}


FERRAMENTA = AbrirChamadoJira()
