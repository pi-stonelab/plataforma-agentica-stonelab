"""Fachada de escrita do mock para as ferramentas: grava pelos `mock/escritas.py` e devolve dicts.

Só as ferramentas de escrita chamam, e só no `efetivar` (depois que a pessoa confirmou) ou para montar a
prévia sem gravar (`classificar_chamado`, `montar_acordo`, `faturas_do_acordo`). Nenhuma regra de permissão
aqui: cargo, área, categoria e carteira são da governança; as regras do negócio são do `mock/escritas.py`.

Regra do negócio violada (`EscritaRecusada`) vira `ErroDefinitivo` (um `ErroFerramenta`) com o mesmo tipo e a mesma frase. Banco ou
sistema simulado fora do ar vira `ConnectionError` (a transação foi desfeita: nada foi gravado). Valores em reais
saem como texto, como na fachada de leitura.

O banco é o de `mock.banco.url_de_escrita()`: no Postgres, o papel `mock_escrita`; no SQLite local, o mesmo
arquivo da leitura. Os testes ligam o mesmo engine da leitura com `configurar`.
"""

import logging

from mock import escritas
from mock.banco import criar_engine, url_de_escrita
from mock.falhas import SistemaIndisponivel
from sqlalchemy.exc import ArgumentError, DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as TempoEsgotadoNoPool

from ferramentas import dados_sinteticos
from ferramentas.base import CONFIRMACAO_EM_CURSO, EfeitoIncerto, ErroDefinitivo, ErroFerramenta
from ferramentas.dados_sinteticos import reais

logger = logging.getLogger(__name__)
# Falha do banco com a transação desfeita (nada foi gravado). A que acontece DEPOIS do commit é `GravacaoIncerta`.
FALHAS_DE_INTEGRACAO = (SistemaIndisponivel, DBAPIError, TempoEsgotadoNoPool)
CATEGORIAS_DE_CHAMADO = escritas.CATEGORIAS_DE_CHAMADO
CANAIS = escritas.CANAIS
TIPOS_DE_NOTA = escritas.TIPOS_DE_NOTA
NIVEIS_DE_ATENDIMENTO = escritas.ORDEM_DOS_NIVEIS
SITUACOES_DE_LIQUIDACAO_QUE_REPROCESSAM = escritas.regras.SITUACOES_DE_LIQUIDACAO_QUE_REPROCESSAM
CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO = escritas.regras.CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO
LIMITE_PARA_DUPLICADO = 50
RESPOSTAS_SIM = ("sim", "s")
RESPOSTAS_NAO = ("não", "nao", "n")
_CONEXAO = {"engine": None}


def configurar(origem):
    """Define o banco em que as escritas gravam: URL ou engine. Sem chamar, vale `url_de_escrita()`."""
    _CONEXAO["engine"] = criar_engine(origem) if isinstance(origem, str) else origem


def _engine():
    if _CONEXAO["engine"] is None:
        try:
            _CONEXAO["engine"] = criar_engine(url_de_escrita())
        except (ValueError, ArgumentError, OSError, OperationalError):  # a mensagem pode ter a senha
            raise ConnectionError("integração indisponível") from None
    return _CONEXAO["engine"]


def _gravar(operacao, *argumentos, **opcoes):
    """Grava com o id da confirmação em curso como chave de idempotência (sem confirmação, não confere duplicata).

    Regra violada vira `ErroDefinitivo`: a prévia foi montada com as mesmas regras, então se a confirmação recusa é
    porque o mundo mudou desde então, e repetir não adianta. Banco fora com a transação desfeita vira
    `ConnectionError` (nada gravado, pode repetir); falha depois do commit vira `EfeitoIncerto` (pode ter gravado).
    """
    try:
        with escritas.com_chave(CONFIRMACAO_EM_CURSO.get()):
            return operacao(_engine(), *argumentos, **opcoes)
    except escritas.EscritaRecusada as erro:
        raise ErroDefinitivo(erro.tipo_erro, erro.mensagem) from None
    except escritas.GravacaoIncerta:
        raise EfeitoIncerto() from None
    except FALHAS_DE_INTEGRACAO as erro:
        logger.warning("escrita no mock falhou: tipo=%s", type(erro).__name__)
        raise ConnectionError("integração indisponível") from None


def _gravar_leitura(leitura, *argumentos):
    """Leitura que a prévia faz no banco de escrita (soma de acordos, quem pode aprovar): sem chave de idempotência."""
    try:
        return leitura(_engine(), *argumentos)
    except FALHAS_DE_INTEGRACAO:
        raise ConnectionError("integração indisponível") from None


