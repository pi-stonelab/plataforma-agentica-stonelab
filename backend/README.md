# Back-end

API FastAPI da plataforma. Pré-requisitos: Python 3.11+ e Docker Desktop.

## Primeira vez

1. Na raiz do repositório, copie `.env.example` para `.env` e preencha `POSTGRES_PASSWORD`
   e `DATABASE_URL` (com a mesma senha). O `.env` nunca vai para o Git.
2. Suba o banco (na raiz):
   ```
   docker compose up -d
   ```
3. Instale as dependências (dentro de `backend/`, de preferência num ambiente virtual):
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # Linux/Mac
   pip install -r requirements.txt
   ```

## Rodar

Dentro de `backend/`:
```
uvicorn app.main:app --reload
```
- http://127.0.0.1:8000/health → `{"status": "ok", "banco": "ok"}`
- http://127.0.0.1:8000/docs → documentação das rotas (contrato com a interface)

## Testes

Dentro de `backend/` (não precisam do Docker, usam SQLite em memória):
```
pytest
```

## Banco do zero

Sem Alembic na Sprint 2: mudou uma tabela, apague o banco e suba de novo.
```
docker compose down -v
docker compose up -d
```
