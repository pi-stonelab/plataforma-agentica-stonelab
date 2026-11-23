"""O "conector" do mock: leituras nomeadas e parametrizadas, só com as colunas necessárias.

Cada função recebe uma `Session` (ou um engine) e devolve dicionários simples. Valores em
centavos; datas em texto ISO (a conversão para reais e para o formato de exibição é de quem
mostra). Listas devolvem no máximo 50 linhas, mais o total encontrado. Aqui não há regra de
permissão: quem decide se o cargo pode chamar é a governança das ferramentas.
"""

import re
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from . import falhas, regras
from .banco import trava_de_acesso
from .modelos import (
    ORIGEM_DAS_TABELAS_ANALITICAS,
    SISTEMA_DONO_DA_TABELA,
    SITUACOES_RECEBIVEL,
    Acordo,
    AnaliticaAtualizacao,
    AnaliticaChamadosDiarios,
    AnaliticaContestacoesMensais,
    AnaliticaResultadoDiario,
    AnaliticaVendasDiarias,
    ArtigoAjuda,
    BaseMock,
    CasoPix,
    Chamado,
    Chargeback,
    ContaRecebimento,
    ContatoLojista,
    Fatura,
    Funcionario,
    Interacao,
    Liquidacao,
    Lojista,
    PesquisaSatisfacao,
    Recebivel,
    Time,
    Venda,
)
from .regras import area_do_cargo

LIMITE_MAXIMO = regras.LIMITE_MAXIMO


@contextmanager
def _sessao_de(origem: Session | Engine) -> Iterator[Session]:
    """Usa a sessão recebida ou abre (e fecha) uma a partir do engine."""
    if isinstance(origem, Session):
        yield origem
    else:
        with trava_de_acesso(origem), Session(origem) as sessao:
            yield sessao


def _limite_efetivo(limite: int | None) -> int:
    if limite is None:
        return LIMITE_MAXIMO
    return max(1, min(int(limite), LIMITE_MAXIMO))


def _lista(sessao: Session, consulta, limite: int | None, formatar) -> dict:
    """Aplica o teto de linhas e devolve {"itens", "total", "limite"}."""
    teto = _limite_efetivo(limite)
    total = sessao.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    linhas = sessao.execute(consulta.limit(teto)).all()
    return {"itens": [formatar(linha) for linha in linhas], "total": total, "limite": teto}


def _iso(valor) -> str | None:
    return valor.isoformat() if valor is not None else None


def buscar_lojista(origem: Session | Engine, codigo: str) -> dict | None:
    """Cadastro do lojista (sem contatos nem conta). None se o código não existe."""
    falhas.verificar("cadastro")
    with _sessao_de(origem) as sessao:
        lojista = sessao.get(Lojista, codigo)
        if lojista is None:
            return None
        return {
            "codigo": lojista.codigo,
            "nome_fantasia": lojista.nome_fantasia,
            "segmento": lojista.segmento,
            "porte": lojista.porte,
            "plano": regras.PLANO_POR_PORTE[lojista.porte],
            "cidade": lojista.cidade,
            "uf": lojista.uf,
            "carteira": lojista.carteira,
            "situacao": lojista.situacao,
            "data_entrada": _iso(lojista.data_entrada),
            "id_responsavel": lojista.id_responsavel,
        }


def carteira_do_lojista(origem: Session | Engine, codigo: str) -> dict | None:
    """Só o necessário para decidir o escopo: carteira e especialista responsável."""
    falhas.verificar("cadastro")
    with _sessao_de(origem) as sessao:
        linha = sessao.execute(
            select(Lojista.codigo, Lojista.carteira, Lojista.id_responsavel).where(
                Lojista.codigo == codigo
            )
        ).first()
        if linha is None:
            return None
        return {"codigo": linha.codigo, "carteira": linha.carteira,
                "id_responsavel": linha.id_responsavel}


