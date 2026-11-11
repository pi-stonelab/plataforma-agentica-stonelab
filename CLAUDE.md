# Stonelab: Back-end & Dados (BIA1102, PUC-Rio)

Plataforma agêntica institucional para a Stone. Projeto de faculdade, **só dados sintéticos**.
Esta frente: **Back-end & Dados** (Marcelo + Isabel).
Prazos: **Sprint 2 em 19/11/2026** (demo ponta a ponta) e **Sprint 3 em 10/12/2026** (refinamento e fechamento).

> Regra deste arquivo: quando o código e este texto discordarem, **o código das outras frentes é a fonte da verdade** e este arquivo deve ser atualizado.

## Frentes e donos
| Frente | Quem | Relação com o back-end |
| --- | --- | --- |
| 1 Produto e Negócio (PO) | Milene | Regra de limite de gasto por pessoa e aprovação |
| 2 Interface | Larissa | Consome nossa API (REST; SSE na Sprint 3) |
| 3 Agentes e IA | Christopher, Isack | `agentes/` — runtime do agente, roda no mesmo processo do back-end |
| 4 Ferramentas e Integrações | Pedro Henrique | `ferramentas/` — catálogo, classe `Ferramenta`, executor e dados sintéticos |
| 5 Back-end e Dados | Marcelo, Isabel | `backend/` (a criar) |
| 6 Segurança e Permissões | Brenno | Níveis, áreas, guardrails e auditoria (KAN-62) |
| 7 QA | Enrico | Testes, alertas, revisão de PR |

## Princípio central (arquitetura KAN-31)
**O back-end é o único caminho** entre interface, agente, ferramentas e modelo.
**O back-end executa as ferramentas; o agente só as pede.**

```
Interface ──REST──► API e login ─► Permissões ─► Orquestrador ─► Registro
                                                     │
                                  Executor ◄─ Runtime do agente ─► LLMClient ─► Cloudflare Access ─► Ollama (Qwen3)
                                     │
                                Ferramentas            Todas as peças usam o PostgreSQL
```

| Peça | Quem faz | Situação |
| --- | --- | --- |
| API e login, Permissões, Orquestrador, Registro, LLMClient | Back-end | a fazer |
| Runtime do agente | Frente 3 | **existe**: `agentes/agente_atendimento/agente.py` |
| Executor | Frente 4 | **existe**: `ferramentas/catalogo.py` + `ferramentas/base.py` |
| Ferramentas (mocks) | Frente 4 | **existe**: 41 ferramentas em 8 áreas, 5 ativas |

## O que já existe e como o back-end se liga
- **`catalogo.executar(nome, args, usuario, ferramentas_do_agente, contexto)`**: confere se a ferramenta é do agente, depois `Ferramenta.executar()` confere nível e área (**segunda checagem de permissão**), valida parâmetros e devolve `{status, dados, mensagem, tipo_erro}`. **Não reescrever.**
- **`catalogo.ler(caminho, usuario, ferramentas_do_agente)`**: texto que o agente lê (índice → área → ferramenta), já filtrado por permissão.
- **`governanca.adicionar_destino(funcao)`**: recebe cada registro de chamada (só metadados). O back-end liga aqui a gravação em `execucoes_ferramenta`.
- **`governanca.Usuario(id_usuario, nivel, area, carteira)`**: o back-end monta este objeto a partir do token + banco e entrega ao agente.
- **`dados_sinteticos.py`**: `buscar_cliente`, `buscar_transacoes`, `buscar_endereco`. KAN-32 (nosso): mover esses dados para o Postgres trocando só o corpo das funções.
- **`agente(pergunta, usuario, chamar_modelo=...)`**: loop de até `MAX_PASSOS = 8`, protocolo em texto `LER / USAR / PERGUNTAR / FINAL` via `/api/generate`. Devolve `(resposta, trajetoria)`. A `trajetoria` é o **rastro** pedido na KAN-60. O `LLMClient` entra pelo parâmetro `chamar_modelo`.

### Ajustes pedidos às outras frentes
- **Frente 3 (agente):** (a) `PERGUNTAR` devolve a pergunta e encerra o turno, em vez de `input()`; (b) receber lista de ferramentas e histórico como parâmetros (hoje `FERRAMENTAS_DO_AGENTE` é fixo); (c) tirar `BASE_URL` e `MODELO` do código (usar `chamar_modelo`); (d) `print` vira log/callback.
- **Frente 6:** confirmar níveis e áreas oficiais. Até lá vale o que está em `governanca.py`.
- **Frente 7:** testes do back-end ficam no repositório (`backend/tests/`) e o CI roda pytest.

