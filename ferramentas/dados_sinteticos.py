"""Fachada do mock para as ferramentas: lê o banco por `mock/consultas.py` e devolve dicts.

Sem SQL aqui e nenhuma regra de permissão (isso é da governança). Banco ou sistema simulado fora do
ar vira ConnectionError, que `Ferramenta.executar` responde como `integracao_indisponivel`, sem
repassar o texto do erro. Valores em reais saem como texto ("R$ 1.842,30") para o modelo não
converter centavos.
"""

import sqlite3
from datetime import date

from mock import consultas, modelos, regras
from mock.banco import criar_engine, url_padrao
from mock.falhas import SistemaIndisponivel
from mock.gerar import garantir_mundo_local
from sqlalchemy.exc import ArgumentError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as TempoEsgotadoNoPool

ENDERECOS = {
    "01310100": ("Avenida Paulista", "Bela Vista", "São Paulo", "SP"),
    "20040020": ("Rua da Quitanda", "Centro", "Rio de Janeiro", "RJ"),
    "30130010": ("Avenida Afonso Pena", "Centro", "Belo Horizonte", "MG"),
}
CAMPOS_DO_CADASTRO = (
    "codigo",
    "nome_fantasia",
    "segmento",
    "porte",
    "plano",
    "cidade",
    "uf",
    "situacao",
    "data_entrada",
)
PAPEIS_CONTATO = modelos.PAPEIS_CONTATO  # as func.py não importam o mock direto
HOJE_DO_MOCK = regras.HOJE_DO_MOCK  # o "hoje" de toda regra de data (nunca date.today())
FALHAS_DE_INTEGRACAO = (SistemaIndisponivel, OperationalError, InterfaceError, TempoEsgotadoNoPool)
_CONEXAO = {"engine": None}


def configurar(origem):
    """Define o banco do mock: URL ou engine.

    Sem chamar, vale `mock.banco.url_padrao()`: a variável MOCK_DATABASE_URL, se declarada, ou o
    SQLite local em dados_locais/, que é gerado sozinho na primeira vez. `DATABASE_URL` (banco da plataforma) nunca é usada.
    """
    _CONEXAO["engine"] = criar_engine(origem) if isinstance(origem, str) else origem


def _engine():
    """Engine do mock, criado na primeira consulta. URL inválida não repete o texto dela."""
    if _CONEXAO["engine"] is None:
        try:
            url = url_padrao()
            garantir_mundo_local(url)  # SQLite local novo: gera o mock na primeira vez
            _CONEXAO["engine"] = criar_engine(url)
        except (ValueError, ArgumentError, OSError, OperationalError, sqlite3.Error):  # a mensagem pode ter a senha
            raise ConnectionError("integração indisponível") from None
    return _CONEXAO["engine"]


def _ler(consulta, *argumentos, **opcoes):
    """Roda uma consulta do mock; banco ou sistema fora do ar vira ConnectionError."""
    try:
        return consulta(_engine(), *argumentos, **opcoes)
    except FALHAS_DE_INTEGRACAO:
        raise ConnectionError("integração indisponível") from None


def reais(centavos):
    """Centavos inteiros em texto no padrão brasileiro: 184230 vira "R$ 1.842,30" e -1500 vira "-R$ 15,00"."""
    if centavos < 0:
        return "-" + reais(-centavos)
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def buscar_funcionario(id_funcionario):
    """Cargo, área, carteiras e situação de um funcionário do diretório do mock, ou None."""
    return _ler(consultas.buscar_funcionario, id_funcionario)


def contato_do_funcionario(id_funcionario):
    """{"nome", "email"} do funcionário, ou None. Só o envio do e-mail usa (o "responder para")."""
    return _ler(consultas.buscar_contato_funcionario, id_funcionario)


def carteira_do_lojista(codigo):
    """Só o necessário para decidir o escopo (`carteira`), ou None se o lojista não existe."""
    return _ler(consultas.carteira_do_lojista, codigo)


def buscar_cliente(codigo):
    """Cadastro do lojista sem contatos nem conta (campos de CAMPOS_DO_CADASTRO), ou None."""
    lojista = _ler(consultas.buscar_lojista, codigo)
    return {campo: lojista[campo] for campo in CAMPOS_DO_CADASTRO} if lojista else None


