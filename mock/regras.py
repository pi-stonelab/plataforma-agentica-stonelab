"""Regras do mock em configuração (sem banco): cargos, carteiras, taxas e máscaras.

Fonte das regras: DOC-MOCK §3, §6, §7, §8.2 e §8.3. Nada aqui lê o banco; quem decide o acesso
(ferramentas/ e seguranca/) importa estas tabelas e consulta o cargo pela função
`regra_do_cargo`. Os prazos, as taxas e as alçadas de negócio também moram aqui: o gerador planta o
mundo com eles e as ferramentas calculam com os mesmos números.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# "Hoje" do mock é fixo para o mundo sair sempre igual (DOC-MOCK §11.1). Nunca use date.today().
HOJE_DO_MOCK = date(2026, 10, 15)
# O "agora" do mock: fim do expediente do dia de hoje, depois de toda venda sorteada (8h às 20h59).
# Serve a quem precisa de hora, como a venda de "10 minutos atrás" do cenário 11. Escolha do mock.
AGORA_DO_MOCK = datetime.combine(HOJE_DO_MOCK, time(21, 0))  # sem fuso: o mock é todo horário de Brasília

# Teto de linhas de qualquer lista que o mock devolve (consultas e ferramentas usam o mesmo).
LIMITE_MAXIMO = 50

AREAS = ("atendimento", "financeiro")
CARTEIRAS = ("varejo", "pme", "contas_chave")
# Filas de chamado: uma por carteira (DOC-MOCK §3.2) e a da ouvidoria (§6.1 e §6.4).
FILA_OUVIDORIA = "ouvidoria"
FILAS = (*CARTEIRAS, FILA_OUVIDORIA)
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
    "agenda_recebiveis",  # as parcelas e a simulação de antecipação (inclui o saldo)
    "saldo_agenda",  # só o saldo da agenda por situação, sem parcelas (cobrança, DOC-MOCK §8.2)
    "liquidacao",
    "cobranca",
    "chamado",
    "interacao",
    "endereco_publico",
    "pedido_plataforma",
    "disputa",  # chargebacks e casos de Pix (DOC-MOCK §7.6 e §7.7)
    "satisfacao",  # pesquisas CSAT (DOC-MOCK §6.7)
    "indicador_agregado",  # base analítica, sem dado de pessoa (DOC-MOCK §4)
    "metadado",  # dicionário de dados do mock (tabelas, colunas e sensibilidade)
    "base_conhecimento",  # artigos públicos de ajuda
    "cambio",  # cotação de moeda (API pública do Banco Central)
    "chamado_interno",  # chamados internos da Stone no Jira (pedido a outro time, falha de sistema)
    "comunicacao_interna",  # mensagem num canal interno da lista permitida (Slack ou Telegram)
    "agenda_pessoal",  # eventos da agenda do próprio funcionário (Google Calendar ou Outlook)
    "documento_de_trabalho",  # planilhas, documentos e anexos do próprio funcionário (Google, Microsoft e anexos do chat)
)

# Categorias que não são dado de lojista: CEP público, pedido de ferramenta ausente, artigo público de ajuda
# e cotação de moeda.
CATEGORIAS_COMUNS = frozenset({"endereco_publico", "pedido_plataforma", "base_conhecimento", "cambio"})
# Dado agregado ou sobre o próprio mock, sem lojista nem pessoa: vale para todo cargo que tem área
# (decisão do bloco A, SEM FONTE para a lista exata; ver docs/decisoes.md).
CATEGORIAS_DE_QUEM_TEM_AREA = frozenset({"indicador_agregado", "metadado"})
# Trabalho interno do funcionário com os colegas: chamados internos (Jira), avisos em canais internos (Slack e
# Telegram) e, no bloco E2, a agenda, as planilhas, os documentos e os anexos da PRÓPRIA conta dele (Google,
# Microsoft e anexos do chat). Vale para todo cargo que tem área; o destino é sempre um projeto, canal ou chat da
# lista do .env, e o que sai de dado de lojista passa pela máscara (decisões E1 e G1, SEM FONTE para a lista
# exata; ver docs/decisoes.md).
CATEGORIAS_DE_TRABALHO_INTERNO = frozenset(
    {"chamado_interno", "comunicacao_interna", "agenda_pessoal", "documento_de_trabalho"}
)

# Nomes grossos que as fichas das ferramentas ainda planejadas usam. Nenhum cargo os permite, então
# essas ferramentas ficam bloqueadas para todos até serem migradas para os nomes finos acima.
CATEGORIAS_DE_FERRAMENTAS_PLANEJADAS = (
    "atendimento",
    "financeiro",
    "comunicacao",
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
        "saldo_agenda",
        "liquidacao",
        "cobranca",
        "chamado",
        "interacao",
    }
)

JANELA_DIAS_ATENDENTE_N1 = 90  # KAN-69: vendas e agenda dos últimos 90 dias
_COMUNS_COM_AREA = CATEGORIAS_COMUNS | CATEGORIAS_DE_QUEM_TEM_AREA | CATEGORIAS_DE_TRABALHO_INTERNO


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
            JANELA_DIAS_ATENDENTE_N1, _DADOS_DO_ATENDIMENTO | _COMUNS_COM_AREA,
        ),
        # "Tudo do N1" (§8.2), mais disputas: contestação de venda é "N2 junto com Disputas" (§6.3).
        # Sem janela: a janela de 90 dias é só do N1 (O1).
        _regra(
            "especialista_n2", "atendimento", "Colaborador", "N2", ESCOPO_CARTEIRAS_DO_TIME,
            None, _DADOS_DO_ATENDIMENTO | {"disputa"} | _COMUNS_COM_AREA,
        ),
        # "Todas as filas da área" e "vê os indicadores do time" (§8.2): disputas como o N2 e a satisfação.
        _regra(
            "supervisor_atendimento", "atendimento", "Supervisor", "N2", ESCOPO_TODAS,
            None, _DADOS_DO_ATENDIMENTO | {"disputa", "satisfacao"} | _COMUNS_COM_AREA,
        ),
        # "Todos os lojistas com caso na ouvidoria e todo o histórico": cadastro, contato, histórico
        # de chamados e as pesquisas de satisfação. Sem ação financeira: sem venda, agenda e liquidação.
        _regra(
            "analista_ouvidoria", "atendimento", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "contato", "chamado", "interacao", "satisfacao"} | _COMUNS_COM_AREA,
        ),
        # "Só faturas, pagamentos, acordos e o saldo da agenda" (§8.2). Cadastro e contato só
        # para identificar o lojista e ligar (telefone chega mascarado na Sprint 2).
        _regra(
            "analista_cobranca", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "contato", "cobranca", "saldo_agenda"} | _COMUNS_COM_AREA,
        ),
        # "Vendas, chargebacks e casos de Pix" (§8.2).
        _regra(
            "analista_disputas", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "venda", "disputa"} | _COMUNS_COM_AREA,
        ),
        # "Agenda, liquidações e antecipações". Sem conta de recebimento (segregação §8.1).
        _regra(
            "analista_recebiveis", "financeiro", "Colaborador", "N1", ESCOPO_TODAS,
            None, {"cadastral", "agenda_recebiveis", "saldo_agenda", "liquidacao"} | _COMUNS_COM_AREA,
        ),
        # "Tudo do Financeiro": a união dos quatro analistas, menos o que é do atendimento.
        _regra(
            "coordenador_financeiro", "financeiro", "Supervisor", "N2", ESCOPO_TODAS, None,
            {"cadastral", "contato", "venda", "agenda_recebiveis", "saldo_agenda", "liquidacao", "cobranca", "disputa"}
            | _COMUNS_COM_AREA,
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
    "comentario": "texto_livre",  # pesquisas_satisfacao.comentario
}

# Campos de texto com formato fixo que parecem número restrito: o valor inteiro precisa casar o
# formato para passar sem a máscara de texto livre (protocolo do chamado: AAAAMMDD-NNNNNN).
FORMATO_DE_IDENTIFICADORES = {
    "protocolo": r"\d{8}-\d{6}",
    # Id de arquivo e link que o Google ou a Microsoft devolvem: texto técnico com dígitos no meio, que a máscara de
    # texto livre estragaria (o id não serve mais). Não é dado de pessoa, e só o valor INTEIRO nesse formato passa.
    "id_arquivo": r"[A-Za-z0-9!_-]{5,128}",
    # Ids dos anexos do chat (sorteados pela plataforma: prefixo e 12 letras, sem dígito).
    "anexo_id": r"ANX-[A-Z]{12}",
    "arquivo_id": r"ARQ-[A-Z]{12}",
    "link": r"https://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]{4,500}",
}

# Campos que as consultas devolvem e que não são restritos (público, interno ou confidencial).
# Inclui os montados pela fachada das ferramentas (valores em reais). Vale para TODAS as ferramentas.
# Campo que só uma ferramenta devolve (como assunto e corpo do enviar_email) não entra aqui: ele vai em
# `campos_liberados` da ficha dessa ferramenta (ferramentas/base.py), para as outras continuarem negando. É o caso do
# que a agenda, as planilhas, os documentos e os anexos da conta da pessoa devolvem (`titulo`, `inicio`, `fim`, `local`,
# `linhas`, `arquivo`...): vai nas fichas de `documentos_e_agenda` (F5).
CAMPOS_NAO_RESTRITOS = frozenset(
    {
        "codigo", "nome_fantasia", "segmento", "porte", "plano", "cidade", "uf", "carteira", "situacao",
        "data_entrada", "id_responsavel", "id", "papel", "banco", "data_hora", "modalidade",
        "parcelas", "bandeira", "valor_bruto_centavos", "valor_liquido_centavos", "data",
        "valor_total_centavos", "motivo_falha", "tipo", "mes_referencia", "vencimento",
        "valor_centavos", "dias_em_atraso", "protocolo", "categoria", "prioridade", "fila",
        "aberto_por", "aberto_em", "dias_em_aberto", "id_liquidacao", "id_fatura", "autor",
        "canal", "id_chamado", "total", "limite", "itens", "cargo", "area", "carteiras",
        "valor_bruto", "valor_liquido", "valor_total", "valor",
        # chamados (prazo do SLA, DOC-MOCK §6.4)
        "prazo_em", "resolvido_em", "prazo_estourado", "dias_uteis_restantes",
        # agenda de recebíveis e antecipação (§7.2 e §7.4)
        "id_venda", "numero_parcela", "data_prevista", "valor_parcela_centavos", "motivos_de_recusa",
        # disputas (§7.6 e §7.7)
        "motivo", "data_notificacao", "prazo_defesa", "valor_contestado_centavos",
        "documentos_enviados", "documentos_exigidos", "dias_para_o_prazo", "id_analista",
        "data_abertura", "valor_bloqueado_centavos", "prazo_contestacao", "tem_comprovante_entrega",
        "valor_retido_centavos", "valor_retido", "motivo_alegado",
        # acordos de cobrança (§7.9)
        "valor_original_centavos", "valor_renegociado_centavos", "entrada_centavos",
        "numero_de_parcelas", "perdao_encargos_centavos", "desconto_principal_centavos", "alcada",
        "id_solicitante", "id_aprovador", "criado_em", "faturas", "valor_original", "valor_renegociado", "entrada",
        "perdao_encargos", "desconto_principal",
        # satisfação (§6.7): a nota e as contagens; o comentário é restrito
        "nota", "respondida_em", "respostas", "media_centesimos", "media", "notas", "chamados_resolvidos",
        # base de conhecimento (texto público escrito pela equipe)
        "titulo_artigo", "texto_artigo", "atualizado_em",
        # base analítica (agregados, DOC-MOCK §4)
        "dia", "mes", "data_corte", "quantidade_aprovadas", "quantidade_negadas",
        "valor_bruto_dia_centavos", "valor_liquido_dia_centavos", "receita_mdr_dia_centavos",
        "quantidade_abertos", "quantidade_resolvidos", "quantidade_estourados",
        "quantidade_vendas_cartao", "quantidade_chargebacks", "taxa_chargeback_pontos_base",
        "receita_mdr", "quantidade", "taxa_chargeback", "maior_venda_dia_centavos",
        "receita_aluguel_e_tarifas_dia_centavos", "inadimplencia_dia_centavos", "concessao_em_acordos_dia_centavos",
        "perda_chargeback_dia_centavos", "receitas", "perdas", "resultado", "maior_venda", "aluguel_e_tarifas",
        "inadimplencia", "concessoes_em_acordos", "chargebacks_perdidos",
        # verificação de identidade (§6.6): só diz se confere, nunca o contato
        "confere",
        # dicionário de dados (metadado): descreve o esquema, nunca o dado
        "tabela", "sistema", "descricao_da_tabela", "origem", "colunas", "coluna", "tipo_da_coluna",
        "descricao_da_coluna", "restrita",
        # código do lojista: como o modelo o vê (id_cliente) e como o banco o chama (id_lojista)
        "id_cliente", "id_lojista",
        # integrações externas: a chave de um chamado interno do Jira, a origem da resposta (real ou modo de
        # demonstração) e o período de uma busca
        "chave_jira", "fonte",
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


# ---------------------------------------------------------------------------------------------
# Prazos de atendimento (DOC-MOCK §6.4). Dia útil é segunda a sexta; feriados ficam de fora
# (escolha do mock, a mesma do gerador). O relógio que para em "aguardando lojista" também fica de
# fora: o prazo é contado só a partir da abertura.
# ---------------------------------------------------------------------------------------------

PRAZO_EM_HORAS_POR_PRIORIDADE = {"crítica": 4}
PRAZO_EM_DIAS_UTEIS_POR_PRIORIDADE = {"alta": 1, "média": 3, "baixa": 5}
PRAZO_OUVIDORIA_DIAS_UTEIS = 10  # Resoluções CMN 4.860 e BCB 28, prorrogáveis por mais 15 dias
PRORROGACAO_OUVIDORIA_DIAS = 15


def eh_dia_util(dia: date) -> bool:
    return dia.weekday() < 5


def proximo_dia_util(dia: date) -> date:
    """Sábado e domingo passam para segunda."""
    while not eh_dia_util(dia):
        dia += timedelta(days=1)
    return dia


def somar_dias_uteis(momento: datetime, dias: int) -> datetime:
    """O mesmo horário, `dias` dias úteis depois (o dia de partida não conta)."""
    dia, contados = momento.date(), 0
    while contados < dias:
        dia += timedelta(days=1)
        contados += eh_dia_util(dia)
    return datetime.combine(dia, momento.time())


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias úteis depois de `inicio` até `fim`, inclusive. Zero se `fim` não passa de `inicio`."""
    return sum(eh_dia_util(inicio + timedelta(days=n)) for n in range(1, (fim - inicio).days + 1))


