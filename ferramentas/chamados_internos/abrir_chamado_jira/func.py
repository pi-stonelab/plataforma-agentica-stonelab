"""Prepara um chamado interno no Jira (projeto e tipo da lista do .env); abre só quando quem pediu confirma."""

from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.integracoes.jira.conector import CONECTOR as JIRA
from ferramentas.integracoes.jira.conector import FONTE_REAL, FONTE_SIMULADA
from ferramentas.mensagens_internas import (
    ASSINATURA_DO_CHAMADO,
    assinado,
    com_rotulo,
    escolher_da_lista,
    exigir_integracao,
    liberados_para_o_agente,
    texto_mascarado,
)

TAMANHO_DO_RESUMO = 200
TAMANHO_DA_DESCRICAO = 4000


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
    sai_da_plataforma = True
    titulo = "Abrir chamado no Jira"
    descricao_para_pessoa = "Prepara um chamado interno no Jira; ele só é aberto depois que você confirma."
    rotulos_da_previa = {"projeto": "Projeto (Jira)", "tipo": "Tipo", "resumo": "Resumo", "texto": "Descrição"}
    parametros = {
        "resumo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_RESUMO},
        "descricao": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DA_DESCRICAO},
        "projeto": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 10},
        "tipo": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 40},
    }

    def situacao_para_o_agente(self):
        projetos, tipos = JIRA.destinos()
        texto = liberados_para_o_agente(JIRA, "Projetos", projetos)
        return f"{texto} Tipos de chamado: {', '.join(tipos) or 'nenhum'} (o primeiro é o padrão)."

    def montar(self, argumentos, usuario):
        exigir_integracao(JIRA)
        projetos, tipos = JIRA.destinos()
        projeto = escolher_da_lista(argumentos.get("projeto") or projetos[0], projetos, "Projeto")
        tipo = escolher_da_lista(argumentos.get("tipo") or tipos[0], tipos, "Tipo de chamado")
        resumo = texto_mascarado(argumentos["resumo"], "O resumo", uma_linha=True)
        descricao = assinado(texto_mascarado(argumentos["descricao"], "A descrição"), usuario, ASSINATURA_DO_CHAMADO)
        conteudo = {"projeto": projeto, "tipo": tipo, "resumo": resumo, "texto": descricao}
        previa = {**conteudo, "projeto": com_rotulo(projeto, JIRA.nomes_dos_projetos())}
        return conteudo, previa

    def efetivar(self, conteudo, usuario):
        simulado = JIRA.demonstracao()
        try:
            chave = JIRA.abrir(conteudo["projeto"], conteudo["tipo"], conteudo["resumo"], conteudo["texto"])
        except DestinoNaoPermitido:  # o projeto ou o tipo saiu da lista do .env depois da prévia
            mensagem = "Esse projeto ou tipo não está mais liberado. Nada foi criado."
            raise ErroFerramenta("parametro_invalido", mensagem) from None
        return {"chave_jira": chave, "fonte": FONTE_SIMULADA if simulado else FONTE_REAL}

    def mensagem_ao_confirmar(self, dados):
        frase = f"Chamado {dados['chave_jira']} aberto."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if dados["fonte"] == FONTE_SIMULADA else frase

    def referencia_do_resultado(self, dados):
        return dados["chave_jira"]  # id neutro: liga o chamado do Jira a quem confirmou, no registro


FERRAMENTA = AbrirChamadoJira()