def buscar_transacoes(codigo, data_inicio, data_fim, limite):
    """Vendas do lojista no período: (lista, total no período), da mais recente para a mais antiga."""
    resposta = _ler(consultas.buscar_vendas, codigo, data_inicio, data_fim, limite)
    vendas = [
        {
            "codigo": venda["codigo"],
            "data_hora": venda["data_hora"],
            "modalidade": venda["modalidade"],
            "parcelas": venda["parcelas"],
            "valor_bruto": reais(venda["valor_bruto_centavos"]),
            "valor_liquido": reais(venda["valor_liquido_centavos"]),
            "situacao": venda["situacao"],
        }
        for venda in resposta["itens"]
    ]
    return vendas, resposta["total"]


def buscar_liquidacoes(codigo, data_inicio, data_fim, limite):
    """Liquidações do lojista no período: (lista, total no período), da mais recente à mais antiga."""
    resposta = _ler(consultas.buscar_liquidacoes, codigo, data_inicio, data_fim, limite)
    liquidacoes = [
        {
            "id_liquidacao": item["id"],
            "data": item["data"],
            "valor": reais(item["valor_total_centavos"]),
            "situacao": item["situacao"],
            "motivo_falha": item["motivo_falha"],
        }
        for item in resposta["itens"]
    ]
    return liquidacoes, resposta["total"]


def buscar_faturas_em_atraso(codigo):
    """Faturas vencidas do lojista: (lista, total, soma dos valores da lista em texto)."""
    resposta = _ler(consultas.buscar_faturas, codigo, True)
    faturas = [
        {
            "codigo": item["codigo"],
            "tipo": item["tipo"],
            "mes_referencia": item["mes_referencia"],
            "vencimento": item["vencimento"],
            "valor": reais(item["valor_centavos"]),
            "situacao": item["situacao"],
            "dias_em_atraso": item["dias_em_atraso"],
        }
        for item in resposta["itens"]
    ]
    soma = sum(item["valor_centavos"] for item in resposta["itens"])
    return faturas, resposta["total"], reais(soma)


def buscar_chamados(codigo, limite):
    """Chamados do lojista, sem o resumo (texto livre): (lista, total), do mais recente ao mais antigo."""
    resposta = _ler(consultas.buscar_chamados, codigo, limite)
    campos = (
        "codigo",
        "protocolo",
        "categoria",
        "prioridade",
        "situacao",
        "aberto_por",
        "aberto_em",
        "dias_em_aberto",
        "id_liquidacao",
        "id_fatura",
    )
    return [{campo: item[campo] for campo in campos} for item in resposta["itens"]], resposta[
        "total"
    ]


def chamado_e_do_lojista(codigo, id_chamado):
    """Diz se o chamado pertence ao lojista. Chamado de outro lojista e inexistente dão False."""
    return _ler(consultas.chamado_e_do_lojista, codigo, id_chamado)


def buscar_interacoes(codigo, id_chamado, limite):
    """Mensagens do chamado DO LOJISTA, em ordem cronológica: (lista, total). Texto livre de terceiros."""
    resposta = _ler(consultas.buscar_interacoes, codigo, id_chamado, limite)
    return resposta["itens"], resposta["total"]


def buscar_contatos(codigo):
    """Contatos do lojista, em claro (a máscara é de `Ferramenta.executar`): (lista, total)."""
    resposta = _ler(consultas.buscar_contatos, codigo)
    return resposta["itens"], resposta["total"]


def contato_para_email(codigo, papeis):
    """Primeiro contato do lojista com um dos `papeis`, na ordem dada: {"papel", "email"} ou None.

    O e-mail sai em claro só para `confirmacoes` guardar no pedido; o agente vê a prévia mascarada.
    """
    contatos, _ = buscar_contatos(codigo)
    for papel in papeis:
        for contato in contatos:
            if contato["papel"] == papel and contato.get("email"):
                return {"papel": papel, "email": contato["email"]}
    return None


def buscar_endereco(cep):
    """Endereço de um CEP público (3 CEPs de exemplo, sem rede e sem banco)."""
    if cep not in ENDERECOS:
        return None
    logradouro, bairro, cidade, uf = ENDERECOS[cep]
    return {"cep": cep, "logradouro": logradouro, "bairro": bairro, "cidade": cidade, "uf": uf}


