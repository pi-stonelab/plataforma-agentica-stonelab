"""Catálogo de ferramentas e as quatro funções que as outras frentes usam.

    listar_para_agente(usuario)  ferramentas que o agente pode ver, para montar o prompt
    executar(nome, argumentos, usuario, contexto)  roda uma ferramenta e devolve o retorno padrão
    listar_fichas(usuario)  fichas para a interface montar o catálogo
    estado_integracoes()  saúde de cada integração

O contexto é opcional: um dicionário com execucao_id, passo e agente_id, usado no registro.
"""
from ferramentas import integracoes, registro_chamada
from ferramentas.base import Ferramenta, retorno_erro, validar_ficha

CATALOGO = {}

CAMPOS_DA_FICHA_RESUMIDA = (
    "nome",
    "descricao",
    "categoria",
    "tipo_acesso",
    "sensibilidade",
    "niveis_permitidos",
    "areas_permitidas",
)


def registrar_ferramenta(ferramenta):
    if not isinstance(ferramenta, Ferramenta):
        raise TypeError("Só é possível registrar uma subclasse de Ferramenta.")
    problemas = validar_ficha(ferramenta)
    if problemas:
        raise ValueError(f"Ficha inválida em {ferramenta.nome or 'ferramenta sem nome'}:\n" + "\n".join(problemas))
    if ferramenta.nome in CATALOGO:
        raise ValueError(f"Já existe uma ferramenta chamada {ferramenta.nome}.")
    CATALOGO[ferramenta.nome] = ferramenta


def listar_para_agente(usuario):
    """Só as ferramentas ativas que este usuário pode usar. O agente não vê as outras."""
    descricoes = []
    for nome in sorted(CATALOGO):
        ferramenta = CATALOGO[nome]
        if ferramenta.status == "ativa" and ferramenta.usuario_pode_usar(usuario):
            descricoes.append(ferramenta.descricao_para_agente())
    return descricoes


def listar_fichas(usuario):
    """Ficha completa das liberadas e resumida das bloqueadas, para a interface mostrar o cadeado."""
    fichas = []
    for nome in sorted(CATALOGO):
        ferramenta = CATALOGO[nome]
        if ferramenta.status != "ativa":
            continue
        ficha = ferramenta.para_dicionario()
        liberada = ferramenta.usuario_pode_usar(usuario)
        if not liberada:
            ficha = {campo: ficha[campo] for campo in CAMPOS_DA_FICHA_RESUMIDA}
        ficha["liberada_para_voce"] = liberada
        fichas.append(ficha)
    return fichas


def executar(nome, argumentos, usuario, contexto=None):
    ferramenta = CATALOGO.get(nome) if isinstance(nome, str) else None
    if ferramenta is None:
        retorno = retorno_erro("ferramenta_nao_encontrada", "Essa ferramenta não existe.")
        registro_chamada.registrar_chamada(retorno, 0, nome_pedido=nome, usuario=usuario, contexto=contexto)
        return retorno
    return ferramenta.executar(argumentos, usuario, contexto)


def estado_integracoes():
    estados = []
    for nome in sorted(integracoes.INTEGRACOES):
        integracao = integracoes.INTEGRACOES[nome]
        estado = integracao.para_dicionario()
        estado.update(integracao.estado())
        estado["pausada"] = integracao.pausada()
        estado["ferramentas"] = sum(1 for ferramenta in CATALOGO.values() if nome in ferramenta.integracoes)
        estados.append(estado)
    return estados
