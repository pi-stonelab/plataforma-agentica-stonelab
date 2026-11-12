"""O "conector" do mock: leituras nomeadas e parametrizadas, só com as colunas necessárias.

Cada função recebe uma `Session` (ou um engine) e devolve dicionários simples. Valores em
centavos; datas em texto ISO (a conversão para reais e para o formato de exibição é de quem
mostra). Listas devolvem no máximo 50 linhas, mais o total encontrado. Aqui não há regra de
permissão: quem decide se o cargo pode chamar é a governança das ferramentas.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from . import falhas
from .modelos import (
    Chamado,
    ContaRecebimento,
    ContatoLojista,
    Fatura,
    Funcionario,
    Interacao,
    Liquidacao,
    Lojista,
    Time,
    Venda,
)
from .regras import area_do_cargo

LIMITE_MAXIMO = 50


@contextmanager
def _sessao_de(origem: Session | Engine) -> Iterator[Session]:
    """Usa a sessão recebida ou abre (e fecha) uma a partir do engine."""
    if isinstance(origem, Session):
        yield origem
    else:
        with Session(origem) as sessao:
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
        Liquidacao.id, Liquidacao.data, Liquidacao.valor_total_centavos, Liquidacao.situacao
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
    """Faturas do lojista, da mais recente para a mais antiga."""
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
        item["vencimento"] = _iso(item["vencimento"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, None, formatar)


def buscar_chamados(origem: Session | Engine, codigo: str, limite: int | None = None) -> dict:
    """Chamados do lojista, do mais recente para o mais antigo."""
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
        item["aberto_em"] = _iso(item["aberto_em"])
        return item

    with _sessao_de(origem) as sessao:
        return _lista(sessao, consulta, limite, formatar)


def buscar_interacoes(
    origem: Session | Engine, codigo_chamado: str, limite: int | None = None
) -> dict:
    """Interações de um chamado, em ordem cronológica. Texto livre: conteúdo de terceiros."""
    falhas.verificar("crm")
    consulta = (
        select(
            Interacao.id, Interacao.autor, Interacao.canal, Interacao.data_hora, Interacao.texto
        )
        .where(Interacao.id_chamado == codigo_chamado)
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
