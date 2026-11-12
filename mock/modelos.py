"""Esquema do mock (a Stone simulada): 10 tabelas, dinheiro sempre em centavos (inteiro).

`BaseMock` é separada da `Base` do back-end: criar ou apagar as tabelas do mock nunca toca nas
tabelas da plataforma. Só existem colunas que alguma ferramenta usa.

O banco também se defende sozinho, além das regras da aplicação: chave primária, chave estrangeira,
NOT NULL, listas de valores aceitos (CHECK) e regras entre colunas (ex.: Pix não tem bandeira). Os
nomes das restrições seguem `CONVENCAO_DE_NOMES`, para o SQL exportado (`mock/sql/`) ser estável.
O comentário de cada tabela e coluna diz a sensibilidade do dado; "RESTRITO" quer dizer que a
coluna sai mascarada das ferramentas (`regras.CLASSIFICACAO_CAMPOS`).
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .regras import AREAS, CARGOS, CARTEIRAS, PORTES

CONVENCAO_DE_NOMES = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


# Sobe quando o esquema muda. O SQLite local guarda a versão (PRAGMA user_version) e é refeito
# sozinho quando ela é diferente (`gerar.garantir_mundo_local`).
VERSAO_DO_ESQUEMA = 2


class BaseMock(DeclarativeBase):
    """Toda tabela do mock herda desta classe."""

    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)


# Valores aceitos em cada coluna de lista fechada. O gerador (`gerar.py`) só usa valores daqui.
SITUACOES_FUNCIONARIO = ("ativo", "afastado", "desligado")
SITUACOES_LOJISTA = ("ativo", "inativo", "bloqueado", "encerrado")
SITUACOES_CONTA = ("ativa", "em_verificacao", "invalida")
PAPEIS_CONTATO = ("socio", "financeiro", "operador_caixa")
MODALIDADES = ("debito", "credito_a_vista", "parcelado", "pix")
BANDEIRAS = ("visa", "mastercard", "elo")
SITUACOES_VENDA = ("aprovada", "negada", "cancelada")
SITUACOES_LIQUIDACAO = ("paga", "falhou", "devolvida")
TIPOS_FATURA = ("aluguel", "tarifa", "saldo_negativo")
SITUACOES_FATURA = ("aberta", "paga", "vencida", "em_acordo", "cancelada")
CATEGORIAS_DE_CHAMADO = (
    "Dúvida de produto",
    "Recebimento",
    "Maquininha",
    "Fatura e aluguel",
    "Antecipação",
    "Alteração cadastral",
    "Contestação",
)
PRIORIDADES = ("baixa", "média", "alta")
SITUACOES_CHAMADO = ("novo", "em_atendimento", "aguardando_lojista", "resolvido", "fechado")
ABERTO_POR = ("sistema", "lojista", "funcionario")
AUTORES_INTERACAO = ("lojista", "funcionario", "agente")
CANAIS = ("whatsapp", "telefone", "chat", "email")
MAXIMO_DE_PARCELAS = 12


def _um_de(coluna: str, valores: tuple[str, ...]) -> CheckConstraint:
    """Aceita só os valores listados (NULL continua valendo onde a coluna aceita NULL)."""
    lista = ", ".join("'" + valor.replace("'", "''") + "'" for valor in valores)
    return CheckConstraint(f"{coluna} IN ({lista})", name=coluna)


def _regra(nome: str, condicao: str) -> CheckConstraint:
    return CheckConstraint(condicao, name=nome)


class Time(BaseMock):
    __tablename__ = "times"
    __table_args__ = (
        _um_de("area", AREAS),
        _um_de("carteira", CARTEIRAS),
        {"comment": "Times de funcionários. Interno. Carteira vazia: time sem carteira própria."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    area: Mapped[str] = mapped_column(String(20))
    carteira: Mapped[str | None] = mapped_column(String(20))


class Funcionario(BaseMock):
    __tablename__ = "funcionarios"
    __table_args__ = (
        _um_de("situacao", SITUACOES_FUNCIONARIO),
        _um_de("cargo", tuple(CARGOS)),
        _regra("id_formato", "id LIKE 'F____'"),
        Index(None, "id_time"),
        {
            "comment": "Diretório de funcionários (DOC-MOCK §3.3). Interno. Pessoa real de teste "
            "tem id F9xxx e nunca entra no SQL exportado."
        },
    )

    id: Mapped[str] = mapped_column(String(5), primary_key=True)  # F0001
    nome: Mapped[str] = mapped_column(String(80), comment="Dado pessoal. Nenhuma ferramenta devolve.")
    email: Mapped[str] = mapped_column(String(120), comment="Dado pessoal. Nenhuma ferramenta devolve.")
    cargo: Mapped[str] = mapped_column(String(40), comment="Decide nível, área e categorias de dado.")
    id_time: Mapped[int | None] = mapped_column(ForeignKey("times.id"))
    situacao: Mapped[str] = mapped_column(String(12), default="ativo")
    pessoa_real_teste: Mapped[bool] = mapped_column(Boolean, default=False)


class Lojista(BaseMock):
    __tablename__ = "lojistas"
    __table_args__ = (
        _um_de("situacao", SITUACOES_LOJISTA),
        _um_de("porte", PORTES),
        _um_de("carteira", CARTEIRAS),
        _regra("codigo_formato", "codigo LIKE 'M_____'"),
        _regra("uf_formato", "length(uf) = 2"),
        {"comment": "Cadastro do lojista. Público ou interno; a carteira decide quem do atendimento vê."},
    )

    codigo: Mapped[str] = mapped_column(String(6), primary_key=True)  # M00001
    nome_fantasia: Mapped[str] = mapped_column(String(80))
    segmento: Mapped[str] = mapped_column(String(30))
    porte: Mapped[str] = mapped_column(String(5))
    cidade: Mapped[str] = mapped_column(String(60))
    uf: Mapped[str] = mapped_column(String(2))
    carteira: Mapped[str] = mapped_column(String(20), comment="Escopo do atendimento.")
    situacao: Mapped[str] = mapped_column(String(12), default="ativo")
    data_entrada: Mapped[date] = mapped_column(Date)
    id_responsavel: Mapped[str | None] = mapped_column(
        ForeignKey("funcionarios.id"), comment="Especialista N2 das contas-chave."
    )


class ContatoLojista(BaseMock):
    __tablename__ = "contatos_lojista"
    __table_args__ = (
        _um_de("papel", PAPEIS_CONTATO),
        Index(None, "id_lojista"),
        {"comment": "Pessoas de contato do lojista. RESTRITO: nome, CPF, telefone e e-mail saem mascarados."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"))
    nome: Mapped[str] = mapped_column(String(80), comment="RESTRITO (nome).")
    cpf: Mapped[str] = mapped_column(String(14), comment="RESTRITO (cpf).")
    papel: Mapped[str] = mapped_column(String(20))
    telefone: Mapped[str] = mapped_column(String(20), comment="RESTRITO (telefone).")
    email: Mapped[str] = mapped_column(String(120), comment="RESTRITO (email).")


class ContaRecebimento(BaseMock):
    __tablename__ = "contas_recebimento"
    __table_args__ = (
        _um_de("situacao", SITUACOES_CONTA),
        {"comment": "Conta onde caem as liquidações, uma por lojista. RESTRITO: agência e conta."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"), unique=True)
    banco: Mapped[str] = mapped_column(String(40))
    agencia: Mapped[str] = mapped_column(String(10), comment="RESTRITO (conta).")
    conta: Mapped[str] = mapped_column(String(15), comment="RESTRITO (conta).")
    situacao: Mapped[str] = mapped_column(String(15))


class Venda(BaseMock):
    __tablename__ = "vendas"
    __table_args__ = (
        _um_de("modalidade", MODALIDADES),
        _um_de("situacao", SITUACOES_VENDA),
        _um_de("bandeira", BANDEIRAS),
        _regra("codigo_formato", "codigo LIKE 'T_______'"),
        _regra("ultimos4_formato", "ultimos4 IS NULL OR length(ultimos4) = 4"),
        _regra(
            "cartao_conforme_modalidade",
            "(modalidade = 'pix' AND bandeira IS NULL AND ultimos4 IS NULL)"
            " OR (modalidade <> 'pix' AND bandeira IS NOT NULL AND ultimos4 IS NOT NULL)",
        ),
        _regra(
            "parcelas_conforme_modalidade",
            f"(modalidade = 'parcelado' AND parcelas BETWEEN 2 AND {MAXIMO_DE_PARCELAS})"
            " OR (modalidade <> 'parcelado' AND parcelas = 1)",
        ),
        _regra("valor_bruto_positivo", "valor_bruto_centavos > 0"),
        _regra("valor_liquido_ate_o_bruto", "valor_liquido_centavos BETWEEN 0 AND valor_bruto_centavos"),
        _regra("sem_liquido_se_nao_aprovada", "situacao = 'aprovada' OR valor_liquido_centavos = 0"),
        Index(None, "id_lojista", "data_hora"),
        {"comment": "Vendas no cartão ou Pix. Nunca o número do cartão: só bandeira e 4 últimos dígitos."},
    )

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)  # T0000001
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"))
    data_hora: Mapped[datetime] = mapped_column(DateTime)
    modalidade: Mapped[str] = mapped_column(String(20))
    parcelas: Mapped[int] = mapped_column(Integer, default=1)
    bandeira: Mapped[str | None] = mapped_column(String(15))
    ultimos4: Mapped[str | None] = mapped_column(String(4), comment="RESTRITO (cartao).")
    valor_bruto_centavos: Mapped[int] = mapped_column(BigInteger)
    valor_liquido_centavos: Mapped[int] = mapped_column(BigInteger)
    situacao: Mapped[str] = mapped_column(String(12))


class Liquidacao(BaseMock):
    __tablename__ = "liquidacoes"
    __table_args__ = (
        _um_de("situacao", SITUACOES_LIQUIDACAO),
        _regra("valor_nao_negativo", "valor_total_centavos >= 0"),
        _regra(
            "motivo_so_quando_falha",
            "(situacao = 'paga' AND motivo_falha IS NULL)"
            " OR (situacao <> 'paga' AND motivo_falha IS NOT NULL)",
        ),
        Index(None, "id_lojista", "data"),
        {"comment": "Depósito diário ao lojista (recebíveis do dia menos descontos). Confidencial."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"))
    data: Mapped[date] = mapped_column(Date)
    valor_total_centavos: Mapped[int] = mapped_column(BigInteger)
    situacao: Mapped[str] = mapped_column(String(12))
    motivo_falha: Mapped[str | None] = mapped_column(String(30))


class Fatura(BaseMock):
    __tablename__ = "faturas"
    __table_args__ = (
        _um_de("tipo", TIPOS_FATURA),
        _um_de("situacao", SITUACOES_FATURA),
        _regra("codigo_formato", "codigo LIKE 'I______'"),
        _regra("mes_referencia_formato", "mes_referencia LIKE '____-__'"),
        _regra("valor_positivo", "valor_centavos > 0"),
        Index(None, "id_lojista", "vencimento"),
        {"comment": "O que o lojista deve à Stone (aluguel, tarifa ou saldo negativo). Confidencial."},
    )

    codigo: Mapped[str] = mapped_column(String(7), primary_key=True)  # I000001
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"))
    tipo: Mapped[str] = mapped_column(String(15))
    mes_referencia: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    vencimento: Mapped[date] = mapped_column(Date)
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    situacao: Mapped[str] = mapped_column(String(12))


class Chamado(BaseMock):
    __tablename__ = "chamados"
    __table_args__ = (
        _um_de("categoria", CATEGORIAS_DE_CHAMADO),
        _um_de("prioridade", PRIORIDADES),
        _um_de("fila", CARTEIRAS),
        _um_de("situacao", SITUACOES_CHAMADO),
        _um_de("aberto_por", ABERTO_POR),
        _regra("codigo_formato", "codigo LIKE 'CH______'"),
        _regra("protocolo_formato", "protocolo LIKE '________-______'"),
        Index(None, "id_lojista", "aberto_em"),
        {"comment": "Chamados do CRM. RESTRITO: o resumo é texto livre e sai mascarado."},
    )

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)  # CH000001
    protocolo: Mapped[str] = mapped_column(String(15), unique=True)  # AAAAMMDD-NNNNNN
    id_lojista: Mapped[str] = mapped_column(ForeignKey("lojistas.codigo"))
    categoria: Mapped[str] = mapped_column(String(40))
    prioridade: Mapped[str] = mapped_column(String(10))
    fila: Mapped[str] = mapped_column(String(20))
    id_responsavel: Mapped[str | None] = mapped_column(ForeignKey("funcionarios.id"))
    situacao: Mapped[str] = mapped_column(String(25))
    aberto_por: Mapped[str] = mapped_column(String(12))
    aberto_em: Mapped[datetime] = mapped_column(DateTime)
    resumo: Mapped[str] = mapped_column(Text, comment="RESTRITO (texto livre).")
    id_liquidacao: Mapped[int | None] = mapped_column(ForeignKey("liquidacoes.id"))
    id_fatura: Mapped[str | None] = mapped_column(ForeignKey("faturas.codigo"))


class Interacao(BaseMock):
    __tablename__ = "interacoes"
    __table_args__ = (
        _um_de("autor", AUTORES_INTERACAO),
        _um_de("canal", CANAIS),
        Index(None, "id_chamado", "data_hora"),
        {"comment": "Mensagens dos chamados. RESTRITO: texto livre, por onde chegaria uma injeção de comando."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_chamado: Mapped[str] = mapped_column(ForeignKey("chamados.codigo"))
    autor: Mapped[str] = mapped_column(String(12))
    canal: Mapped[str] = mapped_column(String(15))
    data_hora: Mapped[datetime] = mapped_column(DateTime)
    texto: Mapped[str] = mapped_column(Text, comment="RESTRITO (texto livre). Sempre dado, nunca ordem.")
    teste_seguranca: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Marca o dado de teste de segurança (DOC-MOCK §10.3)."
    )
    comportamento_esperado: Mapped[str | None] = mapped_column(Text)
