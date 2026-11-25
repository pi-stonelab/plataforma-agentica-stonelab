# Back-end

API FastAPI da plataforma. Pré-requisitos: Python 3.11+ e Docker Desktop.

## Primeira vez

1. Na raiz do repositório, copie `.env.example` para `.env` e preencha `POSTGRES_PASSWORD`
   e `DATABASE_URL` (com a mesma senha), `JWT_SEGREDO` (texto longo e aleatório, pelo menos 32 caracteres) e
   `SEED_SENHA_DEMO` (a senha das contas da demo). O `.env` nunca vai para o Git.
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
4. Crie as contas da demo (dentro de `backend/`). Elas vêm dos funcionários do mock (`F0001`…`F0015`, mais o
   `G0001` de gestão de acessos); o banco do mock é criado sozinho na primeira vez (ou por `python -m mock.gerar`):
   ```
   python -m app.seed
   ```
   O e-mail de cada conta é o do mock (ex.: `ana.lima@stonesim.example`). A tabela está na §7.1 de
   `frontend/CONTRATO_API.md`.

## Rodar

Dentro de `backend/`:
```
uvicorn app.main:app --reload
```
- http://127.0.0.1:8000/health → `{"status": "ok", "banco": "ok"}`
- http://127.0.0.1:8000/docs → documentação das rotas (contrato com a interface)
- `POST /auth/login` com `{"email", "senha"}` → `{"token", "tipo"}`; `GET /me` com `Authorization: Bearer <token>`

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