# ---------------------------------------------------------------------------------------------
# Fase 2 do DOC-MOCK e base analítica. As func.py não importam o mock: as regras que elas precisam
# (prazos, taxas e alçadas) também saem por aqui.
# ---------------------------------------------------------------------------------------------

AGORA_DO_MOCK = regras.AGORA_DO_MOCK
MOTIVOS_DE_RECUSA_DA_ANTECIPACAO = regras.MOTIVOS_DE_RECUSA_DA_ANTECIPACAO
DIAS_UTEIS_PARA_CAIR_A_ANTECIPACAO = regras.DIAS_UTEIS_PARA_CAIR_A_ANTECIPACAO
alcada_do_acordo = regras.alcada_do_acordo
encargos_de_atraso_centavos = regras.encargos_de_atraso_centavos
somar_dias_uteis = regras.somar_dias_uteis
dias_uteis_entre = regras.dias_uteis_entre


def _documentos(slugs):
    return [regras.ROTULOS_DOS_DOCUMENTOS[slug] for slug in slugs]


def buscar_chamado(codigo, id_chamado):
    """Um chamado do lojista com o prazo do SLA (resumo em texto livre, para a máscara), ou None."""
    return _ler(consultas.buscar_chamado, codigo, id_chamado)


def buscar_agenda(codigo, data_inicio, data_fim, situacao, limite):
    """Parcelas da agenda no período: (lista, total), da data mais próxima para a mais distante."""
    resposta = _ler(consultas.buscar_recebiveis, codigo, data_inicio, data_fim, situacao, limite)
    parcelas = [
        {
            "codigo": item["codigo"],
            "id_venda": item["id_venda"],
            "numero_parcela": item["numero_parcela"],
            "data_prevista": item["data_prevista"],
            "valor": reais(item["valor_parcela_centavos"]),
            "situacao": item["situacao"],
        }
        for item in resposta["itens"]
    ]
    return parcelas, resposta["total"]


def resumo_da_agenda(codigo):
    """Agenda futura por situação: {situacao: {"quantidade", "valor"}} (valor em texto)."""
    resumo = _ler(consultas.resumo_da_agenda, codigo)
    return {
        situacao: {"quantidade": item["quantidade"], "valor": reais(item["valor_centavos"])}
        for situacao, item in resumo.items()
    }


def percentual(pontos_base):
    """Pontos-base em texto no padrão brasileiro: 299 vira "2,99%". None continua None."""
    if pontos_base is None:
        return None
    inteiro, resto = divmod(pontos_base, 100)
    return f"{inteiro},{resto:02d}%"


def recebiveis_para_antecipacao(codigo):
    """O que dá para antecipar, parcela por parcela: [{"data_prevista", "valor_centavos"}] (centavos: para calcular)."""
    return _ler(consultas.recebiveis_para_antecipacao, codigo)


def simulacao_de_antecipacao(codigo):
    """Antecipar hoje tudo o que dá (§7.4), ou None se o lojista não existe. Não olha os motivos de recusa:
    quem chama confere `motivos_de_recusa_da_antecipacao` antes.

    {"data_credito", "taxa_mensal", "quantidade_de_parcelas", "valor_antecipado", "desconto", "valor_liquido"}.
    """
    taxa = taxa_de_antecipacao(codigo)
    if taxa is None:
        return None
    credito = regras.data_de_credito_da_antecipacao()
    bruto = desconto = 0
    parcelas = recebiveis_para_antecipacao(codigo)
    for item in parcelas:
        dias = (date.fromisoformat(item["data_prevista"]) - credito).days
        bruto += item["valor_centavos"]
        desconto += regras.desconto_da_antecipacao_centavos(item["valor_centavos"], dias, taxa)
    return {
        "data_credito": credito.isoformat(),
        "taxa_mensal": percentual(taxa),
        "quantidade_de_parcelas": len(parcelas),
        "valor_antecipado": reais(bruto),
        "desconto": reais(desconto),
        "valor_liquido": reais(bruto - desconto),
    }


def motivos_de_recusa_da_antecipacao(codigo):
    """Motivos que recusam a antecipação do lojista, em texto para a pessoa (lista vazia: pode), ou None se ele
    não existe."""
    motivos = _ler(consultas.motivos_de_recusa_da_antecipacao, codigo)
    if motivos is None:
        return None
    return [regras.ROTULOS_DOS_MOTIVOS_DE_RECUSA_DA_ANTECIPACAO[motivo] for motivo in motivos]


