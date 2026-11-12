import os

# Os testes usam SQLite em memória: não precisam do Postgres nem do Docker.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
