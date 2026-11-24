"""Eventos da agenda da conta (Google Calendar ou Outlook) de quem pede, num período."""

from datetime import timedelta

from ferramentas import lojista
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.escritorio import (
    INTEGRACOES,
    PARAMETRO_SERVICO,
    conector_da_pessoa,
    exigir_limite,
    mascarar_celula,
    situacao_das_contas,
)

LIMITE_PADRAO = 10
LIMITE_MAXIMO = 25
DIAS_PADRAO = 7
DIAS_NO_MAXIMO = 31


class ListarEventosAgenda(Ferramenta):
    nome = "listar_eventos_agenda"
    area = "documentos_e_agenda"
    acesso = "leitura"
    integracoes = INTEGRACOES
    integracoes_alternativas = True
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("agenda_pessoal",)
    sensibilidade = "interna"
    conteudo_terceiros = True  # convite de fora entra na agenda sozinho: o título é texto de terceiro
    status = "ativa"
    descricao_para_pessoa = "Mostra os eventos da sua agenda (Google ou Microsoft) num período."
    parametros = {
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
        "servico": PARAMETRO_SERVICO,
    }

    def situacao_para_o_agente(self):
        return situacao_das_contas()

    def rodar(self, argumentos, usuario):
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        data_inicio = argumentos.get("data_inicio") or conta.hoje()
        data_fim = argumentos.get("data_fim") or data_inicio + timedelta(days=DIAS_PADRAO - 1)
        lojista.conferir_ordem_das_datas(data_inicio, data_fim)
        if (data_fim - data_inicio).days >= DIAS_NO_MAXIMO:
            raise ErroFerramenta("parametro_invalido", f"O período pode ter até {DIAS_NO_MAXIMO} dias.")
        limite = exigir_limite(argumentos.get("limite"), LIMITE_PADRAO, LIMITE_MAXIMO)
        eventos, truncado = conta.eventos(usuario.id_usuario, data_inicio, data_fim, limite)
        return {
            "data_inicio": data_inicio.isoformat(),
            "data_fim": data_fim.isoformat(),
            "eventos": [
                {**evento, "titulo": mascarar_celula(evento["titulo"]), "local": mascarar_celula(evento["local"])}
                for evento in eventos
            ],
            "total": len(eventos),
            "truncado": truncado,
            "fonte": conta.fonte(),
        }


FERRAMENTA = ListarEventosAgenda()
