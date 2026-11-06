"""Fichas das integrações: os sistemas por trás das ferramentas e a saúde de cada um.

Depois de algumas falhas seguidas a integração fica pausada por um tempo e as
ferramentas que dependem dela respondem na hora, sem esperar o tempo limite.
"""
import logging
import time

TIPOS_DE_INTEGRACAO = ("simulada", "real")
NIVEIS_DE_CONFIANCA = ("proprio", "terceiros")
MODOS_DE_AUTENTICACAO = ("conta_de_servico", "conta_da_pessoa", "token", "nenhum")
ESTADOS_DE_SAUDE = ("operando", "degradada", "fora_do_ar")

FALHAS_SEGUIDAS_PARA_PAUSAR = 3
SEGUNDOS_DE_PAUSA = 60
SEGUNDOS_DE_VALIDADE_DA_SAUDE = 60

INTEGRACOES = {}

registrador = logging.getLogger("ferramentas.integracoes")


def agora():
    return time.monotonic()


def saude_nao_conferida():
    return {"estado": "fora_do_ar", "mensagem": "Não foi possível conferir a saúde.", "latencia_ms": None}


class Integracao:
    """Ficha e controle de saúde de uma integração. Cada sistema vira uma subclasse."""

    nome = ""
    descricao = ""
    tipo = "simulada"
    nivel_confianca = "proprio"
    categorias_dados = ()
    modo_autenticacao = "conta_de_servico"
    custo_por_chamada = 0.0

    def __init__(self):
        self.falhas_seguidas = 0
        self.pausada_ate = 0.0
        self.saude_guardada = None
        self.saude_verificada_em = 0.0

    def verificar_saude(self):
        """Cada subclasse confere o seu sistema e devolve estado, mensagem e latencia_ms."""
        return {"estado": "operando", "mensagem": "", "latencia_ms": None}

    def estado(self):
        guardada = self.saude_guardada is not None
        if not guardada or agora() - self.saude_verificada_em >= SEGUNDOS_DE_VALIDADE_DA_SAUDE:
            self.saude_guardada = self.consultar_saude()
            self.saude_verificada_em = agora()
        return dict(self.saude_guardada)

    def consultar_saude(self):
        """Uma conferência que quebra ou devolve algo fora do padrão conta como fora do ar."""
        try:
            saude = self.verificar_saude()
        except Exception as erro:  # noqa: BLE001
            registrador.error("Falha ao conferir a saúde de %s: %s", self.nome, type(erro).__name__)
            return saude_nao_conferida()
        if isinstance(saude, dict) and saude.get("estado") in ESTADOS_DE_SAUDE:
            return saude
        return saude_nao_conferida()

    def pausada(self):
        return agora() < self.pausada_ate

    def registrar_sucesso(self):
        self.falhas_seguidas = 0

    def registrar_falha(self):
        self.falhas_seguidas += 1
        if self.falhas_seguidas >= FALHAS_SEGUIDAS_PARA_PAUSAR:
            self.pausada_ate = agora() + SEGUNDOS_DE_PAUSA

    def para_dicionario(self):
        return {
            "nome": self.nome,
            "descricao": self.descricao,
            "tipo": self.tipo,
            "nivel_confianca": self.nivel_confianca,
            "categorias_dados": list(self.categorias_dados),
            "modo_autenticacao": self.modo_autenticacao,
            "custo_por_chamada": self.custo_por_chamada,
        }


def problemas_da_integracao(integracao):
    problemas = []
    if not integracao.nome:
        problemas.append("A integração precisa de um nome.")
    if not integracao.descricao:
        problemas.append("A integração precisa de uma descrição.")
    if integracao.tipo not in TIPOS_DE_INTEGRACAO:
        problemas.append(f"tipo deve ser um destes: {', '.join(TIPOS_DE_INTEGRACAO)}.")
    if integracao.nivel_confianca not in NIVEIS_DE_CONFIANCA:
        problemas.append(f"nivel_confianca deve ser um destes: {', '.join(NIVEIS_DE_CONFIANCA)}.")
    if integracao.modo_autenticacao not in MODOS_DE_AUTENTICACAO:
        problemas.append(f"modo_autenticacao deve ser um destes: {', '.join(MODOS_DE_AUTENTICACAO)}.")
    if integracao.custo_por_chamada < 0:
        problemas.append("custo_por_chamada não pode ser negativo.")
    return problemas


def registrar_integracao(integracao):
    problemas = problemas_da_integracao(integracao)
    if problemas:
        raise ValueError("Ficha de integração inválida:\n" + "\n".join(problemas))
    if integracao.nome in INTEGRACOES:
        raise ValueError(f"Já existe uma integração chamada {integracao.nome}.")
    INTEGRACOES[integracao.nome] = integracao