def buscar_vendas(
    origem: Session | Engine,
    codigo: str,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int | None = None,
) -> dict:
    """Vendas do lojista no período (datas inclusivas), da mais recente para a mais antiga."""
    falhas.verificar("core")
    consulta = select(
        Venda.codigo, Venda.data_hora, Venda.modalidade, Venda.parcelas, Venda.bandeira,
        Venda.ultimos4, Venda.valor_bruto_centavos, Venda.valor_liquido_centavos, Venda.situacao,
    ).where(Venda.id_lojista == codigo)
    if data_inicio is not None:
        consulta = consulta.where(Venda.data_hora >= datetime.combine(data_inicio, time.min))
    if data_fim is not None:
        depois_do_fim = datetime.combine(data_fim + timedelta(days=1), time.min)
        consulta = consulta.where(Venda.data_hora < depois_do_fim)
    consulta = consulta.order_by(Venda.data_hora.desc(), Venda.codigo)

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        item["data_hora"] = _iso(item["data_hora"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def buscar_liquidacoes(
    origem: Session | Engine,
    codigo: str,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int | None = None,
) -> dict:
    """Liquidações do lojista no período (datas inclusivas), da mais recente para a mais antiga."""
    falhas.verificar("core")
    consulta = select(
        Liquidacao.id, Liquidacao.data, Liquidacao.valor_total_centavos, Liquidacao.situacao,
        Liquidacao.motivo_falha,
    ).where(Liquidacao.id_lojista == codigo)
    if data_inicio is not None:
        consulta = consulta.where(Liquidacao.data >= data_inicio)
    if data_fim is not None:
        consulta = consulta.where(Liquidacao.data <= data_fim)
    consulta = consulta.order_by(Liquidacao.data.desc(), Liquidacao.id.desc())

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        item["data"] = _iso(item["data"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def buscar_faturas(origem: Session | Engine, codigo: str, somente_vencidas: bool = False) -> dict:
    """Faturas do lojista, da mais recente para a mais antiga.

    `dias_em_atraso` já vem calculado a partir de HOJE_DO_MOCK (só para fatura vencida).
    """
    falhas.verificar("cobranca")
    consulta = select(
        Fatura.codigo, Fatura.tipo, Fatura.mes_referencia, Fatura.vencimento,
        Fatura.valor_centavos, Fatura.situacao,
    ).where(Fatura.id_lojista == codigo)
    if somente_vencidas:
        consulta = consulta.where(Fatura.situacao == "vencida")
    consulta = consulta.order_by(Fatura.vencimento.desc(), Fatura.codigo)

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        atraso = (regras.HOJE_DO_MOCK - item["vencimento"]).days
        item["dias_em_atraso"] = atraso if item["situacao"] == "vencida" and atraso > 0 else None
        item["vencimento"] = _iso(item["vencimento"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, None, formatar)


def buscar_chamados(origem: Session | Engine, codigo: str, limite: int | None = None) -> dict:
    """Chamados do lojista, do mais recente para o mais antigo.

    `dias_em_aberto` já vem calculado a partir de HOJE_DO_MOCK (só para chamado não fechado).
    """
    falhas.verificar("crm")
    consulta = (
        select(
            Chamado.codigo, Chamado.protocolo, Chamado.categoria, Chamado.prioridade,
            Chamado.fila, Chamado.id_responsavel, Chamado.situacao, Chamado.aberto_por,
            Chamado.aberto_em, Chamado.resumo, Chamado.id_liquidacao, Chamado.id_fatura,
        )
        .where(Chamado.id_lojista == codigo)
        .order_by(Chamado.aberto_em.desc(), Chamado.codigo)
    )

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        aberto = (regras.HOJE_DO_MOCK - item["aberto_em"].date()).days
        item["dias_em_aberto"] = aberto if item["situacao"] != "fechado" else None
        item["aberto_em"] = _iso(item["aberto_em"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def chamado_e_do_lojista(origem: Session | Engine, codigo_lojista: str, codigo_chamado: str) -> bool:
    """True se o chamado existe e pertence ao lojista (uma consulta por código, sem teto de 50)."""
    falhas.verificar("crm")
    consulta = select(Chamado.codigo).where(
        Chamado.codigo == codigo_chamado, Chamado.id_lojista == codigo_lojista
    )
    with _sessao_de(origem) as sessao:
        return sessao.scalar(consulta) is not None


def buscar_interacoes(
    origem: Session | Engine, codigo_lojista: str, codigo_chamado: str, limite: int | None = None
) -> dict:
    """Interações de um chamado DO LOJISTA, em ordem cronológica.

    O join com o chamado garante que o chamado pertence ao lojista informado: a governança
    decide o escopo do lojista (O13) e nunca recebe interação de chamado de outro lojista.
    Texto livre: conteúdo de terceiros.
    """
    falhas.verificar("crm")
    consulta = (
        select(
            Interacao.id, Interacao.autor, Interacao.canal, Interacao.data_hora, Interacao.texto
        )
        .join(Chamado, Interacao.id_chamado == Chamado.codigo)
        .where(Chamado.codigo == codigo_chamado, Chamado.id_lojista == codigo_lojista)
        .order_by(Interacao.data_hora, Interacao.id)
    )

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        item["data_hora"] = _iso(item["data_hora"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def buscar_contatos(origem: Session | Engine, codigo: str) -> dict:
    """Contatos do lojista (dados restritos, em claro: a máscara é de quem exibe)."""
    falhas.verificar("cadastro")
    consulta = (
        select(
            ContatoLojista.id, ContatoLojista.nome, ContatoLojista.cpf, ContatoLojista.papel,
            ContatoLojista.telefone, ContatoLojista.email,
        )
        .where(ContatoLojista.id_lojista == codigo)
        .order_by(ContatoLojista.id)
    )
    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, None, lambda linha: dict(linha._mapping))


def buscar_conta_recebimento(origem: Session | Engine, codigo: str) -> dict | None:
    """Conta de recebimento do lojista (dados restritos, em claro). None se não houver."""
    falhas.verificar("cadastro")
    with _sessao_de(origem) as sessao:
        linha = sessao.execute(
            select(ContaRecebimento.banco, ContaRecebimento.agencia, ContaRecebimento.conta,
                   ContaRecebimento.situacao).where(ContaRecebimento.id_lojista == codigo)
        ).first()
        return dict(linha._mapping) if linha else None


def buscar_contato_funcionario(origem: Session | Engine, id_funcionario: str) -> dict | None:
    """Nome e e-mail do funcionário, para o "responder para" do e-mail que ele confirmou. None se não existir.

    Separada de `buscar_funcionario` de propósito: só o envio do e-mail lê isto (mínimo de dados, LGPD)."""
    falhas.verificar("diretorio")
    with _sessao_de(origem) as sessao:
        linha = sessao.execute(
            select(Funcionario.nome, Funcionario.email).where(Funcionario.id == id_funcionario)
        ).first()
        return dict(linha._mapping) if linha else None


def buscar_funcionario(origem: Session | Engine, id_funcionario: str) -> dict | None:
    """Cargo, área (derivada do cargo), carteiras do time e situação. Sem nome nem e-mail."""
    falhas.verificar("diretorio")
    with _sessao_de(origem) as sessao:
        linha = sessao.execute(
            select(Funcionario.id, Funcionario.cargo, Funcionario.situacao, Time.carteira)
            .outerjoin(Time, Funcionario.id_time == Time.id)
            .where(Funcionario.id == id_funcionario)
        ).first()
        if linha is None:
            return None
        return {
            "id": linha.id,
            "cargo": linha.cargo,
            "area": area_do_cargo(linha.cargo),
            "carteiras": [linha.carteira] if linha.carteira else [],
            "situacao": linha.situacao,
        }


# ---------------------------------------------------------------------------------------------
# Chamado em detalhe (prazo do SLA, DOC-MOCK §6.4)
# ---------------------------------------------------------------------------------------------


def _situacao_do_prazo(prazo_em: datetime, resolvido_em: datetime | None) -> dict:
    """Prazo estourado (até a resolução ou até agora) e dias úteis que faltam se ainda está aberto."""
    fim = resolvido_em or regras.AGORA_DO_MOCK
    restantes = None
    if resolvido_em is None:
        restantes = regras.dias_uteis_entre(regras.HOJE_DO_MOCK, prazo_em.date())
    return {"prazo_estourado": fim > prazo_em, "dias_uteis_restantes": restantes}


def buscar_chamado(origem: Session | Engine, codigo_lojista: str, codigo_chamado: str) -> dict | None:
    """Um chamado DO LOJISTA, com o prazo do SLA. None se não existe ou é de outro lojista."""
    falhas.verificar("crm")
    with _sessao_de(origem) as sessao:
        chamado = sessao.scalar(select(Chamado).where(
            Chamado.codigo == codigo_chamado, Chamado.id_lojista == codigo_lojista))
        if chamado is None:
            return None
        return {
            "codigo": chamado.codigo,
            "protocolo": chamado.protocolo,
            "categoria": chamado.categoria,
            "prioridade": chamado.prioridade,
            "fila": chamado.fila,
            "id_responsavel": chamado.id_responsavel,
            "situacao": chamado.situacao,
            "aberto_por": chamado.aberto_por,
            "aberto_em": _iso(chamado.aberto_em),
            "prazo_em": _iso(chamado.prazo_em),
            "resolvido_em": _iso(chamado.resolvido_em),
            "resumo": chamado.resumo,
            "id_liquidacao": chamado.id_liquidacao,
            "id_fatura": chamado.id_fatura,
            **_situacao_do_prazo(chamado.prazo_em, chamado.resolvido_em),
        }


# ---------------------------------------------------------------------------------------------
# Agenda de recebíveis e antecipação (core, DOC-MOCK §7.2 e §7.4)
# ---------------------------------------------------------------------------------------------

def buscar_recebiveis(
    origem: Session | Engine,
    codigo: str,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    situacao: str | None = None,
    limite: int | None = None,
) -> dict:
    """Agenda do lojista no período (datas previstas inclusivas), da mais próxima para a mais distante."""
    falhas.verificar("core")
    consulta = select(
        Recebivel.codigo, Recebivel.id_venda, Recebivel.numero_parcela, Recebivel.data_prevista,
        Recebivel.valor_parcela_centavos, Recebivel.situacao,
    ).where(Recebivel.id_lojista == codigo)
    if data_inicio is not None:
        consulta = consulta.where(Recebivel.data_prevista >= data_inicio)
    if data_fim is not None:
        consulta = consulta.where(Recebivel.data_prevista <= data_fim)
    if situacao is not None:
        consulta = consulta.where(Recebivel.situacao == situacao)
    consulta = consulta.order_by(Recebivel.data_prevista, Recebivel.codigo)

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        item["data_prevista"] = _iso(item["data_prevista"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def resumo_da_agenda(origem: Session | Engine, codigo: str) -> dict:
    """Quantidade e soma (centavos) da agenda futura do lojista, por situação. Situação sem parcela: zero."""
    falhas.verificar("core")
    consulta = (
        select(Recebivel.situacao, func.count(), func.coalesce(func.sum(Recebivel.valor_parcela_centavos), 0))
        .where(Recebivel.id_lojista == codigo, Recebivel.data_prevista >= regras.HOJE_DO_MOCK)
        .group_by(Recebivel.situacao)
    )
    resumo = {situacao: {"quantidade": 0, "valor_centavos": 0} for situacao in SITUACOES_RECEBIVEL
              if situacao != "pago"}
    with _sessao_de(origem) as sessao:
        for situacao, quantidade, soma in sessao.execute(consulta):
            resumo[situacao] = {"quantidade": quantidade, "valor_centavos": int(soma)}
    return resumo


def recebiveis_para_antecipacao(origem: Session | Engine, codigo: str) -> list[dict]:
    """O que dá para antecipar hoje, parcela por parcela: [{"data_prevista", "valor_centavos"}].

    Só parcela "previsto" (retida e bloqueada ficam de fora, §7.4) e que cai DEPOIS do dia em que o dinheiro
    da antecipação cairia (`regras.data_de_credito_da_antecipacao`): a de amanhã já chega amanhã. Sem teto de
    linhas: o desconto é calculado recebível por recebível (§7.4), e nada disso vai ao modelo.
    """
    falhas.verificar("core")
    consulta = (
        select(Recebivel.data_prevista, Recebivel.valor_parcela_centavos)
        .where(
            Recebivel.id_lojista == codigo, Recebivel.situacao == "previsto",
            Recebivel.data_prevista > regras.data_de_credito_da_antecipacao(),
        )
        .order_by(Recebivel.data_prevista, Recebivel.codigo)
    )
    with _sessao_de(origem) as sessao:
        return [{"data_prevista": _iso(dia), "valor_centavos": valor} for dia, valor in sessao.execute(consulta)]


def motivos_de_recusa_da_antecipacao(origem: Session | Engine, codigo: str) -> list[str] | None:
    """Motivos do lojista que recusam qualquer antecipação (DOC-MOCK §7.4), na ordem de
    `regras.MOTIVOS_DE_RECUSA_DA_ANTECIPACAO`. Lista vazia: pode antecipar. None: lojista não existe.

    O quarto motivo do §7.4 (parcela retida ou bloqueada) vale parcela por parcela: essas parcelas ficam
    fora de `recebiveis_para_antecipacao` em vez de recusar tudo.
    """
    falhas.verificar("cadastro")
    falhas.verificar("cobranca")
    limite_do_vencimento = regras.HOJE_DO_MOCK - timedelta(days=regras.DIAS_DE_FATURA_VENCIDA_QUE_BLOQUEIAM_ANTECIPACAO)
    with _sessao_de(origem) as sessao:
        lojista = sessao.get(Lojista, codigo)
        if lojista is None:
            return None
        conta = sessao.scalar(select(ContaRecebimento.situacao).where(ContaRecebimento.id_lojista == codigo))
        vencida_ha_muito = sessao.scalar(select(func.count()).select_from(Fatura).where(
            Fatura.id_lojista == codigo, Fatura.situacao == "vencida", Fatura.vencimento < limite_do_vencimento))
    motivos = []
    if lojista.situacao == "bloqueado":
        motivos.append("lojista_bloqueado")
    if conta == "em_verificacao":
        motivos.append("conta_em_verificacao")
    if vencida_ha_muito:
        motivos.append("fatura_vencida_ha_mais_de_15_dias")
    return motivos


# ---------------------------------------------------------------------------------------------
# Cobrança: acordos (DOC-MOCK §7.9)
# ---------------------------------------------------------------------------------------------


def buscar_acordos(
    origem: Session | Engine,
    codigo: str | None = None,
    situacao: str | None = None,
    limite: int | None = None,
) -> dict:
    """Acordos de um lojista ou de todos (`codigo` None), do maior valor renegociado para o menor.

    Sem lojista, a lista cruza carteiras: quem chama decide se o cargo pode ver todos (escopo "todas").
    """
    falhas.verificar("cobranca")
    consulta = select(
        Acordo.codigo, Acordo.id_lojista, Acordo.valor_original_centavos, Acordo.valor_renegociado_centavos,
        Acordo.entrada_centavos, Acordo.numero_de_parcelas, Acordo.perdao_encargos_centavos,
        Acordo.desconto_principal_centavos, Acordo.alcada,
        Acordo.id_solicitante, Acordo.id_aprovador, Acordo.criado_em, Acordo.situacao,
    )
    if codigo is not None:
        consulta = consulta.where(Acordo.id_lojista == codigo)
    if situacao is not None:
        consulta = consulta.where(Acordo.situacao == situacao)
    consulta = consulta.order_by(Acordo.valor_renegociado_centavos.desc(), Acordo.codigo)
    with _sessao_de(origem) as sessao:
        faturas_em_acordo = select(Fatura.codigo, Fatura.id_acordo).where(Fatura.id_acordo.is_not(None))
        if codigo is not None:
            faturas_em_acordo = faturas_em_acordo.where(Fatura.id_lojista == codigo)
        faturas: dict[str, list[str]] = {}
        for codigo_fatura, id_acordo in sessao.execute(faturas_em_acordo.order_by(Fatura.codigo)):
            faturas.setdefault(id_acordo, []).append(codigo_fatura)

        def formatar(linha) -> dict:
            item = dict(linha._mapping)
            item["criado_em"] = _iso(item["criado_em"])
            item["faturas"] = faturas.get(item["codigo"], [])
            return item

        return _lista(sessao, consulta, limite, formatar)


# ---------------------------------------------------------------------------------------------
# Disputas: chargebacks e Pix (DOC-MOCK §7.6 e §7.7)
# ---------------------------------------------------------------------------------------------


def buscar_chargebacks(origem: Session | Engine, codigo: str, limite: int | None = None) -> dict:
    """Chargebacks do lojista, do aviso mais recente para o mais antigo.

    `documentos_enviados` vira lista; `dias_para_o_prazo` conta a partir de hoje e só existe enquanto o prazo
    da defesa corre (`regras.SITUACOES_COM_PRAZO_DO_CHARGEBACK`); `valor_retido_centavos` é o que está retido
    na agenda por causa da venda contestada (o líquido, já sem a taxa, §7.6).
    """
    falhas.verificar("disputas")
    consulta = (
        select(
            Chargeback.codigo, Chargeback.id_venda, Chargeback.motivo, Chargeback.data_notificacao,
            Chargeback.prazo_defesa, Chargeback.valor_contestado_centavos, Chargeback.documentos_enviados,
            Chargeback.id_analista, Chargeback.situacao,
        )
        .where(Chargeback.id_lojista == codigo)
        .order_by(Chargeback.data_notificacao.desc(), Chargeback.codigo)
    )

    retido_por_venda = (
        select(Recebivel.id_venda, func.sum(Recebivel.valor_parcela_centavos))
        .where(Recebivel.id_lojista == codigo, Recebivel.situacao == "retido",
               Recebivel.data_prevista >= regras.HOJE_DO_MOCK)
        .group_by(Recebivel.id_venda)
    )

    with _sessao_de(origem) as sessao:
        retido = {venda: int(soma) for venda, soma in sessao.execute(retido_por_venda)}

        def formatar(linha) -> dict:
            item = dict(linha._mapping)
            prazo_corre = item["situacao"] in regras.SITUACOES_COM_PRAZO_DO_CHARGEBACK
            item["documentos_enviados"] = [d for d in item["documentos_enviados"].split(",") if d]
            item["dias_para_o_prazo"] = (item["prazo_defesa"] - regras.HOJE_DO_MOCK).days if prazo_corre else None
            item["valor_retido_centavos"] = retido.get(item["id_venda"], 0)
            item["data_notificacao"] = _iso(item["data_notificacao"])
            item["prazo_defesa"] = _iso(item["prazo_defesa"])
            return item

        return _lista(sessao, consulta, limite, formatar)


def buscar_casos_pix(origem: Session | Engine, codigo: str, limite: int | None = None) -> dict:
    """Pedidos de devolução de Pix (MED) do lojista, do mais recente para o mais antigo."""
    falhas.verificar("disputas")
    consulta = (
        select(
            CasoPix.codigo, CasoPix.id_venda, CasoPix.data_abertura, CasoPix.prazo_contestacao,
            CasoPix.valor_bloqueado_centavos, CasoPix.motivo_alegado, CasoPix.tem_comprovante_entrega,
            CasoPix.id_analista, CasoPix.situacao,
        )
        .where(CasoPix.id_lojista == codigo)
        .order_by(CasoPix.data_abertura.desc(), CasoPix.codigo)
    )

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        prazo_corre = item["situacao"] in regras.SITUACOES_COM_PRAZO_DO_CASO_PIX
        item["dias_para_o_prazo"] = (item["prazo_contestacao"] - regras.HOJE_DO_MOCK).days if prazo_corre else None
        item["data_abertura"] = _iso(item["data_abertura"])
        item["prazo_contestacao"] = _iso(item["prazo_contestacao"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


# ---------------------------------------------------------------------------------------------
# CRM: satisfação, base de conhecimento e verificação de identidade (DOC-MOCK §6.6 e §6.7)
# ---------------------------------------------------------------------------------------------


def _periodo_das_pesquisas(
    consulta, data_inicio: date | None, data_fim: date | None, fila: str | None,
    codigo: str | None = None, carteira: str | None = None,
):
    """Filtros comuns das pesquisas. Lojista e carteira recortam o escopo de quem só vê o próprio time."""
    if codigo is not None:
        consulta = consulta.where(Chamado.id_lojista == codigo)
    if carteira is not None:
        consulta = consulta.join(Lojista, Chamado.id_lojista == Lojista.codigo).where(Lojista.carteira == carteira)
    if data_inicio is not None:
        consulta = consulta.where(PesquisaSatisfacao.respondida_em >= datetime.combine(data_inicio, time.min))
    if data_fim is not None:
        consulta = consulta.where(
            PesquisaSatisfacao.respondida_em < datetime.combine(data_fim + timedelta(days=1), time.min))
    if fila is not None:
        consulta = consulta.where(Chamado.fila == fila)
    return consulta


def buscar_pesquisas(
    origem: Session | Engine,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    fila: str | None = None,
    nota_maxima: int | None = None,
    limite: int | None = None,
    *,
    codigo: str | None = None,
    carteira: str | None = None,
    somente_com_comentario: bool = False,
) -> dict:
    """Respostas CSAT no período, da mais recente para a mais antiga (de todos os lojistas, de um só ou de uma
    carteira).

    O comentário é texto livre do lojista (RESTRITO, conteúdo de terceiros): sai em claro para a máscara.
    """
    falhas.verificar("crm")
    consulta = select(
        PesquisaSatisfacao.id_chamado, Chamado.fila, PesquisaSatisfacao.nota, PesquisaSatisfacao.comentario,
        PesquisaSatisfacao.respondida_em,
    ).join(Chamado, PesquisaSatisfacao.id_chamado == Chamado.codigo)
    consulta = _periodo_das_pesquisas(consulta, data_inicio, data_fim, fila, codigo, carteira)
    if nota_maxima is not None:
        consulta = consulta.where(PesquisaSatisfacao.nota <= nota_maxima)
    if somente_com_comentario:
        consulta = consulta.where(PesquisaSatisfacao.comentario.is_not(None), PesquisaSatisfacao.comentario != "")
    consulta = consulta.order_by(PesquisaSatisfacao.respondida_em.desc(), PesquisaSatisfacao.id)

    def formatar(linha) -> dict:
        item = dict(linha._mapping)
        item["respondida_em"] = _iso(item["respondida_em"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def resumo_satisfacao(
    origem: Session | Engine,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    fila: str | None = None,
    *,
    codigo: str | None = None,
    carteira: str | None = None,
) -> dict:
    """Notas CSAT no período: respostas, quantas de cada nota e a média em centésimos (4,25 vira 425)."""
    falhas.verificar("crm")
    consulta = (
        select(PesquisaSatisfacao.nota, func.count())
        .join(Chamado, PesquisaSatisfacao.id_chamado == Chamado.codigo)
        .group_by(PesquisaSatisfacao.nota)
    )
    consulta = _periodo_das_pesquisas(consulta, data_inicio, data_fim, fila, codigo, carteira)
    notas = {nota: 0 for nota in range(1, 6)}
    with _sessao_de(origem) as sessao:
        for nota, quantidade in sessao.execute(consulta):
            notas[nota] = quantidade
    respostas = sum(notas.values())
    soma = sum(nota * quantidade for nota, quantidade in notas.items())
    media = (200 * soma + respostas) // (2 * respostas) if respostas else None
    return {"respostas": respostas, "notas": notas, "media_centesimos": media}


# Palavras que não ajudam a achar o artigo ("minha maquininha não liga" procura só "maquininha" e "liga").
PALAVRAS_SEM_PESO = frozenset({
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "em", "no", "na", "nos",
    "nas", "ao", "aos", "e", "ou", "que", "para", "pra", "por", "com", "sem", "se", "eu", "meu", "minha",
    "meus", "minhas", "seu", "sua", "seus", "suas", "nao", "sim", "como", "qual", "quais", "esta", "esse",
    "essa", "isso", "ja", "foi", "ser", "tem", "ter", "estou",
})


def _sem_acento_minusculo(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _raiz(palavra: str) -> str:
    """Plural simples volta ao singular: "maquininhas" acha "maquininha"."""
    return palavra[:-1] if len(palavra) > 3 and palavra.endswith("s") else palavra


def palavras_de_busca(texto: str | None) -> frozenset[str]:
    """Palavras inteiras (sem acento, sem caixa, sem plural simples) que contam na busca."""
    palavras = re.findall(r"[a-z0-9]+", _sem_acento_minusculo(texto or ""))
    return frozenset(_raiz(p) for p in palavras if p not in PALAVRAS_SEM_PESO)


def buscar_artigos(
    origem: Session | Engine,
    termo: str | None = None,
    categoria: str | None = None,
    limite: int | None = None,
) -> dict:
    """Artigos da base de conhecimento que têm alguma palavra do termo, do mais parecido para o menos.

    A pergunta chega como o lojista escreve ("minha maquininha não liga"): conta cada palavra que bate
    inteira com o texto ou os sinônimos do artigo, e em dobro com o título ou a categoria ("med" não acha
    "médio"). Sem termo, todos; termo sem nenhuma palavra que conte ("%"), nenhum. A base é pequena (dezenas
    de artigos), então a conta é feita aqui, depois de ler.
    """
    falhas.verificar("crm")
    consulta = select(
        ArtigoAjuda.codigo, ArtigoAjuda.titulo_artigo, ArtigoAjuda.categoria, ArtigoAjuda.texto_artigo,
        ArtigoAjuda.atualizado_em, ArtigoAjuda.termos_de_busca,
    ).order_by(ArtigoAjuda.codigo)
    if categoria is not None:
        consulta = consulta.where(ArtigoAjuda.categoria == categoria)
    procuradas = palavras_de_busca(termo)
    sem_termo = not (termo or "").strip()
    with _sessao_de(origem) as sessao:
        linhas = sessao.execute(consulta).all()
    pontuados = []
    for linha in linhas:
        no_titulo = procuradas & palavras_de_busca(f"{linha.titulo_artigo} {linha.categoria}")
        pontos = len(procuradas & palavras_de_busca(linha.termos_de_busca)) + len(no_titulo)
        if pontos or sem_termo:
            pontuados.append((-pontos, linha.codigo, linha))
    pontuados.sort(key=lambda item: item[:2])
    teto = _limite_efetivo(limite)
    itens = [
        {
            "codigo": linha.codigo, "titulo_artigo": linha.titulo_artigo, "categoria": linha.categoria,
            "texto_artigo": linha.texto_artigo, "atualizado_em": _iso(linha.atualizado_em),
        }
        for _, _, linha in pontuados[:teto]
    ]
    return {"itens": itens, "total": len(pontuados), "limite": teto}


def _so_digitos(texto: str | None) -> str:
    return "".join(caractere for caractere in texto or "" if caractere.isdigit())


def contato_confere(
    origem: Session | Engine, codigo: str, telefone: str | None = None, email: str | None = None
) -> dict | None:
    """Diz se o telefone ou o e-mail informado é de um contato cadastrado do lojista (DOC-MOCK §6.6).

    Nunca devolve o contato: só {"confere", "papel"}. Telefone compara só os dígitos; e-mail, sem caixa.
    None se o lojista não existe.
    """
    falhas.verificar("cadastro")
    digitos, endereco = _so_digitos(telefone), (email or "").strip().lower()
    with _sessao_de(origem) as sessao:
        if sessao.get(Lojista, codigo) is None:
            return None
        contatos = sessao.execute(select(ContatoLojista.papel, ContatoLojista.telefone, ContatoLojista.email)
                                  .where(ContatoLojista.id_lojista == codigo).order_by(ContatoLojista.id))
        for papel, telefone_cadastrado, email_cadastrado in contatos:
            if (digitos and digitos == _so_digitos(telefone_cadastrado)) or (
                endereco and endereco == email_cadastrado.lower()
            ):
                return {"confere": True, "papel": papel}
    return {"confere": False, "papel": None}


# ---------------------------------------------------------------------------------------------
# Base analítica (DOC-MOCK §4): agregados até o dia de corte
# ---------------------------------------------------------------------------------------------


def _corte(sessao: Session) -> date:
    """Último dia que a base analítica tem. Com a falha "desatualizado", alguns dias a menos."""
    corte = sessao.scalar(select(AnaliticaAtualizacao.data_corte).where(AnaliticaAtualizacao.id == 1))
    if falhas.desatualizado("analitica"):
        corte -= timedelta(days=regras.ATRASO_EXTRA_DA_BASE_DESATUALIZADA_DIAS)
    return corte


def _periodo_ate_o_corte(coluna, corte: date, inicio: date | None, fim: date | None) -> list:
    condicoes = [coluna <= (min(fim, corte) if fim is not None else corte)]
    if inicio is not None:
        condicoes.append(coluna >= inicio)
    return condicoes


def totais_de_vendas(
    origem: Session | Engine, data_inicio: date | None = None, data_fim: date | None = None
) -> dict:
    """Vendas do período por modalidade (até o corte): quantidades e somas em centavos."""
    falhas.verificar("analitica")
    tabela = AnaliticaVendasDiarias
    with _sessao_de(origem) as sessao:
        corte = _corte(sessao)
        consulta = (
            select(
                tabela.modalidade, func.sum(tabela.quantidade_aprovadas), func.sum(tabela.quantidade_negadas),
                func.sum(tabela.valor_bruto_dia_centavos), func.sum(tabela.valor_liquido_dia_centavos),
                func.sum(tabela.receita_mdr_dia_centavos),
            )
            .where(*_periodo_ate_o_corte(tabela.dia, corte, data_inicio, data_fim))
            .group_by(tabela.modalidade)
            .order_by(tabela.modalidade)
        )
        itens = [
            {
                "modalidade": modalidade, "quantidade_aprovadas": int(aprovadas),
                "quantidade_negadas": int(negadas), "valor_bruto_dia_centavos": int(bruto),
                "valor_liquido_dia_centavos": int(liquido), "receita_mdr_dia_centavos": int(receita),
            }
            for modalidade, aprovadas, negadas, bruto, liquido, receita in sessao.execute(consulta)
        ]
    return {"data_corte": _iso(corte), "itens": itens}


def vendas_por_dia(
    origem: Session | Engine,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int | None = None,
) -> dict:
    """Vendas do período somadas por dia (até o corte), do dia mais recente para o mais antigo."""
    falhas.verificar("analitica")
    tabela = AnaliticaVendasDiarias
    with _sessao_de(origem) as sessao:
        corte = _corte(sessao)
        consulta = (
            select(
                tabela.dia, func.sum(tabela.quantidade_aprovadas).label("quantidade_aprovadas"),
                func.sum(tabela.valor_bruto_dia_centavos).label("valor_bruto_dia_centavos"),
                func.sum(tabela.receita_mdr_dia_centavos).label("receita_mdr_dia_centavos"),
            )
            .where(*_periodo_ate_o_corte(tabela.dia, corte, data_inicio, data_fim))
            .group_by(tabela.dia)
            .order_by(tabela.dia.desc())
        )

        def formatar(linha) -> dict:
            item = {chave: int(valor) for chave, valor in linha._mapping.items() if chave != "dia"}
            return {"dia": _iso(linha.dia), **item}  # int(): a soma vem como Decimal no Postgres

        resposta = _lista(sessao, consulta, limite, formatar)
    return {**resposta, "data_corte": _iso(corte)}


def chamados_por_fila(
    origem: Session | Engine,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    prioridade: str | None = None,
) -> dict:
    """Chamados abertos no período, por fila (até o corte): abertos, resolvidos e fora do prazo do SLA."""
    falhas.verificar("analitica")
    tabela = AnaliticaChamadosDiarios
    with _sessao_de(origem) as sessao:
        corte = _corte(sessao)
        consulta = select(
            tabela.fila, func.sum(tabela.quantidade_abertos), func.sum(tabela.quantidade_resolvidos),
            func.sum(tabela.quantidade_estourados),
        ).where(*_periodo_ate_o_corte(tabela.dia, corte, data_inicio, data_fim))
        if prioridade is not None:
            consulta = consulta.where(tabela.prioridade == prioridade)
        consulta = consulta.group_by(tabela.fila).order_by(tabela.fila)
        itens = [
            {"fila": fila, "quantidade_abertos": int(abertos), "quantidade_resolvidos": int(resolvidos),
             "quantidade_estourados": int(estourados)}
            for fila, abertos, resolvidos, estourados in sessao.execute(consulta)
        ]
    return {"data_corte": _iso(corte), "itens": itens}


def resultado_por_periodo(
    origem: Session | Engine, data_inicio: date | None = None, data_fim: date | None = None
) -> dict:
    """Receitas e perdas da Stone no período, até o corte, em centavos (KAN-14 caso 4).

    Receitas: MDR das vendas aprovadas e aluguel e tarifas pelo vencimento. Perdas: inadimplência (o que venceu
    no período e segue vencido), concessões em acordos e chargebacks perdidos. Mais a maior venda do período
    (dia e valor), que explica um pico de receita.
    """
    falhas.verificar("analitica")
    vendas, resultado = AnaliticaVendasDiarias, AnaliticaResultadoDiario
    with _sessao_de(origem) as sessao:
        corte = _corte(sessao)
        receita_mdr = sessao.scalar(select(func.coalesce(func.sum(vendas.receita_mdr_dia_centavos), 0)).where(
            *_periodo_ate_o_corte(vendas.dia, corte, data_inicio, data_fim)))
        somas = sessao.execute(
            select(*(func.coalesce(func.sum(coluna), 0) for coluna in (
                resultado.receita_aluguel_e_tarifas_dia_centavos, resultado.inadimplencia_dia_centavos,
                resultado.concessao_em_acordos_dia_centavos, resultado.perda_chargeback_dia_centavos,
            ))).where(*_periodo_ate_o_corte(resultado.dia, corte, data_inicio, data_fim))
        ).one()
        maior = sessao.execute(
            select(vendas.dia, vendas.maior_venda_dia_centavos)
            .where(*_periodo_ate_o_corte(vendas.dia, corte, data_inicio, data_fim))
            .order_by(vendas.maior_venda_dia_centavos.desc(), vendas.dia)
            .limit(1)
        ).first()
    aluguel, inadimplencia, concessao, perda = (int(valor) for valor in somas)  # Decimal no Postgres
    return {
        "data_corte": _iso(corte),
        "receita_mdr_dia_centavos": int(receita_mdr),
        "receita_aluguel_e_tarifas_dia_centavos": aluguel,
        "inadimplencia_dia_centavos": inadimplencia,
        "concessao_em_acordos_dia_centavos": concessao,
        "perda_chargeback_dia_centavos": perda,
        "maior_venda": {"dia": _iso(maior.dia), "maior_venda_dia_centavos": maior.maior_venda_dia_centavos}
        if maior else None,
    }


def _taxa_em_pontos_base(chargebacks: int, vendas: int) -> int | None:
    return (20000 * chargebacks + vendas) // (2 * vendas) if vendas else None


def contestacoes_por_mes(
    origem: Session | Engine,
    mes_inicio: str | None = None,
    mes_fim: str | None = None,
    codigo: str | None = None,
) -> dict:
    """Vendas no cartão, chargebacks e a taxa (pontos-base, 100 = 1%) por mês, de um lojista ou de todos."""
    falhas.verificar("analitica")
    tabela = AnaliticaContestacoesMensais
    with _sessao_de(origem) as sessao:
        corte = _corte(sessao)
        consulta = select(
            tabela.mes, func.sum(tabela.quantidade_vendas_cartao), func.sum(tabela.quantidade_chargebacks),
        ).where(tabela.mes <= f"{corte:%Y-%m}")
        if mes_inicio is not None:
            consulta = consulta.where(tabela.mes >= mes_inicio)
        if mes_fim is not None:
            consulta = consulta.where(tabela.mes <= mes_fim)
        if codigo is not None:
            consulta = consulta.where(tabela.id_lojista == codigo)
        consulta = consulta.group_by(tabela.mes).order_by(tabela.mes)
        itens = [
            {"mes": mes, "quantidade_vendas_cartao": int(vendas), "quantidade_chargebacks": int(chargebacks),
             "taxa_chargeback_pontos_base": _taxa_em_pontos_base(int(chargebacks), int(vendas))}
            for mes, vendas, chargebacks in sessao.execute(consulta)
        ]
    return {"data_corte": _iso(corte), "itens": itens}


# ---------------------------------------------------------------------------------------------
# Dicionário de dados (metadado): tabelas, colunas e sensibilidade, lidos do próprio esquema
# ---------------------------------------------------------------------------------------------


def dicionario_de_dados() -> list[dict]:
    """Uma entrada por tabela do mock: sistema dono, descrição, de onde vem (base analítica) e colunas.

    Não lê o banco: descreve o esquema (`modelos.py`). Coluna restrita é a de `regras.CLASSIFICACAO_CAMPOS`,
    a mesma lista que a máscara usa; nenhum dado sai daqui. As chaves têm nome próprio (`coluna`, e não
    `nome`, que a máscara trata como nome de pessoa) e estão em `regras.CAMPOS_NAO_RESTRITOS`.
    """
    tabelas = []
    for tabela in BaseMock.metadata.sorted_tables:
        colunas = [
            {
                "coluna": coluna.name,
                "tipo_da_coluna": type(coluna.type).__name__.lower(),
                "descricao_da_coluna": coluna.comment or "",
                "restrita": coluna.name in regras.CLASSIFICACAO_CAMPOS,
            }
            for coluna in tabela.columns
        ]
        tabelas.append({
            "tabela": tabela.name,
            "sistema": SISTEMA_DONO_DA_TABELA[tabela.name],
            "descricao_da_tabela": tabela.comment or "",
            "origem": list(ORIGEM_DAS_TABELAS_ANALITICAS.get(tabela.name, ())),
            "colunas": colunas,
        })
    return tabelas