def prazo_do_chamado(aberto_em: datetime, prioridade: str, fila: str) -> datetime:
    """Prazo do SLA: a ouvidoria tem prazo regulatório; as outras filas seguem a prioridade."""
    if fila == FILA_OUVIDORIA:
        return somar_dias_uteis(aberto_em, PRAZO_OUVIDORIA_DIAS_UTEIS)
    if prioridade in PRAZO_EM_HORAS_POR_PRIORIDADE:
        return aberto_em + timedelta(hours=PRAZO_EM_HORAS_POR_PRIORIDADE[prioridade])
    return somar_dias_uteis(aberto_em, PRAZO_EM_DIAS_UTEIS_POR_PRIORIDADE[prioridade])


# ---------------------------------------------------------------------------------------------
# Encargos, antecipação e alçadas (DOC-MOCK §2.2, §7.4, §7.5 e §7.9). Valores ilustrativos da equipe.
# ---------------------------------------------------------------------------------------------

MULTA_ATRASO_PONTOS_BASE = 200  # 2%, multa única
JUROS_AO_MES_PONTOS_BASE = 100  # 1% ao mês, proporcional aos dias (mês de 30 dias)


def _arredondar_divisao(numerador: int, denominador: int) -> int:
    """Divisão inteira com arredondamento para o centavo mais próximo (metade para cima)."""
    return (2 * numerador + denominador) // (2 * denominador)