def taxa_de_antecipacao(codigo):
    """Taxa mensal de antecipação do plano do lojista em pontos-base (299 = 2,99%), ou None."""
    lojista = _ler(consultas.buscar_lojista, codigo)
    if lojista is None:
        return None
    return regras.TAXA_ANTECIPACAO_PONTOS_BASE[regras.PLANO_POR_PORTE[lojista["porte"]]]


def buscar_acordos(codigo, situacao, limite):
    """Acordos de um lojista ou de todos (`codigo` None): (lista, total), do maior para o menor."""
    resposta = _ler(consultas.buscar_acordos, codigo, situacao, limite)
    acordos = [
        {
            "codigo": item["codigo"],
            "id_cliente": item["id_lojista"],
            "faturas": item["faturas"],
            "valor_original": reais(item["valor_original_centavos"]),
            "valor_renegociado": reais(item["valor_renegociado_centavos"]),
            "entrada": reais(item["entrada_centavos"]),
            "numero_de_parcelas": item["numero_de_parcelas"],
            "perdao_encargos": reais(item["perdao_encargos_centavos"]),
            "desconto_principal": reais(item["desconto_principal_centavos"]),
            "alcada": item["alcada"],
            "id_solicitante": item["id_solicitante"],
            "id_aprovador": item["id_aprovador"],
            "criado_em": item["criado_em"],
            "situacao": item["situacao"],
        }
        for item in resposta["itens"]
    ]
    return acordos, resposta["total"]


def buscar_chargebacks(codigo, limite):
    """Chargebacks do lojista com os documentos que o motivo exige: (lista, total).

    `valor` é o contestado (o bruto da venda); `valor_retido` é o que está preso na agenda por causa dele (o
    líquido, já sem a taxa). `dias_para_o_prazo` é None quando o prazo da defesa já não corre.
    """
    resposta = _ler(consultas.buscar_chargebacks, codigo, limite)
    chargebacks = [
        {
            "codigo": item["codigo"],
            "id_venda": item["id_venda"],
            "motivo": regras.ROTULOS_DOS_MOTIVOS_DE_CHARGEBACK[item["motivo"]],
            "data_notificacao": item["data_notificacao"],
            "prazo_defesa": item["prazo_defesa"],
            "dias_para_o_prazo": item["dias_para_o_prazo"],
            "valor": reais(item["valor_contestado_centavos"]),
            "valor_retido": reais(item["valor_retido_centavos"]),
            "documentos_exigidos": _documentos(regras.DOCUMENTOS_POR_MOTIVO[item["motivo"]]),
            "documentos_enviados": _documentos(item["documentos_enviados"]),
            "situacao": item["situacao"],
        }
        for item in resposta["itens"]
    ]
    return chargebacks, resposta["total"]


def buscar_casos_pix(codigo, limite):
    """Pedidos de devolução de Pix (MED) do lojista: (lista, total)."""
    resposta = _ler(consultas.buscar_casos_pix, codigo, limite)
    casos = [
        {
            "codigo": item["codigo"],
            "id_venda": item["id_venda"],
            "data_abertura": item["data_abertura"],
            "prazo_contestacao": item["prazo_contestacao"],
            "dias_para_o_prazo": item["dias_para_o_prazo"],
            "valor": reais(item["valor_bloqueado_centavos"]),
            "motivo_alegado": regras.ROTULOS_DOS_MOTIVOS_DO_MED[item["motivo_alegado"]],
            "tem_comprovante_entrega": item["tem_comprovante_entrega"],
            "situacao": item["situacao"],
        }
        for item in resposta["itens"]
    ]
    return casos, resposta["total"]


def _decimal(centesimos):
    """Centésimos em texto com vírgula: 352 vira "3,52". None continua None."""
    if centesimos is None:
        return None
    inteiro, resto = divmod(centesimos, 100)
    return f"{inteiro},{resto:02d}"


def resumo_satisfacao(data_inicio, data_fim, fila, carteira=None):
    """Notas CSAT do período: {"respostas", "notas", "media"} ("3,52", ou None sem respostas)."""
    resumo = _ler(consultas.resumo_satisfacao, data_inicio, data_fim, fila, carteira=carteira)
    return {"respostas": resumo["respostas"], "notas": resumo["notas"], "media": _decimal(resumo["media_centesimos"])}


