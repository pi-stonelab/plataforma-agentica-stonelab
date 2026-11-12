"""Regras comuns das ferramentas que leem dados de um lojista: formato do código, escopo e janela.

Quem decide é a governança (função pura); aqui só se busca a carteira do lojista e se traduz a
decisão em erro. Lojista inexistente e lojista fora do escopo têm a MESMA resposta, para ninguém
descobrir por tentativa quais códigos existem (O13, A-15).

Vocabulário (I1 da crítica B): "cliente" e "lojista" são a mesma pessoa jurídica. O parâmetro que o
MODELO preenche se chama `id_cliente` (nome da ficha original, o que a Stone chama de cliente); o
valor dele é sempre o código do lojista, como `M00001`. Por dentro (mock, fachada, governança) o
mesmo valor se chama `codigo` (ou `codigo_lojista` quando há outro código por perto, como o do
chamado) e, nas colunas das tabelas, `id_lojista`. Nas ferramentas, `codigo = argumentos["id_cliente"]`
faz a ponte; `preparar` é o único lugar que lê o `id_cliente` das ferramentas que a usam.
"""

import re
from collections import namedtuple

from mock import regras

from ferramentas import dados_sinteticos, governanca
from ferramentas.base import ErroFerramenta

PADRAO_CODIGO = re.compile(r"M[0-9]{5}")
LIMITE_PADRAO = 20


def exigir_acesso(usuario, codigo):
    """Levanta ErroFerramenta se o código é inválido ou se o lojista não é acessível ao usuário."""
    if not PADRAO_CODIGO.fullmatch(codigo):
        raise ErroFerramenta("parametro_invalido", "O id_cliente deve ser como M00001.")
    carteira = dados_sinteticos.carteira_do_lojista(codigo)
    if governanca.lojista_no_escopo(usuario, carteira):
        return
    # Quem enxerga todas as carteiras não tem "fora do escopo": inexistente é só não encontrado.
    if carteira is None and governanca.escopo_do_usuario(usuario) == regras.ESCOPO_TODAS:
        raise ErroFerramenta("nao_encontrado", "Lojista não encontrado.")
    raise ErroFerramenta("permissao_negada", "Lojista fora da sua carteira.")


def periodo_permitido(usuario, data_inicio, data_fim):
    """Aplica a janela de dias do cargo (KAN-69) e devolve (data_inicio, data_fim) a consultar.

    Sem janela: o período pedido. Com janela: sem data_inicio, começa no início da janela; período
    pedido que sai da janela é negado (não vira lista vazia).
    """
    inicio_da_janela = governanca.inicio_da_janela(usuario)
    if inicio_da_janela is None:
        return data_inicio, data_fim
    fora = (data_inicio and data_inicio < inicio_da_janela) or (
        data_fim and data_fim < inicio_da_janela
    )
    if fora:
        dias = governanca.janela_dias(usuario)
        raise ErroFerramenta("permissao_negada", f"Seu cargo só consulta os últimos {dias} dias.")
    return data_inicio or inicio_da_janela, data_fim


def limite_pedido(argumentos, padrao=LIMITE_PADRAO):
    """Limite de linhas do pedido (`padrao` se faltar); fora de 1 a LIMITE_LINHAS é parâmetro inválido."""
    limite = argumentos.get("limite", padrao)
    if not 1 <= limite <= governanca.LIMITE_LINHAS:
        raise ErroFerramenta("parametro_invalido", "O limite deve ficar entre 1 e 50.")
    return limite


def conferir_ordem_das_datas(data_inicio, data_fim):
    """data_inicio depois de data_fim é parâmetro inválido (as duas são opcionais)."""
    if data_inicio and data_fim and data_inicio > data_fim:
        raise ErroFerramenta("parametro_invalido", "A data_inicio vem depois da data_fim.")


# O que as ferramentas de lojista precisam depois das checagens: já validado e dentro do escopo.
PedidoDoLojista = namedtuple("PedidoDoLojista", "codigo data_inicio data_fim limite")


def preparar(usuario, argumentos, *, com_periodo=False, limite_padrao=LIMITE_PADRAO):
    """Todas as checagens de uma ferramenta de lojista, sempre na mesma ordem (I7 da crítica B).

    1. `limite`; 2. ordem das datas (só `com_periodo`); 3. acesso ao lojista (formato, existência e
    escopo); 4. janela de dias do cargo (só `com_periodo`). Parâmetro inválido vem antes do acesso
    de propósito, e o acesso vem antes de qualquer consulta. Ferramenta nova de lojista chama esta
    função primeiro: assim não dá para esquecer `exigir_acesso`.
    """
    codigo = argumentos["id_cliente"]
    limite = limite_pedido(argumentos, limite_padrao)
    data_inicio = argumentos.get("data_inicio") if com_periodo else None
    data_fim = argumentos.get("data_fim") if com_periodo else None
    conferir_ordem_das_datas(data_inicio, data_fim)
    exigir_acesso(usuario, codigo)
    if com_periodo:
        data_inicio, data_fim = periodo_permitido(usuario, data_inicio, data_fim)  # O4
    return PedidoDoLojista(codigo, data_inicio, data_fim, limite)
