"""Chamados por fila num período, com quantos estouraram o prazo do SLA (cenário 11 e onboarding 4)."""

from datetime import timedelta

from ferramentas import dados_sinteticos
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.indicadores import ontem, periodo_pedido

AVISO = (
    "Base analítica: os números vão até a data_corte (ontem). Um chamado que estourou o prazo hoje ainda não "
    "aparece aqui; para o que está acontecendo agora, consulte o chamado no CRM."
)


def _inicio_da_semana_de(dia):
    """Segunda-feira da semana de `dia`: o "nesta semana" do supervisor, que termina em ontem. Numa segunda-feira
    ontem é domingo, então vale a semana que acabou (nunca um início depois do fim)."""
    return dia - timedelta(days=dia.weekday())


class ResumirVolumeChamados(Ferramenta):
    nome = "resumir_volume_chamados"
    descricao_para_pessoa = "Mostra quantos chamados cada fila abriu e resolveu e quantos estouraram o prazo."
    area = "dados_e_indicadores"
    acesso = "leitura"
    integracoes = ("bigquery",)
    nivel_minimo = "N2"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("indicador_agregado",)
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    campos_liberados = ("aviso", "data_fim", "data_inicio")  # texto escrito pela plataforma, não pelo lojista
    parametros = {
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "prioridade": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
    }

    def rodar(self, argumentos, usuario):
        prioridade = argumentos.get("prioridade")
        if prioridade is not None and prioridade not in dados_sinteticos.PRIORIDADES:
            opcoes = ", ".join(dados_sinteticos.PRIORIDADES)
            raise ErroFerramenta("parametro_invalido", f"A prioridade deve ser uma destas: {opcoes}.")
        fim_padrao = argumentos.get("data_fim", ontem())
        padrao = {"data_inicio": _inicio_da_semana_de(fim_padrao), "data_fim": fim_padrao}
        inicio, fim = periodo_pedido(padrao | argumentos, dias_padrao=7)
        resposta = dados_sinteticos.chamados_por_fila(inicio, fim, prioridade)
        filas = resposta["itens"]
        return {
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            "data_corte": resposta["data_corte"],
            "prioridade": prioridade,
            "filas": filas,
            "total": {
                chave: sum(fila[chave] for fila in filas)
                for chave in ("quantidade_abertos", "quantidade_resolvidos", "quantidade_estourados")
            },
            "aviso": AVISO,
        }


FERRAMENTA = ResumirVolumeChamados()
