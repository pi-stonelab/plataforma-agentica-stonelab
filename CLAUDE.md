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
| 4 Ferramentas e Integrações | Pedro Henrique | `ferramentas/` (catálogo, classe `Ferramenta`, executor e fachada do mock) e `mock/` (a Stone simulada, banco sintético) |
| 5 Back-end e Dados | Marcelo, Isabel | `backend/` (existe o esqueleto com `/health`; login, tabelas e rotas a fazer) |
| 6 Segurança e Permissões | Brenno | `seguranca/` (PR #10) — perfis, acesso ao agente, guardrails e auditoria (KAN-62) |
| 7 QA | Enrico | Testes, alertas, revisão de PR |

## Princípio central (arquitetura KAN-31)
**O back-end é o único caminho** entre interface, agente, ferramentas e modelo.
**O back-end executa as ferramentas; o agente só as pede.** (Na prática, o runtime do agente chama `catalogo.executar` dentro do mesmo processo. O back-end entrega o `Usuario` e a lista de ferramentas e liga o registro. Veja "Como as quatro pastas se encaixam".)

```
Interface ──REST──► API e login ─► Permissões ─► Orquestrador ─► Registro
                                                     │
                                  Executor ◄─ Runtime do agente ─► LLMClient ─► Cloudflare Access ─► Ollama (Qwen3)
                                     │
                                Ferramentas            A plataforma usa o PostgreSQL; o mock tem banco próprio
```

| Peça | Quem faz | Situação |
| --- | --- | --- |
| API e login, Permissões, Orquestrador, Registro, LLMClient | Back-end | a fazer |
| Runtime do agente | Frente 3 | **existe**: `agentes/agente_atendimento/agente.py` (motor) e `agentes/agente_geral/` |
| Executor | Frente 4 | **existe**: `ferramentas/catalogo.py` + `ferramentas/base.py` |
| Ferramentas (mocks) | Frente 4 | **existe**: 43 ferramentas em 8 áreas, 11 ativas, lendo o banco de `mock/` |

## O que já existe e como o back-end se liga
- **`catalogo.executar(nome, args, usuario, ferramentas_do_agente, contexto)`**: confere se a ferramenta é do agente, depois `Ferramenta.executar()` confere nível, área e categoria de dado do cargo (**segunda checagem de permissão**), valida parâmetros, mascara a saída, grava o registro e devolve `{status, dados, mensagem, tipo_erro}`. **Não reescrever.**
- **`catalogo.ler(caminho, usuario, ferramentas_do_agente)`**: texto que o agente lê (índice, que já lista as ferramentas liberadas; área; ficha da ferramenta), já filtrado por permissão.
- **`governanca.adicionar_destino(funcao)`**: recebe cada registro de chamada (só metadados). O back-end liga aqui a gravação em `execucoes_ferramenta`. Se algum destino falhar, a ferramenta não responde (falha fechada, O9).
- **`governanca.Usuario(id_usuario, nivel, area, carteiras, cargo)`**: o back-end monta este objeto por `governanca.usuario_do_cargo(id_usuario, cargo, carteiras)`, com cargo e carteiras do diretório do mock, e entrega ao agente. Nunca com dado da requisição.
- **`dados_sinteticos.py`**: fachada do banco do mock (`buscar_funcionario`, `buscar_cliente`, `buscar_transacoes`, `buscar_liquidacoes`, `buscar_chamados`...). Lê por `mock/consultas.py`. Os dados vivem no banco de `mock/` (`MOCK_DATABASE_URL`), não nas tabelas da plataforma.
- **`rodar_turno(pergunta, usuario, ferramentas_do_agente, chamar_modelo, historico, estado, contexto, prompt_sistema)`**: um turno, de até `MAX_PASSOS = 10` passos e 120 s, protocolo em texto `LER / USAR / PERGUNTAR / FINAL`. Devolve um `Turno(resposta, tipo, trajetoria, estado, motivo)`. A `trajetoria` é o **rastro** pedido na KAN-60. O `LLMClient` entra pelo parâmetro `chamar_modelo(prompt_sistema, prompt)`. O `agente(...)` antigo, que devolve `(resposta, trajetoria)`, ficou para testes e terminal. Detalhes em `agentes/CLAUDE.md`.

### Ajustes pedidos às outras frentes (situação atual)
- **Frente 3 (agente), feitos:** (a) `PERGUNTAR` devolve a pergunta e encerra o turno, sem `input()`; (b) lista de ferramentas e histórico entram por parâmetro; (c) `BASE_URL` e `MODELO` saíram do motor (o terminal lê `LLM_URL` e `LLM_MODELO` do `.env`); (d) `print` virou log sem conteúdo.
- **Frente 6 (Brenno), feitos:** (a) gancho de auditoria: `Plataforma(ao_registrar=funcao)`; (b) correspondência entre perfis e níveis de ferramenta: o nível vem do cargo (seção abaixo).
- **Frente 7:** testes do back-end ficam no repositório (`backend/tests/`). O CI de hoje (`.github/workflows/ci.yml`) só roda gitleaks e ruff; ainda não roda pytest.

## Modelo de acesso: duas camadas
Perfil do usuário **vem do token JWT + banco**, nunca do corpo da requisição nem do prompt.

### Camada 1: acesso ao agente (`seguranca/`, Brenno, PR #10 ainda em revisão)
| Perfil | Nível | Agentes |
| --- | --- | --- |
| `AdminGlobal` | 1 | opera sem ver conteúdo: pausa (deprecar) qualquer agente e vê só os não privados; nunca executa, edita nem convida |
| `Supervisor` | 2 | gerencia e executa os não privados da(s) sua(s) área(s) (`areas_extras`); fora delas, só usa o que está aberto ou foi convidado; não vê privado de outra pessoa |
| `Colaborador` | 3 | os que criou (controle total); usa os públicos e aqueles para os quais foi convidado |
| `Auditor` | 0 | nenhum; só lê a auditoria |
| `GestorDeAcessos` | 0 | nenhum; só atribui e remove perfis, nunca o próprio |
- Áreas: `Financeiro` (`financeiro`) e `AtendimentoCliente` (`atendimento`). Ações: `VER`, `EXECUTAR`, `EDITAR`, `CONVIDAR`, `DEPRECAR`. `REPLICAR` é Sprint 3. O inteiro `nivel` não é lido por nada e tem ordem invertida em relação a N1/N2; não o compare com a camada 2.
- **Visibilidade** (o dono escolhe, publicar não exige aprovação): `PRIVADO` (padrão), `CONVIDADOS` ou `PUBLICO` (todos os funcionários das duas áreas). Convidar só vale em `CONVIDADOS`. A tabela completa está em `seguranca/README.md`.
- Uso: `@exige_permissao(Acao.EXECUTAR)` em funções com parâmetros `usuario` e `agente` (e `plataforma` e `execucao_id`, se a função os declara). Negado → `AcessoNegado` (responder 403 genérico).
- A `Plataforma` guarda cadastro e auditoria **em memória, de UM pedido**. O banco é a fonte: a cada pedido o back-end cria uma `Plataforma(ao_registrar=gravar_evento)` nova, cadastra a pessoa com o perfil lido naquele momento, carrega os agentes do banco com `carregar_agente` e descarta tudo no fim. Não use a global `PLATAFORMA` (é só da demo) e não reaproveite uma `Plataforma` entre pedidos. A auditoria vai para a tabela `auditoria` pelo gancho `ao_registrar`.
- O agente geral nasce com `Agente.da_plataforma(nome)`: sem área, dono `plataforma`, público. Veja `seguranca/CLAUDE.md`.

### Camada 2: acesso à ferramenta (`ferramentas/governanca.py`, Pedro)
- Quem decide é o **cargo** (10 cargos em `mock/regras.py`). O cargo dá a área (`atendimento` ou `financeiro`), o nível de ferramenta (**`N1`** ou **`N2`**, N2 é o maior), o escopo de lojistas (carteiras do time, todas ou nenhum), a janela de dias (90 para `atendente_n1`) e as categorias de dado permitidas.
- **Carteiras** são nomes (`varejo`, `pme`, `contas_chave`), tiradas do time do funcionário no diretório do mock. O lojista é identificado por `M00001`. Quem só vê a carteira do time (`atendente_n1`, `especialista_n2`) recebe `permissao_negada` para lojista de fora, com a mesma resposta para lojista que não existe. N2 não vê qualquer cliente.
- Ferramenta: `nivel_minimo` + `areas_permitidas` (`"todas"` libera todas) + `categorias_dados`, que o cargo precisa ter. Só existem as áreas `atendimento` e `financeiro` (`dados` e `tecnologia` saíram, D4).

### Correspondência entre as camadas (decidida: D8, O1)
O back-end monta, para a mesma pessoa, um `seguranca.Usuario` e, se o perfil usa ferramentas, um `governanca.Usuario`. O nível N1/N2 vem do **cargo**, não do perfil: `atendente_n1` e `especialista_n2` são ambos `Colaborador` na camada 1, mas N1 e N2 na camada 2.
| Cargo (mock) | Perfil (camada 1) | Área | Nível | Escopo de lojistas |
| --- | --- | --- | --- | --- |
| `atendente_n1` | `Colaborador` | atendimento | N1 | carteiras do time, janela de 90 dias |
| `especialista_n2` | `Colaborador` | atendimento | N2 | carteiras do time |
| `supervisor_atendimento` | `Supervisor` | atendimento | N2 | todas |
| `analista_ouvidoria` | `Colaborador` | atendimento | N1 | todas |
| `analista_cobranca`, `analista_disputas`, `analista_recebiveis` | `Colaborador` | financeiro | N1 | todas |
| `coordenador_financeiro` | `Supervisor` | financeiro | N2 | todas |
| `auditor_compliance` | `Auditor` | nenhuma | nenhum | nenhum |
| `admin_plataforma` | `AdminGlobal` | nenhuma | nenhum | nenhum |
`GestorDeAcessos` não tem cargo no mock (SEM FONTE sobre qual cargo corresponde). Admin, Auditor e Gestor não usam ferramentas de dado (`usa_ferramentas = False`).

## Contrato de ferramenta (conforme `ferramentas/base.py`)
Ficha (atributos de classe): `nome`, `area`, `acesso` (`leitura` / `escrita` / `calculo`), `integracoes`, `nivel_minimo`, `areas_permitidas`, `categorias_dados`, `sensibilidade` (`publica` / `interna` / `pessoal` / `sigilosa`), `conteudo_terceiros`, `status` (`ativa` / `inativa` / `planejada`), `parametros` (tipos `texto`, `inteiro`, `decimal`, `data`). Descrição para o modelo fica no `agents.md` de cada ferramenta.
Retorno: `{status, dados, mensagem, tipo_erro}`. Tipos de erro: `parametro_invalido`, `permissao_negada`, `nao_encontrado`, `ferramenta_inexistente`, `ferramenta_inativa`, `integracao_indisponivel`, `erro_interno`.
Ferramentas de escrita ficam inativas até existir confirmação em duas etapas (exceção: `solicitar_ferramenta_ausente`). Ativas hoje (11): `consultar_cliente`, `consultar_transacoes_cliente`, `calcular_multa_atraso`, `consultar_endereco_cep`, `solicitar_ferramenta_ausente`, `consultar_liquidacoes_cliente`, `listar_chamados_cliente`, `consultar_historico_contato`, `listar_faturas_em_atraso`, `calcular_parcelas` e `consultar_contatos_lojista`. As ferramentas não vão para o banco (D10).

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
| `usuarios` | id, nome, email, senha_hash, perfil (AdminGlobal/Supervisor/Colaborador/GestorDeAcessos), area, areas_extras (JSONB), carteira (JSONB) |
| `agentes` | id, nome, objetivo, area (vazia no agente geral), dono_id, visibilidade (privado/convidados/publico), ferramentas (JSONB, só os nomes), ativo |
| `agente_convidados` | agente, usuario |
| `auditoria` | quando, id_usuario, acao, alvo, permitido, execucao_id (eventos da `Plataforma`; só o id, nunca o nome) |
| `conversas` | id, usuario, agente, criada_em |
| `mensagens` | conversa, autor (usuario/agente), texto, tipo (final/pergunta), trajetoria (JSONB), criada_em |
| `execucoes_ferramenta` | campos de `governanca.CAMPOS_REGISTRO` (nunca argumentos nem dados) |
| `uso_modelo` | usuario, conversa, tokens de entrada e saída, latência, custo simulado |
| `clientes`, `transacoes` | **não criar**: os dados sintéticos moram no banco de `mock/` (10 tabelas próprias, `MOCK_DATABASE_URL`), criado por `python -m mock.gerar` |

Nota: cargo e carteiras do funcionário vêm do diretório do mock (`buscar_funcionario`). Se `usuarios` guardar cópia, as duas fontes podem divergir. Decidir com Isabel (SEM FONTE). Nome e e-mail reais de colega só se forem necessários (LGPD, mínimo de dados).

Sprint 3: `agente_historico`, `eventos_erro`, limite de gasto.

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
2. API valida o token e busca o usuário no banco → monta `seguranca.Usuario` (camada 1) e `governanca.Usuario` (camada 2).
3. Permissões conferem acesso ao agente com `@exige_permissao(Acao.EXECUTAR)` numa `Plataforma` criada para este pedido (primeira checagem). Negado → 403.
4. Orquestrador carrega o agente (ferramentas permitidas), o histórico e o estado da conversa, e chama `rodar_turno(...)` com `chamar_modelo = LLMClient`.
5. O agente lê/usa ferramentas pelo catálogo, que reconfere permissão (segunda checagem) e o lojista (carteira, janela). Máximo de 10 passos e 120 s por turno.
6. Back-end grava mensagem, rastro, execuções e uso do modelo e responde.

## Como as quatro pastas se encaixam
Quatro pastas de código, cada uma com a sua pergunta. O `CLAUDE.md` de cada pasta tem o detalhe.

- `mock/` é a Stone simulada: um banco de dados inventado (20 lojistas, 15 funcionários, cenários 1, 3, 5 e 7), com o "hoje" fixo em 15/10/2026 e regras por cargo. Não importa nenhuma outra pasta.
- `ferramentas/` lê o `mock/` e responde: este cargo pode usar esta ferramenta? Este lojista é da carteira dele? O que precisa sair mascarado? Importa `mock/` (`regras`, `consultas`, `banco`).
- `seguranca/` responde: esta pessoa pode usar este agente? Não importa nenhuma outra pasta.
- `agentes/` roda um turno de conversa e pede ferramentas ao catálogo. Importa só `ferramentas/` (o motor usa `catalogo`; o terminal usa `governanca` e `dados_sinteticos`). Não importa `mock/` (tem teste) nem `seguranca/`.
- `backend/` é o único lugar que importa as quatro e liga uma à outra: login, `Plataforma` por pedido, orquestrador, registro e rotas. Hoje só existe o esqueleto.

As quatro portas de um pedido, na ordem:
1. Quem é você? Token, linha no banco, funcionário `ativo` no diretório. É do back-end.
2. Você pode usar este agente? `seguranca/`.
3. Você pode usar esta ferramenta? `ferramentas/catalogo.py` e `governanca.motivo_bloqueio` (cargo, área, categoria de dado).
4. Este lojista é seu? `ferramentas/lojista.py` (carteira e janela de dias) e a máscara em `Ferramenta.executar`.

O que cada pasta guarda de um pedido: `seguranca/` grava um evento de acesso por decisão (id da pessoa, ação, id do agente, `execucao_id`); `ferramentas/` grava um registro por chamada (13 campos, sem conteúdo); `agentes/` devolve a `trajetoria` (ação e nome, sem argumentos). O `execucao_id` liga os três.

Vocabulário: `id_cliente` é o nome que o modelo vê para o código do lojista (`M00001`); `codigo` e `id_lojista` são os do banco. Perfil é da camada 1; cargo, nível (N1/N2) e área são da camada 2 e vêm do mock.

## O que a etapa do back-end precisa fazer
Lista tirada de `pesquisa/arquitetura.md`, das auditorias e de `agentes/CLAUDE.md`. Os nomes entre crases que ainda não existem (`montar_acesso`, `executar_agente`, `gravar_evento`) são do rascunho da arquitetura e podem mudar. Detalhes de cada ponto em `seguranca/CLAUDE.md` e `agentes/CLAUDE.md`.
1. **`montar_acesso` a cada pedido**, em `backend/app/permissoes.py`. Lê a linha de `usuarios` pelo `sub` do token, confere no diretório (`buscar_funcionario`) que a situação é `ativo` (desligado e afastado não entram) e devolve os dois objetos: o `seguranca.Usuario` e o `governanca.Usuario` (por `usuario_do_cargo`; `None` se o perfil não usa ferramentas). Perfil fora de `ROLES`, linha ausente ou inativa: 401 genérico. Banco fora: 503.
2. **`Plataforma` por pedido + `carregar_agente`.** Nova a cada pedido, com a pessoa cadastrada e os agentes lidos do banco. Nada de `PLATAFORMA` global nem de estado entre pedidos.
3. **Orquestrador decorado.** `@exige_permissao(Acao.EXECUTAR)` numa função de serviço (`backend/app/orquestrador.py`) que recebe `plataforma`, `usuario`, `agente` e `execucao_id`. A rota chama essa função; o decorator não vai na rota.
4. **Registro e gancho de auditoria.** `governanca.adicionar_destino(gravar_execucao)` uma vez no `lifespan`, e `Plataforma(ao_registrar=gravar_evento)` por pedido, cada um com sessão própria. Se a gravação falhar, levante erro (sem rastro, sem ação). O mesmo `execucao_id` vai para `contexto` das ferramentas e para o evento.
5. **`LLMClient` com `(prompt_sistema, prompt)`.** O motor chama `chamar_modelo(prompt_sistema, prompt)`. Envie o primeiro como `system`. Credenciais do Cloudflare só no back-end.
6. **`PARADA_DO_MODELO`.** Importe `PARADA_DO_MODELO` (`"Observação:"`) de `agentes.agente_atendimento.agente` e passe ao Ollama como `stop`. Sem isso o modelo inventa o resultado da ferramenta. Temperatura 0, `think` falso, tire os blocos `<think>`.
7. **`tempo_limite`.** Se o `LLMClient` declarar o parâmetro `tempo_limite` (segundos), o motor passa o tempo que sobra do turno (120 s por padrão, `contexto["segundos_por_turno"]` troca). Use como timeout da chamada. Falha do modelo: levante `ModeloIndisponivel` com mensagem genérica, sem a URL.
8. **Estado no servidor.** Guarde por conversa o `historico` (pares pergunta e resposta) e o `Turno.estado` do último turno de tipo `pergunta`. Nunca aceite `estado` vindo do cliente.
9. **Motivos de `Turno`.** `tipo` é `final`, `pergunta` ou `limite`. No `limite`, `motivo` é `max_passos`, `repeticao`, `tempo` ou `modelo_indisponivel`. Guarde o `tipo` em `mensagens` (a tabela do plano só prevê `final` e `pergunta`) e a `trajetoria` como rastro.
10. **`MOCK_DATABASE_URL`.** Declare no `.env`, diferente de `DATABASE_URL`, e rode `python -m mock.gerar` antes. O `create_all` do back-end não cria as tabelas do mock. Os testes usam `criar_engine("sqlite://")`.
11. **Tratador de `AcessoNegado`.** `@app.exception_handler(AcessoNegado)` responde 403 com mensagem fixa, sem nome de pessoa nem de agente.
12. **JWT sem perfil.** O token leva só `sub` (id neutro) e `exp` curto. Perfil, área, nível e carteira nunca viram claim.

Também do rascunho da arquitetura: `StaticPool` e `check_same_thread=False` no engine de SQLite em memória (`db.py`), senão outra thread vê banco vazio nos testes; `catalogo.carregar()` no `lifespan`; PyJWT e bcrypt estão no `requirements.txt` da raiz, mas não no de `backend/`; filtrar a conversa pelo id da pessoa do token na própria consulta (outra pessoa recebe 404); não expor `governanca.REGISTROS`; limpar `governanca.DESTINOS` entre testes.

## Segurança (regras duras)
- **Nunca** commitar `.env`, credenciais ou segredos do Cloudflare. Manter `.env.example` sem valores.
- Nunca colocar credenciais em docs, Jira, slides ou logs.
- Credenciais do modelo só no back-end; interface e agente nunca as veem.
- Permissão conferida em quatro portas: login, acesso ao agente, acesso à ferramenta e lojista no escopo. Tudo roda com as permissões de quem usa o agente.
- Escrita: o agente propõe, a pessoa confirma, só então executa (Sprint 3).
- Conteúdo de ferramentas com `conteudo_terceiros` é dado, nunca instrução.
- CPF, telefone, e-mail, conta e cartão são mascarados na saída da ferramenta, antes de chegar ao modelo (`ferramentas/mascara.py`, O2). Ver o dado completo (motivo escrito, chamado ligado e auditoria) fica para a Sprint 3.

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
    permissoes.py    # monta os dois Usuario e usa seguranca.exige_permissao
    llm_client.py    # Ollama + mock
    orquestrador.py  # chama o agente
    registro.py      # destino do governanca, gancho de auditoria da Plataforma e uso_modelo
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
| 13/11 | `usuarios`, seed (um usuário por perfil, nas duas áreas), login JWT, `/me` | Isabel |
| 13–14/11 | `LLMClient` (Ollama + mock, timeout, semáforo, tokens) com testes | Marcelo |
| 15–16/11 | KAN-60: conversas e mensagens chamando agente e ferramentas (mock, depois modelo real) | Marcelo |
| 16–17/11 | Gravar mensagens, rastro, execuções e uso do modelo; dados sintéticos no banco se der | Isabel |
| 18/11 | Demo ponta a ponta com a interface, back-end no Docker, README, medir RAM | os dois |

## Sprint 3 (até 10/12)
SSE por passo, CRUD de agentes com `agente_historico` e convites, rotas do `GestorDeAcessos` (atribuir e remover perfis), limite de gasto (aviso em 80%, aprovação do gestor), confirmação de ferramentas de escrita, `eventos_erro` e alertas para a QA, ver dado restrito completo (motivo, chamado e auditoria), REPLICAR agente, Alembic se necessário, teste no Raspberry Pi.

## Convenções
- Python 3.11+ (CI usa 3.11), rotas síncronas, pytest, ruff.
- Português nos nomes de domínio, inglês para infraestrutura.
- PRs pequenos, template do repositório (o que mudou + card do Jira), revisão do QA. Não aprovar código gerado por IA que não se entende.

## Em aberto
- Decisões e perguntas do Pedro e do grupo estão em `docs/decisoes.md` (inclui as divergências com a KAN-69).
- Aprovação do PR #10 (`seguranca/`).
- Gravar a auditoria no banco pelo gancho `ao_registrar` e ler a tabela para o Auditor (back-end).
- Limite de gasto por pessoa (Milene).
- Lista de ferramentas do agente de atendimento (KAN-55): hoje fixa em 5, sem as 6 novas.
- Eventos que a QA quer receber (Enrico).
- Branch `misabelalbponte-crypto-patch-2` (Isabel): alinhar com a estrutura acima.
