"""Tabelas do mock (fase 1 reduzida). Dinheiro sempre em centavos (inteiro).

`BaseMock` é separada da `Base` do back-end: criar ou apagar as tabelas do mock nunca toca nas
tabelas da plataforma. Só existem colunas que alguma ferramenta usa.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseMock(DeclarativeBase):
    """Toda tabela do mock herda desta classe."""


SITUACOES_FUNCIONARIO = ("ativo", "afastado", "desligado")
SITUACOES_LOJISTA = ("ativo", "inativo", "bloqueado", "encerrado")
SITUACOES_CONTA = ("ativa", "em_verificacao", "invalida")
MODALIDADES = ("debito", "credito_a_vista", "parcelado", "pix")
SITUACOES_VENDA = ("aprovada", "negada", "cancelada")
SITUACOES_LIQUIDACAO = ("paga", "falhou", "devolvida")
TIPOS_FATURA = ("aluguel", "tarifa", "saldo_negativo")
SITUACOES_FATURA = ("aberta", "paga", "vencida", "em_acordo", "cancelada")
AUTORES_INTERACAO = ("lojista", "funcionario", "agente")


def _restricao(coluna: str, valores: tuple[str, ...]) -> CheckConstraint:
    """Aceita só os valores listados (o banco recusa o resto)."""
    lista = ", ".join(f"'{valor}'" for valor in valores)
    return CheckConstraint(f"{coluna} IN ({lista})", name=f"ck_{coluna}_{len(valores)}")


class Time(BaseMock):
    """Time de funcionários. `carteira` vazia = time sem carteira própria."""

    __tablename__ = "times"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    area: Mapped[str] = mapped_column(String(20))
    carteira: Mapped[str | None] = mapped_column(String(20))


class Funcionario(BaseMock):
    """Diretório de funcionários (DOC-MOCK §3.3). Pessoa real de teste tem id F9xxx."""

    __tablename__ = "funcionarios"
    __table_args__ = (_restricao("situacao", SITUACOES_FUNCIONARIO),)

    id: Mapped[str] = mapped_column(String(5), primary_key=True)  # F0001
    nome: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str] = mapped_column(String(40))
    id_time: Mapped[int | None] = mapped_column(ForeignKey("times.id"))
    situacao: Mapped[str] = mapped_column(String(12), default="ativo")
    pessoa_real_teste: Mapped[bool] = mapped_column(Boolean, default=False)


class Lojista(BaseMock):
    """Cadastro do lojista. `id_responsavel` é o especialista N2 das contas-chave."""

    __tablename__ = "lojistas"
    __table_args__ = (_restricao("situacao", SITUACOES_LOJISTA),)

    codigo: Mapped[str] = mapped_column(String(6), primary_key=True)  # M00001
    nome_fantasia: Mapped[str] = mapped_column(String(80))
    segmento: Mapped[str] = mapped_column(String(30))
    porte: Mapped[str] = mapped_column(String(5))
    cidade: Mapped[str] = mapped_column(String(60))
    uf: Mapped[str] = mapped_column(String(2))
    carteira: Mapped[str] = mapped_column(String(20))
    situacao: Mapped[str] = mapped_column(String(12), default="ativo")
    data_entrada: Mapped[date] = mapped_column(Date)
    id_responsavel: Mapped[str | None] = mapped_column(ForeignKey("funcionarios.id"))


class ContatoLojista(BaseMock):
    """Pessoa de contato do lojista. Nome, CPF, telefone e e-mail são restritos."""

    __tablename__ = "contatos_lojista"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    cpf: Mapped[str] = mapped_column(String(14))
    papel: Mapped[str] = mapped_column(String(20))  # socio | financeiro | operador_caixa
    telefone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(120))


class ContaRecebimento(BaseMock):
    """Conta onde caem as liquidações. Banco, agência e conta são restritos."""

    __tablename__ = "contas_recebimento"
    __table_args__ = (_restricao("situacao", SITUACOES_CONTA),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), unique=True)
    banco: Mapped[str] = mapped_column(String(40))
    agencia: Mapped[str] = mapped_column(String(10))
    conta: Mapped[str] = mapped_column(String(15))
    situacao: Mapped[str] = mapped_column(String(15))


class Venda(BaseMock):
    """Venda no cartão ou Pix. Só bandeira e 4 últimos dígitos: nunca o número do cartão."""

    __tablename__ = "vendas"
    __table_args__ = (
        _restricao("modalidade", MODALIDADES),
        _restricao("situacao", SITUACOES_VENDA),
    )

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)  # T0000001
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), index=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime)
    modalidade: Mapped[str] = mapped_column(String(20))
    parcelas: Mapped[int] = mapped_column(Integer, default=1)
    bandeira: Mapped[str | None] = mapped_column(String(15))
    ultimos4: Mapped[str | None] = mapped_column(String(4))
    valor_bruto_centavos: Mapped[int] = mapped_column(Integer)
    valor_liquido_centavos: Mapped[int] = mapped_column(Integer)
    situacao: Mapped[str] = mapped_column(String(12))


class Liquidacao(BaseMock):
    """Depósito diário ao lojista (soma dos recebíveis do dia, menos descontos)."""

    __tablename__ = "liquidacoes"
    __table_args__ = (_restricao("situacao", SITUACOES_LIQUIDACAO),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), index=True)
    data: Mapped[date] = mapped_column(Date)
    valor_total_centavos: Mapped[int] = mapped_column(Integer)
    situacao: Mapped[str] = mapped_column(String(12))


class Fatura(BaseMock):
    """Fatura que o lojista deve à Stone (aluguel, tarifa ou saldo negativo)."""

    __tablename__ = "faturas"
    __table_args__ = (
        _restricao("tipo", TIPOS_FATURA),
        _restricao("situacao", SITUACOES_FATURA),
    )

    codigo: Mapped[str] = mapped_column(String(7), primary_key=True)  # I000001
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), index=True)
    tipo: Mapped[str] = mapped_column(String(15))
    mes_referencia: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    vencimento: Mapped[date] = mapped_column(Date)
    valor_centavos: Mapped[int] = mapped_column(Integer)
    situacao: Mapped[str] = mapped_column(String(12))


class Chamado(BaseMock):
    """Chamado do CRM. O resumo é texto livre restrito. Pode ligar a uma liquidação ou fatura."""

    __tablename__ = "chamados"

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)  # CH000001
    protocolo: Mapped[str] = mapped_column(String(15), unique=True)  # AAAAMMDD-NNNNNN
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), index=True)
    categoria: Mapped[str] = mapped_column(String(40))
    prioridade: Mapped[str] = mapped_column(String(10))
    fila: Mapped[str] = mapped_column(String(20))
    id_responsavel: Mapped[str | None] = mapped_column(ForeignKey("funcionarios.id"))
    situacao: Mapped[str] = mapped_column(String(25))
    aberto_por: Mapped[str] = mapped_column(String(12))  # sistema | lojista | funcionario
    aberto_em: Mapped[datetime] = mapped_column(DateTime)
    resumo: Mapped[str] = mapped_column(Text)
    id_liquidacao: Mapped[int | None] = mapped_column(ForeignKey("liquidacoes.id"))
    id_fatura: Mapped[str | None] = mapped_column(ForeignKey("faturas.codigo"))


class Interacao(BaseMock):
    """Mensagem dentro de um chamado. Texto livre: é por onde a injeção de comando chegaria."""

    __tablename__ = "interacoes"
    __table_args__ = (_restricao("autor", AUTORES_INTERACAO),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_chamado: Mapped[str] = mapped_column(ForeignKey("chamados.codigo"), index=True)
    autor: Mapped[str] = mapped_column(String(12))
    canal: Mapped[str] = mapped_column(String(15))
    data_hora: Mapped[datetime] = mapped_column(DateTime)
    texto: Mapped[str] = mapped_column(Text)
    teste_seguranca: Mapped[bool] = mapped_column(Boolean, default=False)
    comportamento_esperado: Mapped[str | None] = mapped_column(Text)
