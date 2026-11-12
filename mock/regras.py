"""Regras do mock em configuração (sem banco): cargos, carteiras, taxas e máscaras.

Fonte das regras: DOC-MOCK §3, §8.2 e §8.3. Nada aqui lê o banco; quem decide o acesso
(ferramentas/ e seguranca/) importa estas tabelas e consulta o cargo pela função
`regra_do_cargo`.
"""

from dataclasses import dataclass
from datetime import date

# "Hoje" do mock é fixo para o mundo sair sempre igual (DOC-MOCK §11.1). Nunca use date.today().
HOJE_DO_MOCK = date(2026, 10, 15)

AREAS = ("atendimento", "financeiro")
CARTEIRAS = ("varejo", "pme", "contas_chave")
PORTES = ("MEI", "ME", "EPP", "media")

# Carteira por porte (DOC-MOCK §3.2): Varejo = MEI e ME, PME = EPP, Contas-chave = média empresa.
CARTEIRA_POR_PORTE = {"MEI": "varejo", "ME": "varejo", "EPP": "pme", "media": "contas_chave"}

# Perfis de acesso a agentes. "Auditor" ainda não existe em seguranca/ (nasce na etapa de segurança).
PERFIS = ("Colaborador", "Supervisor", "AdminGlobal", "Auditor")
NIVEIS_FERRAMENTA = ("N1", "N2")

ESCOPO_CARTEIRAS_DO_TIME = "carteiras_do_time"
ESCOPO_TODAS = "todas"
ESCOPO_NENHUM = "nenhum"
ESCOPOS = (ESCOPO_CARTEIRAS_DO_TIME, ESCOPO_TODAS, ESCOPO_NENHUM)

CATEGORIAS_DADO = (
    "cadastral",
    "contato",
    "conta_recebimento",
    "venda",
    "agenda_recebiveis",
    "liquidacao",
    "cobranca",
    "chamado",
    "interacao",
    "endereco_publico",
    "pedido_plataforma",
)

# Categorias que não são dado de lojista: CEP público e pedido de ferramenta ausente.
CATEGORIAS_COMUNS = frozenset({"endereco_publico", "pedido_plataforma"})

# Nomes grossos que as fichas das ferramentas ainda planejadas usam. Nenhum cargo os permite, então
# essas ferramentas ficam bloqueadas para todos até serem migradas para os nomes finos acima.
CATEGORIAS_DE_FERRAMENTAS_PLANEJADAS = (
    "atendimento",
    "financeiro",
    "agenda",
    "comunicacao",
    "documento",
    "cambio",
    "metadado",
    "indicador_agregado",
    "chamado_interno",
)

# DOC-MOCK §8.2: o atendimento vê o lojista inteiro (cadastro, contato, conta, vendas, agenda,
# liquidação, faturas, chamados). Liquidação entra por decisão O4 (cenário 1 exige).
_DADOS_DO_ATENDIMENTO = frozenset(
    {
        "cadastral",
        "contato",
        "conta_recebimento",
        "venda",
        "agenda_recebiveis",
        "liquidacao",
        "cobranca",
        "chamado",
        "interacao",
    }
)

JANELA_DIAS_ATENDENTE_N1 = 90  # KAN-69: vendas e agenda dos últimos 90 dias


@dataclass(frozen=True)
class RegraCargo:
    """O que um cargo pode ver. `area` e `nivel_ferramenta` são None nos cargos transversais."""

    cargo: str
    area: str | None
    perfil_padrao: str
    nivel_ferramenta: str | None
    escopo_lojistas: str
    janela_dias: int | None
    categorias_dado: frozenset[str]


def _regra(cargo, area, perfil, nivel, escopo, janela, categorias) -> RegraCargo:
    return RegraCargo(cargo, area, perfil, nivel, escopo, janela, frozenset(categorias))


# Os 10 cargos do mock (DOC-MOCK §3.1), com os identificadores exatos. Ordem de decisão do
# DOC-MOCK §8.1: cargo, escopo, alçada, máscara. Aqui ficam cargo, escopo, janela e categorias.
CARGOS: dict[str, RegraCargo] = {
    r.cargo: r
    for r in (
        _regra(
            "atendente_n1", "atendimento", "Colaborador", "N1", ESCOPO_CARTEIRAS_DO_TIME,
            JANELA_DIAS_ATENDENTE_N1, _DADOS_DO_ATENDIMENTO | CATEGORIAS_COMUNS,
        ),
        # "Tudo do N1" (§8.2). Sem janela: a janela de 90 dias é só do N1 (O1).
        _regra(
            "especialista_n2", "atendimento", "Colaborador", "N2", ESCOPO_CARTEIRAS_DO_TIME,
            None, _DADOS_DO_ATENDIMENTO | CATEGORIAS_COMUNS,
        ),
        # "Todas as filas da área" (§8.2).
        _regra(
            "supervisor_atendimento", "atendimento", "Supervisor", "N2", ESCOPO_TODAS,
            None, _DADOS_DO_ATENDIMENTO | CATEGORIAS_COMUNS,
        ),
        # "Todos os lojistas com caso na ouvidoria e todo o histórico": cadastro, contato e
        # histórico de chamados. Sem ação financeira, então sem venda, agenda e liquidação.
        _regra(
            "analista_ouvidoria", "atendimento", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "contato", "chamado", "interacao"} | CATEGORIAS_COMUNS,
        ),
        # "Só faturas, pagamentos, acordos e o saldo da agenda" (§8.2). Cadastro e contato só
        # para identificar o lojista e ligar (telefone chega mascarado na Sprint 2).
        _regra(
            "analista_cobranca", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "contato", "cobranca", "agenda_recebiveis"} | CATEGORIAS_COMUNS,
        ),
        # "Vendas, chargebacks e casos de Pix". Chargeback e Pix não existem na fase 1.
        _regra(
            "analista_disputas", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "venda"} | CATEGORIAS_COMUNS,
        ),
        # "Agenda, liquidações e antecipações". Sem conta de recebimento (segregação §8.1).
        _regra(
            "analista_recebiveis", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "agenda_recebiveis", "liquidacao"} | CATEGORIAS_COMUNS,
        ),
        # "Tudo do Financeiro": a união dos quatro analistas, menos o que é do atendimento.
        _regra(
            "coordenador_financeiro", "financeiro", "Supervisor", "N2", ESCOPO_TODAS, None,
            {"cadastral", "contato", "venda", "agenda_recebiveis", "liquidacao", "cobranca"}
            | CATEGORIAS_COMUNS,
        ),
        # Na Sprint 2 não há ferramenta de dado para os dois cargos transversais.
        _regra("auditor_compliance", None, "Auditor", None, ESCOPO_NENHUM, None, ()),
        _regra("admin_plataforma", None, "AdminGlobal", None, ESCOPO_NENHUM, None, ()),
    )
}