def encargos_de_atraso_centavos(valor_centavos: int, dias_de_atraso: int) -> tuple[int, int]:
    """(multa, juros) em centavos. Ex.: R$ 320,00 com 40 dias dá (640, 427), total R$ 330,67."""
    if dias_de_atraso <= 0:
        return 0, 0
    multa = _arredondar_divisao(valor_centavos * MULTA_ATRASO_PONTOS_BASE, 10000)
    juros = _arredondar_divisao(valor_centavos * JUROS_AO_MES_PONTOS_BASE * dias_de_atraso, 10000 * 30)
    return multa, juros


# Taxa mensal de antecipação em pontos-base (299 = 2,99% ao mês). O Negociado não tem tabela no
# DOC-MOCK ("sempre abaixo do Volume"): aqui o Volume menos 20 pontos-base, a mesma escolha do MDR.
TAXA_ANTECIPACAO_PONTOS_BASE = {"essencial": 299, "volume": 249, "negociado": 229}
DIAS_UTEIS_PARA_CAIR_A_ANTECIPACAO = 1
DIAS_DE_FATURA_VENCIDA_QUE_BLOQUEIAM_ANTECIPACAO = 15


def data_de_credito_da_antecipacao() -> date:
    """Quando cai o dinheiro de uma antecipação pedida hoje: 1 dia útil (§7.4)."""
    return somar_dias_uteis(datetime.combine(HOJE_DO_MOCK, time()), DIAS_UTEIS_PARA_CAIR_A_ANTECIPACAO).date()