def _calcular(conta, *argumentos):
    """Conta sem banco (prévia): regra violada vira `ErroFerramenta`."""
    try:
        return conta(*argumentos)
    except escritas.EscritaRecusada as erro:
        raise ErroDefinitivo(erro.tipo_erro, erro.mensagem) from None


# --- CRM: chamados (DOC-MOCK §6.3 a §6.6) -------------------------------------------------------------


def classificar_chamado(categoria, fila, impede_vender, valor_envolvido_centavos, nivel_minimo=None):
    """Prioridade, nível e prazo que o chamado terá ao abrir agora (a mesma conta da gravação)."""
    classe = _calcular(escritas.classificar_chamado, categoria, fila, impede_vender, valor_envolvido_centavos, nivel_minimo)
    return {**classe, "prazo_em": classe["prazo_em"].isoformat()}


def abrir_chamado(codigo, categoria, resumo, canal, id_funcionario, impede_vender, valor_envolvido_centavos,
                  nivel_minimo=None):
    return _gravar(
        escritas.abrir_chamado, codigo, categoria, resumo, canal, id_funcionario,
        impede_vender=impede_vender, valor_envolvido_centavos=valor_envolvido_centavos, nivel_minimo=nivel_minimo,
    )


def chamados_abertos_da_categoria(codigo, categoria):
    """Códigos dos chamados ainda abertos do lojista nesta categoria (para a prévia avisar de duplicado)."""
    recentes, _ = dados_sinteticos.buscar_chamados(codigo, LIMITE_PARA_DUPLICADO)
    return [c["codigo"] for c in recentes if c["categoria"] == categoria and c["situacao"] != "fechado"]


def aviso_de_duplicado(codigo, categoria):
    """"Já existe chamado aberto ..." para a prévia, ou None. Só avisa: abrir outro é decisão da pessoa."""
    abertos = chamados_abertos_da_categoria(codigo, categoria)
    if not abertos:
        return None
    quantos = "um chamado aberto" if len(abertos) == 1 else f"{len(abertos)} chamados abertos"
    return f"Este lojista já tem {quantos} de {categoria}: {', '.join(abertos)}. Confira antes de abrir outro."


def adicionar_nota(codigo, id_chamado, texto, tipo, id_funcionario):
    """Texto que o agente escreveu e a pessoa confirmou: autor "agente", com o id de quem confirmou (§6.8)."""
    return _gravar(escritas.adicionar_nota, codigo, id_chamado, texto, tipo, id_funcionario, escrita_pelo_agente=True)


def atualizar_chamado(codigo, id_chamado, id_funcionario, nova_situacao, encaminhar_para, suspeita_fraude):
    return _gravar(
        escritas.atualizar_chamado, codigo, id_chamado, id_funcionario,
        nova_situacao=nova_situacao, encaminhar_para=encaminhar_para, suspeita_fraude=suspeita_fraude,
    )


# --- Core: liquidação e antecipação (DOC-MOCK §7.3 e §7.4) --------------------------------------------


def reprocessar_liquidacao(codigo, id_liquidacao, id_funcionario):
    feito = _gravar(escritas.reprocessar_liquidacao, codigo, id_liquidacao, id_funcionario)
    return {
        "id_liquidacao": feito["id_liquidacao"],
        "id_nova_tentativa": feito["id_nova_tentativa"],
        "data": feito["data"],
        "valor": reais(feito["valor_total_centavos"]),
    }


def executar_antecipacao(codigo, id_chamado, id_funcionario, valor_maximo_centavos=None):
    """Sem `valor_maximo_centavos`, antecipa toda a agenda disponível; com ele, só as parcelas mais próximas que cabem."""
    feito = _gravar(
        escritas.executar_antecipacao, codigo, id_chamado, id_funcionario, valor_maximo_centavos=valor_maximo_centavos
    )
    return {
        "codigo": feito["codigo"],
        "id_chamado": feito["id_chamado"],
        "quantidade_de_parcelas": feito["quantidade_de_parcelas"],
        "valor_antecipado": reais(feito["valor_antecipado_bruto_centavos"]),
        "desconto": reais(feito["desconto_antecipacao_centavos"]),
        "valor_liquido": reais(feito["valor_antecipado_liquido_centavos"]),
        "data_credito": feito["data_credito"],
    }


# --- Cobrança: acordos (DOC-MOCK §7.5 e §7.9) ---------------------------------------------------------


def faturas_do_acordo(codigo, codigos_das_faturas):
    """As faturas que entrariam no acordo: [{"codigo", "valor_centavos", "vencimento" (date)}]."""
    return _gravar(escritas.faturas_do_acordo, codigo, codigos_das_faturas)