def buscar_comentarios_satisfacao(data_inicio, data_fim, fila, nota_maxima, limite, carteira=None):
    """Respostas CSAT que TÊM comentário (texto livre de terceiros), da mais recente: (lista, total).

    `carteira` recorta o escopo de quem só vê o próprio time; None é todas.
    """
    resposta = _ler(
        consultas.buscar_pesquisas, data_inicio, data_fim, fila, nota_maxima, limite,
        carteira=carteira, somente_com_comentario=True,
    )
    return resposta["itens"], resposta["total"]


def buscar_artigos(termo, categoria, limite):
    """Artigos da base de conhecimento com as palavras do termo: (lista, total)."""
    resposta = _ler(consultas.buscar_artigos, termo, categoria, limite)
    return resposta["itens"], resposta["total"]


def normalizar_telefone(texto):
    """Só DDD + número (sem pontuação, 55 do país ou 0 de discagem), a forma em que o cadastro é comparado."""
    return consultas.normalizar_telefone(texto)


def contato_confere(codigo, telefone, email):
    """{"confere", "papel"}: todo contato informado é do MESMO contato cadastrado do lojista? None se o lojista não existe."""
    return _ler(consultas.contato_confere, codigo, telefone, email)


def resumo_de_vendas(data_inicio, data_fim):
    """Vendas do período por modalidade, da base analítica (até ontem), com valores em texto."""
    resposta = _ler(consultas.totais_de_vendas, data_inicio, data_fim)
    modalidades = [
        {
            "modalidade": item["modalidade"],
            "quantidade_aprovadas": item["quantidade_aprovadas"],
            "quantidade_negadas": item["quantidade_negadas"],
            "valor_bruto": reais(item["valor_bruto_dia_centavos"]),
            "valor_liquido": reais(item["valor_liquido_dia_centavos"]),
            "receita_mdr": reais(item["receita_mdr_dia_centavos"]),
        }
        for item in resposta["itens"]
    ]
    soma = {
        chave: sum(item[chave] for item in resposta["itens"])
        for chave in ("quantidade_aprovadas", "valor_bruto_dia_centavos", "receita_mdr_dia_centavos")
    }
    total = {
        "quantidade_aprovadas": soma["quantidade_aprovadas"],
        "valor_bruto": reais(soma["valor_bruto_dia_centavos"]),
        "receita_mdr": reais(soma["receita_mdr_dia_centavos"]),
    }
    return {"data_corte": resposta["data_corte"], "modalidades": modalidades, "total": total}


def resumo_de_resultado(data_inicio, data_fim):
    """Receitas, perdas e resultado da Stone no período, da base analítica (até ontem), com valores em texto.

    {"data_corte", "receitas": {"mdr", "aluguel_e_tarifas", "total"}, "perdas": {"inadimplencia",
    "concessoes_em_acordos", "chargebacks_perdidos", "total"}, "resultado", "maior_venda": {"dia", "valor"}}.
    """
    resposta = _ler(consultas.resultado_por_periodo, data_inicio, data_fim)
    receitas = (resposta["receita_mdr_dia_centavos"], resposta["receita_aluguel_e_tarifas_dia_centavos"])
    perdas = (
        resposta["inadimplencia_dia_centavos"], resposta["concessao_em_acordos_dia_centavos"],
        resposta["perda_chargeback_dia_centavos"],
    )
    maior = resposta["maior_venda"]
    return {
        "data_corte": resposta["data_corte"],
        "receitas": {"mdr": reais(receitas[0]), "aluguel_e_tarifas": reais(receitas[1]), "total": reais(sum(receitas))},
        "perdas": {
            "inadimplencia": reais(perdas[0]), "concessoes_em_acordos": reais(perdas[1]),
            "chargebacks_perdidos": reais(perdas[2]), "total": reais(sum(perdas)),
        },
        "resultado": reais(sum(receitas) - sum(perdas)),
        "maior_venda": {"dia": maior["dia"], "valor": reais(maior["maior_venda_dia_centavos"])} if maior else None,
    }


def vendas_por_dia(data_inicio, data_fim, limite):
    """Vendas por dia da base analítica: (lista, total de dias, data de corte)."""
    resposta = _ler(consultas.vendas_por_dia, data_inicio, data_fim, limite)
    dias = [
        {
            "dia": item["dia"],
            "quantidade_aprovadas": item["quantidade_aprovadas"],
            "valor_bruto": reais(item["valor_bruto_dia_centavos"]),
            "receita_mdr": reais(item["receita_mdr_dia_centavos"]),
        }
        for item in resposta["itens"]
    ]
    return dias, resposta["total"], resposta["data_corte"]