def desconto_da_antecipacao_centavos(valor_centavos: int, dias_antecipados: int, taxa_pontos_base: int) -> int:
    """§7.4: valor da parcela × taxa mensal × dias antecipados ÷ 30, arredondado ao centavo. Ex.: R$ 1.000,00
    antecipados 30 dias a 2,99% ao mês dão R$ 29,90."""
    if dias_antecipados <= 0:
        return 0
    return _arredondar_divisao(valor_centavos * taxa_pontos_base * dias_antecipados, 10000 * 30)


# Os motivos de recusa da antecipação, na ordem em que a ferramenta explica, com o texto para a pessoa. Os quatro
# do §7.4 mais a conta inválida: o §7.3 diz que com ela o dinheiro fica retido, então nada sai (docs/decisoes.md, C7).
ROTULOS_DOS_MOTIVOS_DE_RECUSA_DA_ANTECIPACAO = {
    "recebivel_retido_ou_bloqueado": "a parcela está retida ou bloqueada",
    "lojista_bloqueado": "o lojista está bloqueado",
    "conta_em_verificacao": "a conta de recebimento está em verificação",
    "conta_invalida": "a conta de recebimento está inválida e o dinheiro fica retido",
    "fatura_vencida_ha_mais_de_15_dias": "há fatura vencida há mais de 15 dias",
}
MOTIVOS_DE_RECUSA_DA_ANTECIPACAO = tuple(ROTULOS_DOS_MOTIVOS_DE_RECUSA_DA_ANTECIPACAO)