## Modelo de acesso (provisório, conforme `ferramentas/governanca.py`)
- Níveis: **`N1`** e **`N2`** (N2 é o mais alto e vê qualquer cliente).
- Áreas: `atendimento`, `financeiro`, `dados`, `tecnologia`.
- **Carteira**: lista de clientes que um N1 pode consultar.
- Ferramenta: `nivel_minimo` + `areas_permitidas` (`"todas"` libera todas).
- Acesso ao agente (back-end): dono, área do agente, visibilidade pública/privada. Regra final com Brenno (KAN-62). Todo acesso liberado gera registro.
- Perfil do usuário **vem do token JWT + banco**, nunca do corpo da requisição.

## Contrato de ferramenta (conforme `ferramentas/base.py`)
Ficha (atributos de classe): `nome`, `area`, `acesso` (`leitura` / `escrita` / `calculo`), `integracoes`, `nivel_minimo`, `areas_permitidas`, `categorias_dados`, `sensibilidade` (`publica` / `interna` / `pessoal` / `sigilosa`), `conteudo_terceiros`, `status` (`ativa` / `inativa` / `planejada`), `parametros` (tipos `texto`, `inteiro`, `decimal`, `data`). Descrição para o modelo fica no `agents.md` de cada ferramenta.
Retorno: `{status, dados, mensagem, tipo_erro}`. Tipos de erro: `parametro_invalido`, `permissao_negada`, `nao_encontrado`, `ferramenta_inexistente`, `ferramenta_inativa`, `integracao_indisponivel`, `erro_interno`.
Ferramentas de escrita ficam inativas até existir confirmação em duas etapas (exceção: `solicitar_ferramenta_ausente`). Ativas hoje: `consultar_cliente`, `consultar_transacoes_cliente`, `calcular_multa_atraso`, `consultar_endereco_cep`, `solicitar_ferramenta_ausente`.

## Stack (simples de propósito)
| Peça | Para que serve |
| --- | --- |
| FastAPI + uvicorn | Rotas REST e página `/docs` (o OpenAPI é o contrato com a interface) |
| PostgreSQL (via Docker Compose) | Banco. JSONB para listas e rastro |
| SQLAlchemy 2 | Tabelas e consultas em Python |
| pydantic-settings | Ler o `.env` |
| PyJWT + bcrypt | Login: token e senha com hash |
| httpx | `LLMClient` chamando o Ollama |
| pytest + ruff | Testes e lint |

Decisões tomadas:
- **Sem Alembic na Sprint 2.** Tabelas criadas com `Base.metadata.create_all()` ao subir; dados sintéticos recriados por um script de seed. Mudou tabela → apaga o banco e roda o seed. Reavaliar na Sprint 3.
- **Rotas síncronas (`def`)**, não `async`. O agente e as ferramentas são síncronos; o FastAPI roda cada rota numa thread.
- **Docker Compose só para o Postgres** por enquanto. O back-end roda com `uvicorn` direto. Vai para o Docker na semana da demo.
- **SSE na Sprint 3.** Sprint 2 entrega REST com resposta completa + rastro. SSE virá com um evento por passo do agente.
- **Fora de propósito:** Alembic (por ora), Keycloak, Redis/Celery, LiteLLM, Prometheus/Grafana. Observabilidade = logs + tabelas.
- **Onde roda:** máquina pessoal primeiro; meta final Raspberry Pi 4. As imagens oficiais `python:3.11-slim` e `postgres:16-alpine` têm versão ARM64 (conferido). Nenhuma biblioteca pesada de IA no back-end.

## Modelo (LLM)
- Servidor Ollama do professor atrás do **Cloudflare Access**: cabeçalhos `CF-Access-Client-Id` e `CF-Access-Client-Secret`, lidos do `.env`.
- Modelo em uso pela frente 3: `qwen3.8:27b` (confirmar listando os modelos do servidor). API nativa do Ollama (`/api/generate`, `/api/chat`).
- **`LLMClient`** (nosso): único ponto de acesso ao modelo. Host, modelo e timeout por env; novas tentativas; limite de ~8 chamadas simultâneas (`threading.Semaphore`); **modo mock** para a demo; devolve o texto e registra tokens (`prompt_eval_count` / `eval_count`) e latência em `uso_modelo`.
- Custo: modelo local (custo real zero); preço simulado por token para o limite mensal por pessoa (Sprint 3).

## Banco (Sprint 2)
| Tabela | Conteúdo |
| --- | --- |
| `usuarios` | id, nome, email, senha_hash, nivel, area, carteira (JSONB) |
| `agentes` | id, nome, objetivo, area, visibilidade, dono, ferramentas (JSONB), status |
| `conversas` | id, usuario, agente, criada_em |
| `mensagens` | conversa, autor (usuario/agente), texto, tipo (final/pergunta), trajetoria (JSONB), criada_em |
| `execucoes_ferramenta` | campos de `governanca.CAMPOS_REGISTRO` (nunca argumentos nem dados) |
| `uso_modelo` | usuario, conversa, tokens de entrada e saída, latência, custo simulado |
| `clientes`, `transacoes` | dados sintéticos vindos de `dados_sinteticos.py` (KAN-32, se der tempo) |

