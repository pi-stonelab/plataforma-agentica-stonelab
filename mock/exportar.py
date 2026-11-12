"""Exporta o mundo do mock como SQL pronto: `mock/sql/<banco>/01_esquema.sql` e `02_dados.sql`.

Os arquivos vão para o Git. Quem baixa o repositório carrega o mock sem rodar Python:
o Postgres do `mock/docker-compose.yml` lê `mock/sql/postgres/` sozinho na primeira subida, e o
SQLite local é montado a partir de `mock/sql/sqlite/` (`gerar.garantir_mundo_local`).

A fonte da verdade continua sendo o código (`modelos.py` e `gerar.py`); o SQL é o resultado. Um teste
confere que os arquivos do Git são iguais ao que este módulo gera. Mudou o esquema ou o gerador:

    python -m mock.exportar            # regrava os arquivos
    python -m mock.exportar --conferir # só confere (sai com 1 se estiver desatualizado)

Nunca exporta pessoa real de teste (CSV de `dados_locais/`): o mundo é gerado só da semente.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine, Integer, Table, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Dialect
from sqlalchemy.schema import (
    CreateIndex,
    CreateTable,
    SetColumnComment,
    SetTableComment,
)

from .banco import criar_engine
from .gerar import SEMENTE, recriar
from .modelos import VERSAO_DO_ESQUEMA, BaseMock, Funcionario

PASTA_SQL = Path(__file__).resolve().parent / "sql"
ARQUIVO_ESQUEMA = "01_esquema.sql"
ARQUIVO_DADOS = "02_dados.sql"
DIALETOS: dict[str, Dialect] = {"sqlite": sqlite.dialect(), "postgres": postgresql.dialect()}

CABECALHO = f"""-- Mock da Stone (Plataforma Agêntica Institucional). 100% sintético: nenhum dado real.
-- Gerado por `python -m mock.exportar` a partir de mock/modelos.py e mock/gerar.py
-- (semente {SEMENTE}, esquema versão {VERSAO_DO_ESQUEMA}). Não edite à mão: rode o exportador.
"""


def _tabelas() -> list[Table]:
    """Tabelas em ordem de dependência: quem é referenciado vem antes."""
    return list(BaseMock.metadata.sorted_tables)


def _instrucao(elemento, dialeto: Dialect, **opcoes) -> str:
    return str(elemento.compile(dialect=dialeto, **opcoes)).strip() + ";"


def _ddl(elemento, dialeto: Dialect) -> str:
    """CREATE e COMMENT sem tabulação nem espaço no fim da linha (o texto não tem literal multilinha)."""
    linhas = _instrucao(elemento, dialeto).replace("\t", "    ").splitlines()
    return "\n".join(linha.rstrip() for linha in linhas)


def _id_com_sequencia(tabela: Table) -> str | None:
    """Nome da coluna inteira que o Postgres numera sozinho (SERIAL), se houver."""
    chave = list(tabela.primary_key.columns)
    if len(chave) == 1 and isinstance(chave[0].type, Integer) and chave[0].autoincrement in (True, "auto"):
        return chave[0].name
    return None


def esquema_sql(banco: str) -> str:
    """CREATE TABLE e CREATE INDEX de todas as tabelas, mais os comentários de sensibilidade."""
    dialeto = DIALETOS[banco]
    partes = [CABECALHO]
    for tabela in _tabelas():
        if banco == "sqlite":  # o SQLite não guarda comentário: vai como comentário do arquivo
            partes.append(f"-- {tabela.name}: {tabela.comment}")
        partes.append(_ddl(CreateTable(tabela), dialeto))
        for indice in sorted(tabela.indexes, key=lambda i: i.name):
            partes.append(_ddl(CreateIndex(indice), dialeto))
        if banco == "postgres":
            partes.append(_ddl(SetTableComment(tabela), dialeto))
            for coluna in tabela.columns:
                if coluna.comment:
                    partes.append(_ddl(SetColumnComment(coluna), dialeto))
        partes.append("")
    if banco == "sqlite":
        partes.append(f"PRAGMA user_version = {VERSAO_DO_ESQUEMA};")
    return "\n".join(partes).rstrip() + "\n"


def _mundo() -> Engine:
    """O mundo da semente, em memória e sem pessoas reais de teste."""
    engine = criar_engine("sqlite://")
    recriar(engine, caminho_pessoas_teste=None)
    with engine.connect() as conexao:
        reais = conexao.scalars(select(Funcionario.id).where(Funcionario.pessoa_real_teste)).all()
    if reais:  # defesa em profundidade: o recriar acima já não lê CSV nenhum
        raise RuntimeError("O mundo exportado não pode ter pessoa real de teste.")
    return engine


def dados_sql(banco: str, engine: Engine | None = None) -> str:
    """Um INSERT por linha, em ordem de chave primária, numa transação só."""
    dialeto = DIALETOS[banco]
    engine = engine or _mundo()
    partes = [CABECALHO, "BEGIN;", ""]
    with engine.connect() as conexao:
        for tabela in _tabelas():
            linhas = conexao.execute(select(tabela).order_by(*tabela.primary_key.columns)).mappings()
            partes.append(f"-- {tabela.name}")
            for linha in linhas:
                instrucao = insert(tabela).values(**linha)
                partes.append(_instrucao(instrucao, dialeto, compile_kwargs={"literal_binds": True}))
            coluna_id = _id_com_sequencia(tabela)
            if banco == "postgres" and coluna_id:
                # os ids vieram escritos; a sequência precisa continuar depois do maior
                partes.append(
                    f"SELECT setval(pg_get_serial_sequence('{tabela.name}', '{coluna_id}'), "
                    f"COALESCE((SELECT max({coluna_id}) FROM {tabela.name}), 1));"
                )
            partes.append("")
    partes.append("COMMIT;")
    return "\n".join(partes) + "\n"


def arquivos() -> dict[Path, str]:
    """Todos os arquivos exportados, com o conteúdo que deveriam ter."""
    engine = _mundo()
    conteudo = {}
    for banco in DIALETOS:
        conteudo[PASTA_SQL / banco / ARQUIVO_ESQUEMA] = esquema_sql(banco)
        conteudo[PASTA_SQL / banco / ARQUIVO_DADOS] = dados_sql(banco, engine)
    engine.dispose()
    return conteudo


def desatualizados() -> list[Path]:
    """Arquivos que faltam ou diferem do que o exportador gera agora."""
    return [
        caminho
        for caminho, texto in arquivos().items()
        if not caminho.exists() or caminho.read_text(encoding="utf-8") != texto
    ]


def principal(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description="Exporta o mock como SQL pronto (mock/sql/).")
    analisador.add_argument("--conferir", action="store_true", help="só confere, sem gravar")
    parametros = analisador.parse_args(argumentos)
    if parametros.conferir:
        faltando = desatualizados()
        for caminho in faltando:
            print(f"Desatualizado: {caminho.relative_to(PASTA_SQL.parent.parent)}", file=sys.stderr)
        return 1 if faltando else 0
    for caminho, texto in arquivos().items():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        print(f"Gravado: {caminho.relative_to(PASTA_SQL.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