def chamados_por_fila(data_inicio, data_fim, prioridade):
    """Chamados por fila da base analítica: {"data_corte", "itens"}."""
    return _ler(consultas.chamados_por_fila, data_inicio, data_fim, prioridade)


def _contestacoes(mes_inicio, mes_fim, codigo):
    resposta = _ler(consultas.contestacoes_por_mes, mes_inicio, mes_fim, codigo)
    itens = [
        {
            "mes": item["mes"],
            "quantidade_vendas_cartao": item["quantidade_vendas_cartao"],
            "quantidade_chargebacks": item["quantidade_chargebacks"],
            "taxa_chargeback": percentual(item["taxa_chargeback_pontos_base"]),
        }
        for item in resposta["itens"]
    ]
    return {"data_corte": resposta["data_corte"], "itens": itens}


def contestacoes_por_mes(mes_inicio, mes_fim):
    """Chargebacks e taxa ("0,45%") por mês, somando TODOS os lojistas (indicador agregado): {"data_corte", "itens"}."""
    return _contestacoes(mes_inicio, mes_fim, None)


def contestacoes_do_lojista_por_mes(codigo, mes_inicio, mes_fim):
    """O mesmo de um lojista só. É dado de disputa daquele lojista: a ficha que usa pede a categoria `disputa`
    e passa pelas portas do lojista (carteira e janela), não `indicador_agregado`."""
    return _contestacoes(mes_inicio, mes_fim, codigo)


def dicionario_de_dados():
    """Tabelas e colunas do mock com o sistema dono e a sensibilidade (não lê dado nenhum)."""
    return consultas.dicionario_de_dados()


# ---------------------------------------------------------------------------------------------
# Leituras do bloco C. Listas fechadas que as func.py validam e leituras que só elas usam.
# ---------------------------------------------------------------------------------------------

FILAS = regras.FILAS
PRIORIDADES = modelos.PRIORIDADES
SITUACOES_RECEBIVEL = modelos.SITUACOES_RECEBIVEL
SITUACOES_ACORDO = modelos.SITUACOES_ACORDO
DESCRICAO_DOS_SISTEMAS = consultas.DESCRICAO_DOS_SISTEMAS
LIMITE_DE_CHARGEBACK_DO_MONITORAMENTO = regras.CHARGEBACK_QUE_LIGA_O_MONITORAMENTO_PONTOS_BASE  # pontos-base
PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS = regras.PERDAO_DE_ENCARGOS_DO_ANALISTA_ATE_CENTAVOS
PARCELAS_MAXIMAS_ANALISTA = regras.PARCELAS_MAXIMAS_ANALISTA
PARCELAS_MAXIMAS_COORDENADOR = regras.PARCELAS_MAXIMAS_COORDENADOR
ENTRADA_MINIMA_ANALISTA_PERCENTUAL = regras.ENTRADA_MINIMA_ANALISTA_PERCENTUAL
DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL = regras.DESCONTO_MAXIMO_COORDENADOR_PERCENTUAL
LIMITE_DA_DUPLA_APROVACAO_CENTAVOS = regras.LIMITE_DA_DUPLA_APROVACAO_CENTAVOS


def buscar_lojistas_por_nome(termo, carteiras, limite):
    """Lojistas com o termo no nome fantasia, só nas `carteiras` (None = todas): (lista, total)."""
    resposta = _ler(consultas.buscar_lojistas_por_nome, termo, carteiras, limite)
    return resposta["itens"], resposta["total"]


def agenda_e_liquidacoes_por_dia(codigo, data_inicio, data_fim):
    """Por dia até ontem: agenda do dia e quanto a liquidação pagou, em centavos (para a conferência calcular)."""
    return _ler(consultas.agenda_e_liquidacoes_por_dia, codigo, data_inicio, data_fim)


def ultimas_interacoes(codigo, id_chamado, limite):
    """As mensagens mais recentes do chamado, em ordem cronológica: (lista, total do chamado)."""
    resposta = _ler(consultas.ultimas_interacoes, codigo, id_chamado, limite)
    return resposta["itens"], resposta["total"]