# Alçadas do §7.9. `calcular_parcelas` usa estas, pela fachada (docs/decisoes.md, C15).
ENTRADA_MINIMA_ANALISTA_PERCENTUAL = 20
PARCELAS_MAXIMAS_ANALISTA = 6
PARCELAS_MAXIMAS_COORDENADOR = 12
DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL = 10
PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS = 200000  # R$ 2.000
LIMITE_DA_DUPLA_APROVACAO_CENTAVOS = 1000000  # acima de R$ 10.000, duas pessoas; quem pede não aprova
ALCADAS = ("analista", "coordenador", "dupla_aprovacao", "proibido")


def alcada_do_acordo(
    valor_original_centavos: int,
    valor_renegociado_centavos: int,
    numero_de_parcelas: int,
    entrada_centavos: int,
    perdao_encargos_centavos: int = 0,
    desconto_principal_centavos: int = 0,
) -> str:
    """Quem aprova o acordo (DOC-MOCK §7.9): "analista", "coordenador", "dupla_aprovacao" ou "proibido".

    - Desconto no principal (o valor original das faturas): só o coordenador, até 10%; acima disso, proibido.
    - Perdão de multa e juros: o analista perdoa em dívida de até R$ 2.000; acima disso, o coordenador.
    - Parcelas: o analista até 6, com entrada de pelo menos 20% do renegociado; o coordenador até 12.
    - Acima de R$ 10.000 renegociados, duas aprovações (e quem pede nunca aprova).
    """
    if (
        numero_de_parcelas > PARCELAS_MAXIMAS_COORDENADOR
        or desconto_principal_centavos * 100 > valor_original_centavos * DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL
    ):
        return "proibido"
    if valor_renegociado_centavos > LIMITE_DA_DUPLA_APROVACAO_CENTAVOS:
        return "dupla_aprovacao"
    perdao_acima_da_analista = (
        perdao_encargos_centavos > 0 and valor_original_centavos > PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS
    )
    if (
        desconto_principal_centavos > 0
        or perdao_acima_da_analista
        or numero_de_parcelas > PARCELAS_MAXIMAS_ANALISTA
        or entrada_centavos * 100 < valor_renegociado_centavos * ENTRADA_MINIMA_ANALISTA_PERCENTUAL
    ):
        return "coordenador"
    return "analista"


