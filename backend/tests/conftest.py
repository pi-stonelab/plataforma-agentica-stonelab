import os

# Os testes usam SQLite em memória: não precisam do Postgres nem do Docker.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
# O .env de quem desenvolve não pode mudar o resultado dos testes: a variável vazia vence o .env,
# porque o dotenv não sobrescreve variável já declarada. Cada teste que precisa dela a define.
os.environ["MOCK_DATABASE_URL"] = ""