def regra_do_cargo(cargo: str | None) -> RegraCargo | None:
    """Devolve a regra do cargo ou None se o cargo é desconhecido (quem chama nega)."""
    if not isinstance(cargo, str):
        return None
    return CARGOS.get(cargo)


def area_do_cargo(cargo: str | None) -> str | None:
    """Área do cargo (atendimento, financeiro) ou None para transversal ou desconhecido."""
    regra = regra_do_cargo(cargo)
    return regra.area if regra else None


# Máscara de cada campo restrito (DOC-MOCK §8.3). Uma fonte só: o mascaramento lê daqui
# (DOC-MOCK §11.6). CONTRATO: a chave é o nome do campo no dict PLANO que as consultas
# (`consultas.py`) devolvem, não "tabela.coluna". O nome do campo é único entre as tabelas, e um
# teste confere isso. Campo restrito novo = uma linha aqui; campo que não está aqui nem em
# CAMPOS_NAO_RESTRITOS sai mascarado (negar por padrão).
CLASSIFICACAO_CAMPOS = {
    "nome": "nome",  # contatos_lojista.nome (restrito, DOC-MOCK §5)
    "cpf": "cpf",
    "telefone": "telefone",
    "email": "email",
    "agencia": "conta",
    "conta": "conta",
    "ultimos4": "cartao",
    "texto": "texto_livre",  # interacoes.texto
    "resumo": "texto_livre",  # chamados.resumo
}

# Campos que as consultas devolvem e que não são restritos (público, interno ou confidencial).
# Inclui os montados pela fachada das ferramentas (valores em reais).
CAMPOS_NAO_RESTRITOS = frozenset(
    {
        "codigo", "nome_fantasia", "segmento", "porte", "cidade", "uf", "carteira", "situacao",
        "data_entrada", "id_responsavel", "id", "papel", "banco", "data_hora", "modalidade",
        "parcelas", "bandeira", "valor_bruto_centavos", "valor_liquido_centavos", "data",
        "valor_total_centavos", "motivo_falha", "tipo", "mes_referencia", "vencimento",
        "valor_centavos", "dias_em_atraso", "protocolo", "categoria", "prioridade", "fila",
        "aberto_por", "aberto_em", "dias_em_aberto", "id_liquidacao", "id_fatura", "autor",
        "canal", "id_chamado", "total", "limite", "itens", "cargo", "area", "carteiras",
        "valor_bruto", "valor_liquido", "valor_total", "valor",
    }
)

# MDR em pontos-base (199 = 1,99%) por plano (DOC-MOCK §2.2). Inteiros evitam erro de arredondamento.
# MEI, ME e EPP usam o Essencial. A média empresa usa o Negociado: "sempre abaixo do Volume",
# aqui o Volume menos 20 pontos-base (escolha do mock).
MDR_PONTOS_BASE = {
    "essencial": {"debito": 199, "credito_a_vista": 349, "ate_6x": 429, "ate_12x": 499, "pix": 0},
    "volume": {"debito": 149, "credito_a_vista": 299, "ate_6x": 379, "ate_12x": 449, "pix": 0},
    "negociado": {"debito": 129, "credito_a_vista": 279, "ate_6x": 359, "ate_12x": 429, "pix": 0},
}
PLANO_POR_PORTE = {"MEI": "essencial", "ME": "essencial", "EPP": "essencial", "media": "negociado"}
ALUGUEL_CENTAVOS = {"essencial": 3990, "volume": 2990, "negociado": 2990}


def mdr_pontos_base(plano: str, modalidade: str, parcelas: int) -> int:
    """MDR da venda em pontos-base, conforme plano, modalidade e número de parcelas."""
    tabela = MDR_PONTOS_BASE[plano]
    if modalidade == "parcelado":
        return tabela["ate_6x"] if parcelas <= 6 else tabela["ate_12x"]
    return tabela[modalidade]