# ---------------------------------------------------------------------------------------------
# Disputas (DOC-MOCK §7.6 e §7.7)
# ---------------------------------------------------------------------------------------------

PRAZO_DE_DEFESA_DO_CHARGEBACK_DIAS = 7  # corridos, a partir do aviso ao lojista
PRAZO_DA_DECISAO_DO_CHARGEBACK_DIAS = 120
CHARGEBACK_QUE_LIGA_O_MONITORAMENTO_PONTOS_BASE = 100  # mais de 1% das vendas do mês, em quantidade
PRAZO_DO_MED_DIAS = 80  # para contestar a devolução de um Pix, desde 1º/09/2026
# O que quem pagou alegou no pedido de MED. O MED só vale para fraude ou golpe, nunca para arrependimento,
# erro de chave ou desacordo comercial (§7.7).
ROTULOS_DOS_MOTIVOS_DO_MED = {
    "golpe_produto_nao_entregue": "golpe: quem pagou diz que o produto não foi entregue",
    "fraude_conta_invadida": "fraude: quem pagou diz que a conta dele foi invadida",
}
MOTIVOS_DO_MED = tuple(ROTULOS_DOS_MOTIVOS_DO_MED)

ROTULOS_DOS_DOCUMENTOS = {
    "nota_fiscal": "nota fiscal",
    "comprovante_entrega": "comprovante de entrega (rastreio ou recibo assinado)",
    "comprovante_venda": "comprovante da venda (via do lojista)",
    "conversa_com_cliente": "conversa com o cliente",
    "descricao_do_produto": "descrição ou fotos do produto vendido",
    "comprovantes_das_duas_vendas": "comprovantes das duas vendas, mostrando que são compras diferentes",
    "politica_de_cancelamento": "política de cancelamento aceita pelo cliente",
    "comprovante_de_estorno": "comprovante de estorno ou de que o cancelamento não foi pedido",
}
# Motivo do chargeback -> documentos que a defesa exige ("cada motivo pede documentos diferentes").
DOCUMENTOS_POR_MOTIVO = {
    "compra_nao_reconhecida": ("comprovante_venda", "nota_fiscal"),
    "mercadoria_nao_recebida": ("nota_fiscal", "comprovante_entrega"),
    "produto_diferente": ("nota_fiscal", "descricao_do_produto", "conversa_com_cliente"),
    "cobranca_duplicada": ("comprovantes_das_duas_vendas",),
    "valor_divergente": ("nota_fiscal", "comprovante_venda"),
    "cancelamento_nao_processado": ("politica_de_cancelamento", "comprovante_de_estorno"),
}
MOTIVOS_DE_CHARGEBACK = tuple(DOCUMENTOS_POR_MOTIVO)
ROTULOS_DOS_MOTIVOS_DE_CHARGEBACK = {
    "compra_nao_reconhecida": "compra não reconhecida pelo dono do cartão",
    "mercadoria_nao_recebida": "mercadoria não recebida",
    "produto_diferente": "produto diferente do anunciado",
    "cobranca_duplicada": "cobrança duplicada",
    "valor_divergente": "valor cobrado diferente do combinado",
    "cancelamento_nao_processado": "cancelamento não processado",
}
# Só nestas situações o prazo ainda corre para o lojista (defesa do chargeback, contestação do MED).
SITUACOES_COM_PRAZO_DO_CHARGEBACK = ("aguardando_defesa",)
SITUACOES_COM_PRAZO_DO_CASO_PIX = ("bloqueado",)

# ---------------------------------------------------------------------------------------------
# Satisfação e base analítica (DOC-MOCK §4, §6.7 e §10.1)
# ---------------------------------------------------------------------------------------------

NOTA_QUE_ABRE_REVISAO_DO_SUPERVISOR = 2  # nota 1 ou 2
ATRASO_DA_BASE_ANALITICA_DIAS = 1  # cópia diária: os dados vão até ontem
ATRASO_EXTRA_DA_BASE_DESATUALIZADA_DIAS = 3  # falha "dado desatualizado" (mock/falhas.py)


def data_de_corte_da_base_analitica(desatualizada: bool = False) -> date:
    """Último dia que a base analítica tem. Desatualizada: mais 3 dias de atraso."""
    atraso = ATRASO_DA_BASE_ANALITICA_DIAS + (ATRASO_EXTRA_DA_BASE_DESATUALIZADA_DIAS if desatualizada else 0)
    return HOJE_DO_MOCK - timedelta(days=atraso)


