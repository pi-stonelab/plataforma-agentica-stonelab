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

## Demonstração

O front servido pelo back-end tem duas formas de abrir:

| Endereço | O que mostra |
| --- | --- |
| http://127.0.0.1:8000/app/?mock=0 | A interface falando com a API real (forma recomendada na opção A do contrato) |
| http://127.0.0.1:8000/docs | As rotas, para chamar a API sem a interface |

Sem `?mock=0` o front abre em modo simulado. A escolha fica guardada no navegador; `?mock=1` volta ao simulado.
Qual das duas vai para a banca ainda precisa ser combinado com a Larissa.

### Tempo por turno

Um turno tem prazo total de 300 s (`SEGUNDOS_POR_TURNO`, em `agentes/`). Para trocar, preencha `TURNO_SEGUNDOS`
no `.env` (número maior que zero, até 1000) e reinicie o back-end. Vazio mantém o padrão.

- Com 45 a 50 s por chamada ao modelo, 300 s comportam cerca de 6 chamadas. Um turno com uma ferramenta usa 4 ou 5.
- No teste de 16/11, o cenário de três ferramentas levou perto de 8 minutos, acima do padrão.
- Aumentar o prazo não garante a tela: o navegador também desiste de um pedido sem resposta. Há relato de limite
  perto de [300 s no Chrome e 90 s no Firefox](https://dmitripavlutin.com/timeout-fetch-request/) (não medido
  aqui). Para a banca, prefira pedidos de uma ferramenta e ensaie no navegador que será usado.

## Auditoria, execuções e uso do modelo

| Tabela | Uma linha por | Se a gravação falhar |
| --- | --- | --- |
| `auditoria` | decisão de acesso da `Plataforma` | a ação é negada (403) |
| `execucoes_ferramenta` | registro de chamada de ferramenta (`governanca.CAMPOS_REGISTRO`) | a ferramenta não entrega a resposta |
| `uso_modelo` | resposta do modelo | o turno é interrompido (503) |

Nenhuma delas guarda argumento, dado de lojista, texto de conversa ou nome de pessoa. O `execucao_id` liga as três.
O uso é gravado a cada chamada, então fica registrado mesmo quando o turno termina em 504.

`GET /auditoria` devolve a trilha só para o perfil `Auditor` (formato na §5.10 de `frontend/CONTRATO_API.md`).
Cada consulta também fica na auditoria.

## Rodar no Docker

Na raiz, com o `.env` preenchido:
```
docker compose --profile app up -d --build
docker compose --profile app exec backend python -m app.seed
```
- Sem `--profile app`, o Compose continua subindo só o banco.
- No contêiner, `DATABASE_URL` é montada pelo Compose com `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`.
  Use uma senha sem `@ : / ? # %` e sem `$`.
- O mock roda em SQLite no volume `dados_mock`. `MOCK_DATABASE_URL` e `MOCK_ESCRITA_DATABASE_URL` do `.env` são
  ignoradas no contêiner.
- Endereços e caminhos do `.env` valem de dentro do contêiner: `localhost` (ex.: `EMAIL_SMTP_HOST`) não é a sua máquina.
- A porta 8000 só atende a própria máquina. Para abrir de outro computador numa rede confiável, defina
  `API_BIND=0.0.0.0` no `.env` (a conexão é HTTP, sem criptografia).
- Mantenha um único processo do uvicorn: as prévias de escrita ficam em memória.
- Para parar: `docker compose --profile app down`.

## Raspberry Pi e memória

Precisa de um sistema de 64 bits (`uname -m` responde `aarch64`) com Docker e o plugin Compose. Clone o
repositório no Pi, preencha o `.env` e rode os dois comandos de "Rodar no Docker".

Meça parado e durante uma conversa:
```
docker stats --no-stream
free -h
```
Para registrar ao longo da demonstração (Ctrl+C encerra):
```
while true; do docker stats --no-stream --format "$(date +%T),{{.Name}},{{.MemUsage}}" | tee -a memoria.csv; sleep 5; done
```
Se o `docker stats` mostrar `0B` de memória, acrescente `cgroup_enable=memory cgroup_memory=1` ao fim da única
linha de `/boot/firmware/cmdline.txt` e reinicie o Pi.

| Situação | `backend` | `db` | Data |
| --- | --- | --- | --- |
| Parado | a medir | a medir | |
| Durante um turno | a medir | a medir | |

## Testes

Dentro de `backend/` (não precisam do Docker, usam SQLite em memória):
```
pytest
```
O CI roda o mesmo comando em todo PR para a `main` (job `testes`).

## Banco do zero

Sem Alembic na Sprint 2: tabela nova é criada ao subir; mudou uma tabela que já existe, apague o banco e suba de
novo. Isso também apaga a auditoria.
```
docker compose down -v
docker compose up -d
```