def montar_acordo(faturas, numero_de_parcelas, entrada_percentual, perdoar_encargos, desconto_principal_percentual,
                  acordos_abertos=None):
    """Os números do acordo em centavos (a mesma conta da gravação), sem gravar. `acordos_abertos`
    (`acordos_abertos_do_lojista`) soma o que o lojista já tem para a alçada."""
    return _calcular(
        escritas.montar_acordo, faturas, numero_de_parcelas, entrada_percentual, perdoar_encargos,
        desconto_principal_percentual, acordos_abertos,
    )


def acordos_abertos_do_lojista(codigo):
    """{"quantidade", "valor_original_centavos", "valor_renegociado_centavos"} dos acordos pendentes ou ativos do
    lojista na janela da alçada (os pendentes vencidos não contam)."""
    return _gravar_leitura(escritas.acordos_abertos_do_lojista, codigo)


def aprovadores_possiveis(alcada, id_solicitante):
    """Quantas outras pessoas ativas podem aprovar um acordo desta alçada (zero: o acordo ficaria parado)."""
    return _gravar_leitura(escritas.aprovadores_possiveis, alcada, id_solicitante)


def retirar_acordo(codigo_acordo, id_solicitante):
    feito = _gravar(escritas.retirar_acordo, codigo_acordo, id_solicitante)
    return {
        "codigo": feito["codigo"],
        "id_cliente": feito["id_cliente"],
        "situacao": feito["situacao"],
        "valor_renegociado": reais(feito["valor_renegociado_centavos"]),
        "faturas": feito["faturas"],
    }


def registrar_acordo(codigo, codigos_das_faturas, numero_de_parcelas, entrada_percentual, perdoar_encargos,
                     desconto_principal_percentual, id_solicitante):
    feito = _gravar(
        escritas.registrar_acordo, codigo, tuple(codigos_das_faturas), numero_de_parcelas, entrada_percentual,
        perdoar_encargos, desconto_principal_percentual, id_solicitante,
    )
    return {"codigo": feito["codigo"], "situacao": feito["situacao"], "faturas": feito["faturas"], **numeros_em_reais(feito)}


def decidir_acordo(codigo_acordo, aprovar, id_aprovador):
    feito = _gravar(escritas.decidir_acordo, codigo_acordo, aprovar, id_aprovador)
    return {
        "codigo": feito["codigo"],
        "id_cliente": feito["id_cliente"],
        "situacao": feito["situacao"],
        "valor_renegociado": reais(feito["valor_renegociado_centavos"]),
        "faturas": feito["faturas"],
    }


def numeros_em_reais(numeros):
    """Os números de `montar_acordo` como a pessoa lê (centavos viram "R$ ...")."""
    return {
        "valor_original": reais(numeros["valor_original_centavos"]),
        "encargos": reais(numeros["encargos_centavos"]),
        "perdao_encargos": reais(numeros["perdao_encargos_centavos"]),
        "desconto_principal": reais(numeros["desconto_principal_centavos"]),
        "valor_renegociado": reais(numeros["valor_renegociado_centavos"]),
        "entrada": reais(numeros["entrada_centavos"]),
        "numero_de_parcelas": numeros["numero_de_parcelas"],
        "valor_da_parcela": reais(numeros["valor_da_parcela_centavos"]),
        "valor_da_ultima_parcela": reais(numeros["valor_da_ultima_parcela_centavos"]),
        "alcada": numeros["alcada"],
    }


def alcadas_do_cargo(cargo):
    """As alçadas de acordo que o cargo fecha sozinho (vazia: o cargo não negocia)."""
    return escritas.regras.ALCADAS_DE_ACORDO_DO_CARGO.get(cargo, ())



def sim_ou_nao(valor, nome):
    """Parâmetro de sim ou não ("sim", "não"; ausente é não)."""
    if valor is None:
        return False
    texto = valor.strip().lower()
    if texto in RESPOSTAS_SIM:
        return True
    if texto in RESPOSTAS_NAO:
        return False
    raise ErroFerramenta("parametro_invalido", f"O parâmetro {nome} deve ser sim ou não.")


def centavos(valor, nome):
    """Valor em reais (o decimal do parâmetro) em centavos inteiros; ausente é None, negativo é recusado."""
    if valor is None:
        return None
    if valor < 0:
        raise ErroFerramenta("parametro_invalido", f"O parâmetro {nome} não pode ser negativo.")
    return int((valor * 100).to_integral_value())


def proximo_dia_util():
    """O dia em que a nova tentativa de uma liquidação cai (a mesma conta da gravação), em ISO."""
    return escritas.proximo_dia_util().isoformat()


def ensaiar(operacao, *argumentos, **opcoes):
    """Roda uma operação desta fachada com todas as regras e desfaz tudo no fim (para a prévia). Regra violada
    levanta o mesmo `ErroFerramenta` que a confirmação levantaria."""
    return escritas.ensaiar(operacao, *argumentos, **opcoes)