def momento_de_corte_da_base_analitica() -> datetime:
    """Fim do último dia da base analítica (o começo de hoje)."""
    return datetime.combine(data_de_corte_da_base_analitica() + timedelta(days=1), time.min)


# ---------------------------------------------------------------------------------------------
# Escrita nos sistemas (DOC-MOCK §6.3, §6.5, §7.3, §7.4 e §7.9): quem pode mudar o quê
# ---------------------------------------------------------------------------------------------

# Quem cuida do chamado (§6.3). A ouvidoria é uma fila, não um nível: o caso dela continua com o N1 que o abriu
# até a ouvidoria assumir.
NIVEIS_DE_ATENDIMENTO = ("N1", "N2", "supervisor")
NIVEL_DE_ATENDIMENTO_POR_CATEGORIA = {
    "Dúvida de produto": "N1",
    "Recebimento": "N1",
    "Maquininha": "N1",
    "Fatura e aluguel": "N1",
    "Antecipação": "N1",
    "Alteração cadastral": "N2",
    "Contestação": "N2",
}
# Prioridade padrão de cada categoria (§6.3). Maquininha é crítica quando o lojista não consegue vender.
PRIORIDADE_POR_CATEGORIA = {
    "Dúvida de produto": "baixa",
    "Recebimento": "alta",
    "Maquininha": "média",
    "Fatura e aluguel": "média",
    "Antecipação": "média",
    "Alteração cadastral": "média",
    "Contestação": "alta",
}
CATEGORIA_QUE_FICA_CRITICA_SE_NAO_VENDE = "Maquininha"
VALOR_QUE_SOBE_O_CHAMADO_PARA_O_N2_CENTAVOS = 100000  # "o valor envolvido passa de R$ 1.000" (§6.5)
CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO = "Antecipação"

# Ciclo de vida do chamado (§6.5): de onde para onde a situação pode ir. "Fechado" não volta: um novo contato
# abre outro chamado. Fechar é do sistema, 7 dias depois de resolvido; quem atende só resolve.
TRANSICOES_DO_CHAMADO = {
    "novo": ("em_atendimento",),
    "em_atendimento": ("aguardando_lojista", "aguardando_area_interna", "resolvido"),
    "aguardando_lojista": ("em_atendimento", "resolvido"),
    "aguardando_area_interna": ("em_atendimento", "resolvido"),
    "resolvido": ("em_atendimento",),  # reaberto por uma mensagem do lojista em até 7 dias
    "fechado": (),
}
# O nível de quem atende, por cargo. Só esses cargos mudam a situação de um chamado.
NIVEL_DE_ATENDIMENTO_DO_CARGO = {
    "atendente_n1": "N1",
    "analista_ouvidoria": "N1",
    "especialista_n2": "N2",
    "supervisor_atendimento": "supervisor",
}
# Na fila da ouvidoria, só a ouvidoria muda a situação (cenário 9: o agente resume, mas não fecha o caso).
CARGOS_DA_OUVIDORIA = frozenset({"analista_ouvidoria"})
# Suspeita de fraude sobe o chamado para o N2 (§6.6: só o N2 troca a conta; cenário 6).
NIVEL_DA_SUSPEITA_DE_FRAUDE = "N2"
SITUACOES_DE_CHAMADO_SEM_ENCAMINHAMENTO = ("resolvido", "fechado")

# Liquidação (§7.3): só a que falhou é reprocessada, e só com a conta de recebimento ativa. A nova tentativa
# entra agendada para o próximo dia útil; o recebível do dia continua retido até ela ser paga.
SITUACOES_DE_LIQUIDACAO_QUE_REPROCESSAM = ("falhou",)
SITUACAO_DA_CONTA_QUE_RECEBE = "ativa"

# §7.9: até onde cada cargo aprova um acordo sozinho ("Alçada é o valor até onde um cargo pode aprovar algo
# sozinho"). A dupla aprovação nunca é de uma pessoa só: quem pediu não aprova, e a segunda aprovação é do
# coordenador (§8.2).
ALCADAS_DE_ACORDO_DO_CARGO = {
    "analista_cobranca": ("analista",),
    "coordenador_financeiro": ("analista", "coordenador"),
}
CARGOS_DA_SEGUNDA_APROVACAO = frozenset({"coordenador_financeiro"})