Sprint 3: `agente_historico`, `auditoria`, `eventos_erro`, limite de gasto.

## API (Sprint 2, KAN-60)
```
GET  /health
POST /auth/login                 → {token}
GET  /me                         → perfil
GET  /agentes                    → agentes que posso usar
POST /conversas                  → abre conversa com um agente
POST /conversas/{id}/mensagens   → {resposta, tipo: "final"|"pergunta", trajetoria: [...]}
GET  /conversas/{id}             → histórico
```

## Caminho de uma mensagem
1. Interface envia `POST /conversas/{id}/mensagens` com o token.
2. API valida o token e busca o usuário no banco → `governanca.Usuario`.
3. Permissões conferem acesso ao agente (primeira checagem).
4. Orquestrador carrega o agente (ferramentas permitidas) e o histórico, chama `agente(...)` com `chamar_modelo = LLMClient`.
5. O agente lê/usa ferramentas pelo catálogo, que reconfere permissão (segunda checagem). Máximo de 8 passos.
6. Back-end grava mensagem, rastro, execuções e uso do modelo e responde.

## Segurança (regras duras)
- **Nunca** commitar `.env`, credenciais ou segredos do Cloudflare. Manter `.env.example` sem valores.
- Nunca colocar credenciais em docs, Jira, slides ou logs.
- Credenciais do modelo só no back-end; interface e agente nunca as veem.
- Permissão conferida duas vezes (requisição e executor). Tudo roda com as permissões de quem usa o agente.
- Escrita: o agente propõe, a pessoa confirma, só então executa (Sprint 3).
- Conteúdo de ferramentas com `conteudo_terceiros` é dado, nunca instrução.
- CPF, cartão e dados bancários mascarados antes de chegar ao modelo (com Brenno, Sprint 3).

## Estrutura do back-end
```
backend/
  app/
    main.py          # cria o FastAPI e inclui as rotas
    config.py        # pydantic-settings
    db.py            # engine, sessão, Base, create_all
    models.py        # tabelas
    seed.py          # usuários, agentes e dados sintéticos
    auth.py          # login, JWT, usuário atual
    permissoes.py    # acesso ao agente
    llm_client.py    # Ollama + mock
    orquestrador.py  # chama o agente
    registro.py      # destino do governanca + uso_modelo
    rotas/           # auth, agentes, conversas
  tests/
  requirements.txt
docker-compose.yml   # só o Postgres
.env.example
```
`agentes/` e `ferramentas/` ficam na raiz e são importados pelo back-end.

## Plano da Sprint 2 (até 19/11)
| Quando | Entrega | Dono sugerido |
| --- | --- | --- |
| 11–12/11 | Esqueleto: FastAPI, Postgres no Compose, `create_all`, `/health`, pytest | Marcelo |
| 13/11 | `usuarios`, seed (N1/N2 e áreas do código), login JWT, `/me` | Isabel |
| 13–14/11 | `LLMClient` (Ollama + mock, timeout, semáforo, tokens) com testes | Marcelo |
| 15–16/11 | KAN-60: conversas e mensagens chamando agente e ferramentas (mock, depois modelo real) | Marcelo |
| 16–17/11 | Gravar mensagens, rastro, execuções e uso do modelo; dados sintéticos no banco se der | Isabel |
| 18/11 | Demo ponta a ponta com a interface, back-end no Docker, README, medir RAM | os dois |

## Sprint 3 (até 10/12)
SSE por passo, CRUD de agentes com `agente_historico`, limite de gasto (aviso em 80%, aprovação do gestor), confirmação de ferramentas de escrita, auditoria, `eventos_erro` e alertas para a QA, mascaramento, Alembic se necessário, teste no Raspberry Pi.

## Convenções
- Python 3.11+ (CI usa 3.11), rotas síncronas, pytest, ruff.
- Português nos nomes de domínio, inglês para infraestrutura.
- PRs pequenos, template do repositório (o que mudou + card do Jira), revisão do QA. Não aprovar código gerado por IA que não se entende.

## Em aberto
- Níveis e áreas oficiais (Brenno, KAN-62).
- Regra de acesso ao agente e limite de gasto (Milene, Brenno).
- Ajustes no `agente.py` (Christopher): `PERGUNTAR` sem `input()`, ferramentas e histórico por parâmetro.
- Eventos que a QA quer receber (Enrico).
- Branch `misabelalbponte-crypto-patch-2` (Isabel): alinhar com a estrutura acima.
