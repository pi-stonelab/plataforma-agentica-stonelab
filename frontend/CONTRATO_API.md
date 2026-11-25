# Contrato da API: o que o back-end precisa entregar para a interface

Este documento é **tudo o que o back-end precisa saber** para a interface funcionar.
Não é preciso abrir nenhum arquivo `.js` do front: cada rota, campo, código de erro e regra de permissão está aqui.

- **Seção 1**: lista de todas as rotas, em uma tabela.
- **Seção 2**: convenções que valem para todas (login, erros, datas, dinheiro).
- **Seção 3**: como ligar o front ao back-end e testar.
- **Seção 4**: os objetos que se repetem (Agente, Mensagem, Passo...), definidos uma vez só.
- **Seções 5 e 6**: cada rota em detalhe (Sprint 2, depois Sprint 3).
- **Seção 7**: dados de seed para a demo bater com o roteiro.
- **Seção 8**: o que ainda precisa ser combinado com as outras frentes.

> **Regra:** se o back-end precisar mudar um formato, mude **este arquivo e `frontend/js/api.js` no mesmo PR**.
> `api.js` é o único arquivo do front que chama o back-end (uma função por rota).

---

## 1. Todas as rotas

| # | Método e caminho | Sprint | Quem pode | Tela que usa |
| --- | --- | --- | --- | --- |
| 1 | `GET /health` | 2 | qualquer um, sem token | (diagnóstico) |
| 2 | `POST /auth/login` | 2 | qualquer um, sem token | Login |
| 3 | `GET /me` | 2 | logado | todas (barra lateral, faixa de gasto) |
| 4 | `GET /agentes` | 2 | logado | Painel, Chat |
| 5 | `GET /agentes/{id}` | 2 | quem pode `VER` o agente | Chat |
| 6 | `GET /conversas` | 2 | logado (só as próprias) | Painel, Chat |
| 7 | `POST /conversas` | 2 | quem pode `EXECUTAR` o agente | Chat |
| 8 | `GET /conversas/{id}` | 2 | dono da conversa | Chat |
| 9 | `POST /conversas/{id}/mensagens` | 2 (SSE na 3) | dono da conversa + `EXECUTAR` | Chat |
| 10 | `POST /conversas/{id}/confirmacoes/{confirmacao_id}` | 3 | dono da conversa + `EXECUTAR` | Chat |
| 11 | `GET /ferramentas` | 3 | todos menos `GestorDeAcessos` | Criação guiada |
| 12 | `POST /rascunhos` | 3 | todos menos `GestorDeAcessos` | Criação guiada |
| 13 | `GET /rascunhos/{id}` | 3 | dono do rascunho | Criação guiada |
| 14 | `POST /rascunhos/{id}/respostas` | 3 | dono do rascunho | Criação guiada |
| 15 | `POST /rascunhos/{id}/ajustes` | 3 | dono do rascunho | Criação guiada |
| 16 | `PATCH /rascunhos/{id}` | 3 | dono do rascunho | Criação guiada |
| 17 | `POST /rascunhos/{id}/simulacao` | 3 | dono do rascunho | Criação guiada |
| 18 | `POST /rascunhos/{id}/aprovar` | 3 | dono do rascunho | Criação guiada |
| 19 | `GET /monitoramento/resumo?dias=` | 3 | todos menos `GestorDeAcessos` | Monitoramento |
| 20 | `GET /monitoramento/uso-diario?dias=` | 3 | todos menos `GestorDeAcessos` | Monitoramento |
| 21 | `GET /monitoramento/agentes?dias=` | 3 | todos menos `GestorDeAcessos` | Monitoramento |
| 22 | `GET /monitoramento/alertas` | 3 | todos menos `GestorDeAcessos` | Monitoramento, Painel |

**Com as rotas 1 a 9, Login, Painel e Chat funcionam com o back-end real (demo da Sprint 2).**
As telas de Criação guiada e Monitoramento mostram uma mensagem de erro enquanto as rotas delas não existirem.
O Painel tolera a falta de `/monitoramento/alertas`: sem ela, mostra "0 alertas".

---

## 2. Convenções (valem para todas as rotas)

| Item | Regra |
| --- | --- |
| Formato | JSON. O front envia `Content-Type: application/json` e `Accept: application/json` |
| Login | `Authorization: Bearer <token>` em todas as rotas, menos `/health` e `/auth/login` |
| Quem é a pessoa | **Sempre do token + banco.** O front nunca envia perfil, área, nível nem carteira, e o back-end não deve aceitar esses campos no corpo |
| Datas e horas | ISO 8601 com fuso: `2026-11-12T14:03:00-03:00` (o `Z` de UTC também serve) |
| Dias | `YYYY-MM-DD` no fuso de Brasília (o "hoje" do gráfico tem que bater com o relógio da pessoa) |
| Dinheiro | `number` em reais, duas casas (`16.42`). O preço por token é **simulado** (o modelo é local) |
| Frações | `number` entre 0 e 1 (`0.089` = 8,9%) |
| IDs | `string`, sem formato obrigatório. O seed sugerido usa prefixos (`u-`, `ag-`, `cv-`, `m-`, `rs-`, `cf-`, `al-`) só para facilitar a leitura |
| Texto | Todo texto devolvido é **texto puro**. O front nunca interpreta HTML nem Markdown. Quebras de linha (`\n`) aparecem como quebras |
| Idioma | Mensagens de erro em português: o front as mostra **direto para a pessoa** |

### Erros
Use o padrão do FastAPI (`HTTPException`). O front aceita as três formas:

```json
{ "detail": "Agente não encontrado." }
{ "detail": { "codigo": "limite_atingido", "mensagem": "Você atingiu o limite de gasto do mês." } }
{ "detail": [ { "loc": ["body", "texto"], "msg": "...", "type": "..." } ] }
```
A terceira é a que o pydantic gera sozinho no 422: o front junta os `msg`.
Use a segunda quando o front precisar reagir a um caso específico (hoje só `limite_atingido`).

| Código | Quando usar | O que o front faz |
| --- | --- | --- |
| `401` | Token ausente, inválido ou expirado. No login: e-mail ou senha errados | Volta para a tela de login (no login, só mostra a mensagem) |
| `403` | Logado, mas sem permissão (ex.: `AcessoNegado` do `seguranca`) | Mostra a mensagem |
| `404` | Não existe **ou a pessoa não pode ver**. Agente ou conversa de outra pessoa responde `404`, não `403`, para não revelar que existe | Mostra a mensagem |
| `409` | Conflito de estado (confirmação já decidida, ajustar rascunho sem ficha) | Mostra a mensagem |
| `422` | Validação (campo faltando, texto vazio ou longo demais) | Mostra a mensagem |
| `402` | Limite de gasto do mês atingido (Sprint 3), com `codigo: "limite_atingido"` | Mostra a mensagem |
| `504` | O modelo não respondeu a tempo | Mostra a mensagem e mantém o texto digitado |
| `500` | Erro inesperado. **Nunca** devolva stack trace nem dados internos | Mostra "Erro interno no servidor." |

Sem `detail`, o front usa uma mensagem padrão por código.
Se o back-end estiver fora do ar, o front mostra "Não foi possível falar com o back-end. Ele está rodando?".

---

## 3. Como ligar o front ao back-end

O front tem um **modo mock** (padrão) que simula todas as rotas dentro do navegador.
Para usar o back-end real, abra o front com `?mock=0`. A escolha fica guardada no navegador; `?mock=1` volta para o mock.

Escolham uma das duas opções:

**Opção A: mesma origem (recomendada para a demo, dispensa CORS).** O FastAPI serve a pasta `frontend/`:
```python
# backend/app/main.py, DEPOIS de incluir as rotas
from pathlib import Path
from fastapi.staticfiles import StaticFiles

PASTA_FRONT = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/app", StaticFiles(directory=PASTA_FRONT, html=True), name="frontend")
```
Abrir `http://localhost:8000/app/?mock=0`.

**Opção B: origens separadas.** Front com `python -m http.server 5500` (dentro de `frontend/`) e back-end em `:8000`.
Abrir `http://localhost:5500/?mock=0&api=http://localhost:8000`. O back-end precisa de CORS:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
```

**Testar uma rota sem o front:** a página `/docs` do FastAPI, ou `curl`:
```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"carla@stonelab.test","senha":"stone123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s localhost:8000/agentes -H "Authorization: Bearer $TOKEN"
```

**Comparar com o mock:** abra o front em modo mock, aperte F12 → aba Console e rode
`(await import("./js/api.js")).api.agentes()`. Sai exatamente o JSON que o front espera daquela rota.

---

## 4. Objetos que se repetem

Na coluna "Obrig.", **sim** = o front quebra ou mostra errado sem o campo; **não** = opcional (pode faltar ou ser `null`).

### 4.1 `Usuario` (resposta de `GET /me`)
```json
{
  "id": "u-carla",
  "nome": "Carla Souza",
  "email": "carla@stonelab.test",
  "perfil": "Colaborador",
  "area": "AtendimentoCliente",
  "areas_extras": [],
  "carteira": ["CLI-0001", "CLI-0002", "CLI-0003"],
  "uso_mes": { "gasto": 16.42, "limite": 20.0 }
}
```
| Campo | Tipo | Obrig. | Observação |
| --- | --- | --- | --- |
| `id`, `nome`, `email` | string | sim | `nome` aparece na barra lateral; as iniciais viram o avatar |
| `perfil` | `"AdminGlobal"` \| `"Supervisor"` \| `"Colaborador"` \| `"GestorDeAcessos"` \| `"Auditor"` | sim | Nomes das classes de `seguranca/`. Define o menu: o `GestorDeAcessos` não vê Chat, Criação nem Monitoramento. O back-end real também devolve `"Auditor"` (cargo `auditor_compliance`), que não usa agentes nem ferramentas |
| `area` | `"Financeiro"` \| `"AtendimentoCliente"` \| `null` | sim | No back-end real vem do cargo do mock: `null` para `AdminGlobal` e `Auditor`, que não têm área |
| `areas_extras` | string[] | não | Áreas extras do Supervisor |
| `carteira` | string[] | não | No back-end real, os **nomes das carteiras** do time do funcionário (ex.: `["varejo"]`); lista vazia para quem vê todos os lojistas ou nenhum. O front só exibe; quem barra é o executor |
| `uso_mes` | `{gasto: number, limite: number}` | não | Soma do `uso_modelo` do mês + limite do perfil. **Sem ele somem o medidor do Painel e a faixa de aviso.** A faixa aparece em `gasto/limite >= 0.8` |

### 4.2 `Agente` (itens de `GET /agentes`, `GET /agentes/{id}`, resposta de aprovar rascunho)
```json
{
  "id": "ag-atendimento",
  "nome": "Assistente de Atendimento",
  "objetivo": "Tira dúvidas sobre clientes, transações, multas e endereços durante o atendimento.",
  "area": "AtendimentoCliente",
  "dono": { "id": "u-bruno", "nome": "Bruno Martins" },
  "ferramentas": ["consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso"],
  "ativo": true,
  "criado_em": "2026-10-28T14:00:00-03:00",
  "relacao": "convidado",
  "acoes": ["VER", "EXECUTAR"]
}
```
| Campo | Tipo | Obrig. | Observação |
| --- | --- | --- | --- |
| `id`, `nome`, `objetivo`, `area` | string | sim | |
| `dono` | `{id, nome}` | sim | |
| `ferramentas` | string[] | sim | Nomes do catálogo (`ferramentas/`) |
| `ativo` | boolean | sim | `false` = deprecado: o cartão fica cinza e só permite consultar |
| `criado_em` | data-hora | sim | |
| `relacao` | `"dono"` \| `"admin"` \| `"supervisor"` \| `"convidado"` | sim | Selo do cartão. Regra: dono se `agente.dono == usuario.id`; senão admin se `AdminGlobal`; senão supervisor se `Supervisor` e o agente é da área (ou `areas_extras`) dele; senão convidado |
| `acoes` | string[] | sim | Cada `Acao` (`VER`, `EXECUTAR`, `EDITAR`, `CONVIDAR`, `DEPRECAR`) para a qual `usuario.pode(acao, agente)` é verdade. **O botão "Conversar" só aparece com `EXECUTAR`.** Agente desativado só tem `VER` |

### 4.3 `ResumoConversa` (itens de `GET /conversas`)
```json
{
  "id": "cv-123",
  "agente": { "id": "ag-atendimento", "nome": "Assistente de Atendimento" },
  "titulo": "Qual a situação do cliente CLI-0002?",
  "criada_em": "2026-11-12T10:00:00-03:00",
  "atualizada_em": "2026-11-12T10:01:09-03:00"
}
```
- `titulo`: primeiros 60 caracteres da primeira mensagem da pessoa. `null` enquanto a conversa está vazia (o front mostra "Nova conversa").
- `atualizada_em`: hora da última mensagem (igual a `criada_em` se estiver vazia). A lista sai **da mais recente para a mais antiga** por este campo.

### 4.4 `Conversa` (resposta de `GET /conversas/{id}` e `POST /conversas`)
```json
{
  "id": "cv-123",
  "agente": {
    "id": "ag-atendimento",
    "nome": "Assistente de Atendimento",
    "objetivo": "Tira dúvidas sobre clientes...",
    "ferramentas": ["consultar_cliente", "calcular_multa_atraso"],
    "ativo": true,
    "pode_executar": true
  },
  "criada_em": "2026-11-12T10:00:00-03:00",
  "mensagens": [ /* MensagemUsuario e MensagemAgente, da mais antiga para a mais nova */ ]
}
```
- `agente.pode_executar` = `usuario.pode(Acao.EXECUTAR, agente)` **agora**. Com `false` (convite removido, agente desativado), a caixa de texto fica desligada mas o histórico continua visível.
- `agente.ferramentas` vira sugestões de pergunta na conversa vazia.

### 4.5 `MensagemUsuario` e `MensagemAgente` (itens de `Conversa.mensagens`)
```json
{ "id": "m-1", "autor": "usuario", "texto": "Qual a situação do cliente CLI-0002?", "criada_em": "2026-11-12T10:00:00-03:00" }
```
```json
{
  "id": "m-2",
  "autor": "agente",
  "texto": "Mercearia Horizonte (CLI-0002), varejo, Rio de Janeiro/RJ. Cliente ativo...",
  "tipo": "final",
  "trajetoria": [ /* Passo */ ],
  "uso": { /* Uso */ },
  "confirmacao": null,
  "criada_em": "2026-11-12T10:00:09-03:00"
}
```
| Campo | Tipo | Obrig. | Observação |
| --- | --- | --- | --- |
| `autor` | `"usuario"` \| `"agente"` | sim | |
| `texto` | string | sim | Texto puro |
| `tipo` | ver abaixo | só no agente | Ausente ou `null` é tratado como `"final"` |
| `trajetoria` | `Passo[]` | não | Lista vazia ou ausente esconde o "Como cheguei nessa resposta" |
| `uso` | `Uso` | não | Mostrado em letra pequena embaixo da mensagem |
| `confirmacao` | `Confirmacao` \| null | não | Só quando `tipo` é `"confirmacao"` (Sprint 3) |

Valores de `tipo`:
| `tipo` | Quando | Como aparece |
| --- | --- | --- |
| `final` | O agente respondeu (`FINAL`) | Balão normal |
| `pergunta` | O agente usou `PERGUNTAR`. **O turno termina aqui.** A próxima mensagem da pessoa é a resposta | Etiqueta "O agente precisa de uma informação" |
| `bloqueio` (Sprint 3) | Barrado pelas travas da Frente 6 (injeção de instrução, troca de conta bancária) | Balão vermelho com escudo |
| `confirmacao` (Sprint 3) | Ferramenta de escrita aguardando a pessoa | Cartão com os campos e os botões Confirmar / Cancelar |

### 4.6 `RespostaAgente` (resposta de `POST /conversas/{id}/mensagens` e da confirmação)
É a mensagem do agente recém-criada, mas com o texto no campo **`resposta`** em vez de `texto`:
```json
{
  "id": "m-9",
  "resposta": "Para uma fatura de R$ 1.250,00 com 15 dias de atraso:\n• Multa (2%): R$ 25,00\n• Juros (1% ao mês): R$ 6,25\n• Total: R$ 1.281,25",
  "tipo": "final",
  "trajetoria": [ /* Passo */ ],
  "uso": { /* Uso */ },
  "confirmacao": null,
  "criada_em": "2026-11-12T21:06:00-03:00"
}
```
Depois, em `GET /conversas/{id}`, essa mesma mensagem volta como `MensagemAgente` (com `autor: "agente"` e `texto`).

### 4.7 `Passo` (itens de `trajetoria`, o rastro da KAN-60)
Um objeto por passo do agente (no máximo 8):
```json
{
  "passo": 4,
  "acao": "USAR",
  "alvo": "calcular_multa_atraso",
  "resumo": "'calcular_multa_atraso' executada: sucesso",
  "status": "ok",
  "tipo_erro": null,
  "pensamento": "Vou conferir os parâmetros antes de usar."
}
```
| Campo | Tipo | Obrig. | Observação |
| --- | --- | --- | --- |
| `passo` | inteiro | sim | Começa em 1 |
| `acao` | `"LER"` \| `"USAR"` \| `"PERGUNTAR"` \| `"FINAL"` (Sprint 3: `"BLOQUEIO"` \| `"CONFIRMAR"`) | sim | |
| `alvo` | string | não | Caminho lido (`atendimento/consultar_cliente`) ou ferramenta usada. Vazio no índice e no `FINAL` |
| `resumo` | string | sim | Uma linha. **Nunca** coloque argumentos com dados de cliente nem o resultado da ferramenta aqui |
| `status` | `"ok"` \| `"erro"` \| `"bloqueado"` | sim | `bloqueado` (permissão negada ou trava) aparece em vermelho com cadeado |
| `tipo_erro` | string \| null | não | Os 7 tipos de `ferramentas/base.py` (`parametro_invalido`, `permissao_negada`, `nao_encontrado`, `ferramenta_inexistente`, `ferramenta_inativa`, `integracao_indisponivel`, `erro_interno`) ou `"guardrail"` para as travas da Frente 6 |
| `pensamento` | string | não | O texto de `PENSAMENTO:` do modelo |

**Compatibilidade com o que existe hoje:** o `agente.py` devolve strings no formato
`"Passo 4: USAR -> 'calcular_multa_atraso' executada: sucesso"`. O front também aceita isso
(ele extrai número, ação e resumo da string), então **a Sprint 2 pode sair com strings**.
Uma string com "permissao_negada", "bloqueado" ou "não liberado" vira `status: "bloqueado"`; uma com "erro", "inválid", "invalido" ou "indisponivel" vira `status: "erro"`.

### 4.8 `Uso` (custo de uma resposta)
```json
{ "chamadas_modelo": 5, "tokens_entrada": 7400, "tokens_saida": 410, "latencia_ms": 4300, "custo": 0.078 }
```
Todos inteiros, menos `custo` (reais, simulado). São os mesmos números gravados em `uso_modelo` (somados no turno).

### 4.9 `Confirmacao` (Sprint 3)
```json
{
  "id": "cf-77",
  "ferramenta": "enviar_email",
  "titulo": "Enviar e-mail",
  "campos": [
    { "rotulo": "Para", "valor": "time-financeiro@stonelab.test" },
    { "rotulo": "Assunto", "valor": "Resumo semanal de receita" },
    { "rotulo": "Mensagem", "valor": "Olá, time..." }
  ],
  "situacao": "pendente"
}
```
- `campos` é só para mostrar. **Os argumentos reais ficam guardados no back-end**, ligados ao `id`: o front nunca os reenvia.
- `situacao`: `"pendente"` \| `"aprovada"` \| `"cancelada"`. Depois da decisão, o back-end atualiza a mensagem original, para o histórico (`GET /conversas/{id}`) mostrar "Confirmado por você" ou "Cancelado" no lugar dos botões.

### 4.10 `Ferramenta` (itens de `GET /ferramentas` e de `Ficha.ferramentas`)
```json
{
  "nome": "consultar_transacoes_cliente",
  "area": "financeiro",
  "descricao": "Lista as transações mais recentes de um cliente, com filtro opcional por período.",
  "acesso": "leitura",
  "sensibilidade": "sigilosa",
  "status": "ativa",
  "integracoes": ["sql"],
  "liberada": true,
  "motivo": null
}
```
- Os campos vêm da ficha da ferramenta (`ferramentas/base.py`). `descricao` é a primeira frase útil do `agents.md` (sem os textos `[preencher...]`).
- `liberada` / `motivo` = `governanca.motivo_bloqueio(ferramenta, usuario_camada2)`. Com `liberada: false`, a ferramenta aparece desabilitada e o `motivo` é mostrado ao lado ("Nível insuficiente.", "Área não permitida.").
- `integracoes` é opcional dentro da `Ficha`.

---

## 5. Sprint 2: rotas da demo (KAN-60)

### 5.1 `GET /health`
Sem token. Saída `200`: `{ "status": "ok" }`.

### 5.2 `POST /auth/login`
Sem token.
```json
{ "email": "carla@stonelab.test", "senha": "stone123" }
```
Saída `200`: `{ "token": "eyJhbGciOi...", "tipo": "bearer" }`.
- O front guarda o token no `sessionStorage` (some ao fechar a aba) e logo depois chama `GET /me`.
- Compare o e-mail sem diferenciar maiúsculas e ignorando espaços nas pontas.
- Erro `401`: `{"detail": "E-mail ou senha inválidos."}`. **A mesma mensagem** para e-mail inexistente e senha errada.
- Validade do token: sugestão de 8 horas. Ao expirar, qualquer rota responde `401` e o front volta ao login.

### 5.3 `GET /me`
Saída `200`: um `Usuario` (4.1). Sem `uso_mes` na Sprint 2 está tudo bem.

### 5.4 `GET /agentes`
Saída `200`: `Agente[]` (4.2) com **todos os agentes que a pessoa pode `VER`**, incluindo os desativados.
- `AdminGlobal`: todos. `Supervisor`: os da(s) área(s) dele + onde foi convidado. `Colaborador`: os que criou + onde foi convidado. `GestorDeAcessos`: `[]`.
- Ordem: tanto faz (o front não reordena; sugestão: ativos primeiro, depois por nome).

### 5.5 `GET /agentes/{id}`
Saída `200`: um `Agente`. Erro `404` (`"Agente não encontrado."`) se não existe **ou** a pessoa não pode `VER`.

### 5.6 `GET /conversas`
Saída `200`: `ResumoConversa[]` (4.3), **só as da pessoa logada**, da mais recente para a mais antiga.

### 5.7 `POST /conversas`
```json
{ "agente_id": "ag-atendimento" }
```
Saída `201` (ou `200`): uma `Conversa` (4.4) com `mensagens: []`.
- **Primeira checagem de permissão:** `@exige_permissao(Acao.EXECUTAR)`.
- Erros: `404` se o agente não existe ou a pessoa não pode vê-lo; `403` se pode ver mas não executar
  (ex.: `"Este agente foi desativado e só pode ser consultado."`).

### 5.8 `GET /conversas/{id}`
Saída `200`: uma `Conversa` (4.4) com todas as mensagens, da mais antiga para a mais nova.
Erro `404` se a conversa não existe ou é de outra pessoa (inclusive para o admin: conversa é privada).

### 5.9 `POST /conversas/{id}/mensagens`
```json
{ "texto": "Calcule a multa de R$ 1.250,00 com 15 dias de atraso" }
```
Saída `200`: uma `RespostaAgente` (4.6).

O que o back-end faz, em ordem:
1. Confere se a conversa é da pessoa (`404`) e se ela ainda pode `EXECUTAR` o agente (`403`).
2. Valida `texto`: sem espaços nas pontas, de 1 a 2.000 caracteres (`422`: `"Escreva uma mensagem."` / `"Mensagem muito longa (máximo 2.000 caracteres)."`).
3. (Sprint 3) Confere o limite de gasto: `402` com `{"detail": {"codigo": "limite_atingido", "mensagem": "Você atingiu o limite de gasto do mês. Peça aprovação ao seu gestor para continuar."}}`. Sugestão: o `AdminGlobal` não tem limite.
4. Grava a mensagem da pessoa. Se a conversa não tem `titulo`, usa os primeiros 60 caracteres desse texto.
5. Monta os dois `Usuario` (camadas 1 e 2) e chama o agente com as ferramentas do agente **e o histórico da conversa**.
   Se a mensagem anterior do agente foi `tipo: "pergunta"`, esta mensagem é a resposta a ela.
6. Grava a resposta (`texto`, `tipo`, `trajetoria` em JSONB), as execuções (via `governanca.adicionar_destino`) e o `uso_modelo`.
7. Atualiza `atualizada_em` da conversa e responde.

Erros: `403`, `404`, `422`, `402` (Sprint 3), `504` (`"O modelo não respondeu. Tente de novo."`).
**Uma falha de ferramenta não é erro HTTP:** o agente responde normalmente (`200`) explicando o que deu errado,
e o passo aparece na `trajetoria` com `status: "erro"`.

**Tempo de resposta:** o front espera sem limite, mostrando "pensando". Com o Qwen remoto, uma resposta pode levar dezenas de segundos.
Coloque um timeout no `LLMClient` e devolva `504` se estourar.

---

## 6. Sprint 3

### 6.1 Streaming (SSE): mesma rota `POST /conversas/{id}/mensagens`
O front só usa SSE quando aberto com `?sse=1`. Sem isso, espera a resposta inteira (Sprint 2).

Pedido: mesmo corpo, com o cabeçalho `Accept: text/event-stream`. Resposta `200` com `Content-Type: text/event-stream` e eventos separados por linha em branco:
```
event: passo
data: {"passo": 1, "acao": "LER", "alvo": "", "resumo": "índice lido", "status": "ok", "tipo_erro": null}

event: passo
data: {"passo": 2, "acao": "LER", "alvo": "atendimento", "resumo": "'atendimento' lido", "status": "ok", "tipo_erro": null}

event: mensagem
data: {"id": "m-9", "resposta": "...", "tipo": "final", "trajetoria": [...], "uso": {...}, "confirmacao": null, "criada_em": "..."}
```
- `passo`: um `Passo` (4.7) assim que ele acontece. O front mostra os passos ao vivo.
- `mensagem`: a `RespostaAgente` completa (4.6). **Precisa ser o último evento.** Sem ele, o front mostra "A resposta do agente veio incompleta."
- Erro no meio: `event: erro` com `data: {"status": 504, "mensagem": "O modelo não respondeu."}` (pode ter `"codigo"`).
- Cada `data:` em **uma linha só** (JSON sem quebras de linha; `json.dumps` já faz assim).
- Erros antes de começar (`401`, `403`, `404`, `402`, `422`) voltam como resposta HTTP normal, com JSON, sem stream.
- Implementação sugerida: `StreamingResponse` com uma fila; o agente chama um callback a cada passo (o ajuste "`print` vira callback" pedido à Frente 3).

### 6.2 Confirmação de ferramentas de escrita
Quando o agente pede uma ferramenta com `acesso = "escrita"` (menos `solicitar_ferramenta_ausente`), o back-end **não executa**.
Ele guarda os argumentos e responde a mensagem com `tipo: "confirmacao"` e uma `Confirmacao` (4.9) com `situacao: "pendente"`.
O último passo da trajetória é `acao: "CONFIRMAR"`.

#### `POST /conversas/{id}/confirmacoes/{confirmacao_id}`
```json
{ "aprovar": true }
```
- `true`: executa a ferramenta pelo `catalogo.executar` (que **confere a permissão de novo**) com os argumentos guardados. `false`: não executa nada.
- Muda a `situacao` da confirmação para `"aprovada"` ou `"cancelada"` na mensagem original.
- Saída `200`: uma `RespostaAgente` (4.6) **nova**, com o resultado (`"E-mail enviado para ..."` ou `"Envio cancelado. Nada foi enviado."`) e `confirmacao: null`. O front a acrescenta ao fim da conversa.
- Erros: `404` (`"Confirmação não encontrada."`), `409` (`"Esta ação já foi confirmada ou cancelada."`), `403` se perdeu acesso ao agente.

### 6.3 `GET /ferramentas`
Saída `200`: `Ferramenta[]` (4.10) com o **catálogo inteiro** (as 41, inclusive planejadas e inativas), cada uma marcada para a pessoa logada.
Erro `403` para `GestorDeAcessos` (`"Seu perfil não usa ferramentas."`).
Usado no seletor "Adicionar ferramentas" da criação guiada.

### 6.4 Criação guiada de agentes (as 8 etapas do slide 11)
Um **rascunho** guarda o progresso. É da pessoa que o criou (os outros recebem `404`).
As etapas "Entender", "Perguntar", "Propor" e "Ajustar" podem ser feitas pelo modelo; o formato de saída é que precisa ser este.

#### Objeto `Rascunho`
```json
{
  "id": "rs-1",
  "etapa": "perguntas",
  "descricao": "Todo dia recebo pedidos de lojistas para calcular multa de fatura atrasada...",
  "area": "AtendimentoCliente",
  "entendimento": {
    "objetivo": "Calcular multa de faturas atrasadas",
    "quando": "Todo dia",
    "sistemas": ["CRM simulado", "SQL simulado"],
    "dados": ["Cadastro de clientes", "Faturas, multas e cobrança"]
  },
  "perguntas": [ /* Pergunta */ ],
  "respostas": {},
  "ficha": null,
  "mensagem": "Entendi o pedido. Faltam alguns detalhes: escolha as opções abaixo.",
  "testado": false,
  "criado_em": "2026-11-12T15:00:00-03:00"
}
```
| Campo | Observação |
| --- | --- |
| `etapa` | `"perguntas"` (sem ficha) → `"proposta"` (com ficha) → `"aprovado"` (virou agente) |
| `area` | A área de quem criou |
| `entendimento` | Etapa 2. `quando` pode ser `"A confirmar"`; `sistemas` e `dados` podem ser listas vazias |
| `respostas` | `{id_pergunta: valor}`, acumulando o que já foi respondido |
| `ficha` | `null` até as perguntas serem respondidas. Depois, um objeto `Ficha` |
| `mensagem` | Texto do "assistente" no topo da etapa (ex.: o que mudou depois de um ajuste). Pode ser `null` |
| `testado` | `true` depois de uma simulação. O front só libera "Aprovar" com `testado: true` |

#### Objeto `Pergunta`
```json
{
  "id": "dados",
  "texto": "Quais dados o agente precisa consultar?",
  "multipla": true,
  "opcoes": [
    { "valor": "clientes", "rotulo": "Cadastro de clientes" },
    { "valor": "faturas", "rotulo": "Faturas, multas e cobrança" }
  ],
  "sugestao": ["clientes", "faturas"]
}
```
- `multipla: true` → caixas de marcar, e a resposta é uma **lista** de `valor`. `false` → botões de opção, e a resposta é **um** `valor` (string).
- `sugestao`: o que já vem marcado (lista se `multipla`, string se não; pode ser `null`).
- Só perguntas de múltipla escolha. Não há campo de texto livre.

#### Objeto `Ficha`
```json
{
  "nome": "Assistente de Cobrança",
  "objetivo": "Calcular multa de faturas atrasadas",
  "area": "AtendimentoCliente",
  "passos": [
    "Entender o pedido do funcionário e perguntar o que faltar",
    "Consultar cadastro de clientes",
    "Calcular multa e juros da fatura em atraso",
    "Responder com um resumo claro, sem inventar dados"
  ],
  "ferramentas": [ /* Ferramenta (4.10) */ ],
  "risco": "medio",
  "usos_mes_estimados": 50,
  "custo_estimado_mes": 2.75,
  "economia_horas_mes": 13,
  "permissoes": {
    "ok": true,
    "avisos": [
      { "nivel": "aviso", "texto": "listar_faturas_em_atraso ainda está planejada: o agente só poderá usá-la depois de ativada." },
      { "nivel": "info", "texto": "Usa dados pessoais ou sigilosos: CPF, cartão e dados bancários são mascarados antes de chegar ao modelo." }
    ]
  }
}
```
| Campo | Regra sugerida (a mesma do mock) |
| --- | --- |
| `ferramentas` | Objetos completos (4.10), sempre incluindo `solicitar_ferramenta_ausente` |
| `risco` | `"alto"` se tem ferramenta de escrita; senão `"medio"` se tem sensibilidade `pessoal` ou `sigilosa`; senão `"baixo"` |
| `usos_mes_estimados` | Da pergunta "Quantas vezes por mês": poucas = 16, várias = 50, muitas = 110 |
| `custo_estimado_mes` | `usos × 5.500 tokens ÷ 1.000 × preço simulado por 1k tokens` (o mock usa R$ 0,01) |
| `economia_horas_mes` | `usos × 15 minutos ÷ 60`, arredondado |
| `permissoes.avisos[].nivel` | `"erro"`: ferramenta não liberada para a pessoa. `"aviso"`: ferramenta `planejada` ou `inativa`. `"info"`: escrita pede confirmação; dados sensíveis são mascarados |
| `permissoes.ok` | `true` só se **todas** as ferramentas estão `liberada`. Com `false`, o front bloqueia "Aprovar" |

#### Rotas da criação guiada
Todas devolvem o `Rascunho` atualizado, menos `simulacao` e `aprovar`.

| Rota e corpo | Etapa | O que faz | Erros |
| --- | --- | --- | --- |
| `POST /rascunhos` `{"descricao": "..."}` | 1–3 | Cria o rascunho: extrai o `entendimento` e gera de 2 a 4 `perguntas` | `422` se a descrição tiver menos de 15 caracteres; `403` para `GestorDeAcessos` |
| `GET /rascunhos/{id}` | | Retoma um rascunho (o id fica na URL do front: `#/criar/rs-1`) | `404` |
| `POST /rascunhos/{id}/respostas` `{"respostas": {"dados": ["clientes"], "acao": "consultar", "volume": "de_5_a_20"}}` | 4–5 | Junta com as respostas anteriores, monta a `ficha` e checa a permissão de cada ferramenta. `etapa` → `"proposta"` | `404` |
| `POST /rascunhos/{id}/ajustes` `{"texto": "adicione envio de e-mails"}` | 6 | Ajuste em linguagem simples. Devolve a ficha nova e uma `mensagem` dizendo o que mudou (ou que não entendeu) | `404`; `409` se ainda não há ficha |
| `PATCH /rascunhos/{id}` `{"ficha": {"nome": "...", "objetivo": "...", "ferramentas": ["consultar_cliente"]}}` | 6 | Edição direta pela tela. Todos os campos são opcionais; `ferramentas` é uma lista de **nomes** e substitui a lista inteira. Recalcula risco, custo e permissões | `404`; `409` se ainda não há ficha |
| `POST /rascunhos/{id}/simulacao` `{"exemplo": "Calcule a multa de R$ 500 com 10 dias"}` | 7 | Roda o agente com as ferramentas da ficha. **Ferramentas de escrita não executam.** Marca `testado: true` | `404`; `409` sem ficha; `422` com exemplo vazio |
| `POST /rascunhos/{id}/aprovar` (sem corpo) | 8 | Cria o agente (dono = quem aprovou, área = a da pessoa, `ativo: true`), grava em `agente_historico` e marca `etapa: "aprovado"` | `404`; `409` sem ficha; `403` se `permissoes.ok` for falso |

Saída da `simulacao`:
```json
{ "resposta": "...", "tipo": "final", "trajetoria": [ /* Passo */ ], "uso": { /* Uso */ }, "simulacao": true }
```
Saída do `aprovar`: o `Agente` criado (4.2). O front mostra "Conversar agora", que abre uma conversa com ele (`POST /conversas`).

Tabelas novas: `rascunhos` (JSONB para `entendimento`, `perguntas`, `respostas`, `ficha`) e `agente_historico`.

### 6.5 Monitoramento
O **escopo** é decidido pelo back-end a partir do perfil:
| Perfil | `escopo` | `rotulo_escopo` | O que entra |
| --- | --- | --- | --- |
| `Colaborador` | `"pessoal"` | `"Seu uso"` | Só o uso da própria pessoa |
| `Supervisor` | `"area"` | `"Agentes da sua área"` | Uso dos agentes da(s) área(s) dele, por qualquer pessoa |
| `AdminGlobal` | `"plataforma"` | `"Toda a plataforma"` | Tudo |
| `GestorDeAcessos` | | | `403` em todas as rotas de monitoramento |

As três primeiras rotas aceitam `?dias=7` ou `?dias=30` (padrão 30). O período vai de hoje (inclusive) até `dias - 1` dias atrás.
Fontes: `uso_modelo` (tokens, latência, custo), `execucoes_ferramenta` e `mensagens` (execuções e erros), `eventos_erro` (alertas).
**Uma execução = uma mensagem respondida pelo agente.** Ela conta como erro se alguma ferramenta falhou (`tipo_erro` diferente de `null` e de `permissao_negada`).

#### `GET /monitoramento/resumo`
```json
{
  "escopo": "pessoal",
  "rotulo_escopo": "Seu uso",
  "dias": 30,
  "gasto_mes": 16.42,
  "limite_mes": 20.0,
  "custo_periodo": 44.11,
  "execucoes": 437,
  "erros": 39,
  "taxa_erro": 0.089,
  "chamadas_modelo": 2137,
  "tokens_entrada": 2900000,
  "tokens_saida": 184081,
  "latencia_media_ms": 1124
}
```
- `gasto_mes` e `limite_mes` são **sempre da pessoa** (o limite é por pessoa, no mês corrente). O resto é do escopo e do período.
- `taxa_erro = erros / execucoes` (0 se não houve execução). `latencia_media_ms` = média por chamada ao modelo.

#### `GET /monitoramento/uso-diario`
**Exatamente um item por dia do período, inclusive dias sem uso (com zeros)**, do mais antigo ao mais novo:
```json
[
  { "dia": "2026-11-11", "custo": 0, "execucoes": 0, "erros": 0, "tokens": 0 },
  { "dia": "2026-11-12", "custo": 1.89, "execucoes": 17, "erros": 2, "tokens": 98000 }
]
```
`tokens` = entrada + saída. O gráfico usa `custo`; a tabela alternativa mostra todos os campos.

#### `GET /monitoramento/agentes`
Um item por agente com uso no período, do mais usado ao menos usado:
```json
[
  {
    "agente_id": "ag-atendimento",
    "nome": "Assistente de Atendimento",
    "area": "AtendimentoCliente",
    "ativo": true,
    "execucoes": 636,
    "taxa_sucesso": 0.94,
    "latencia_media_ms": 1100,
    "tokens": 3100000,
    "custo": 31.2,
    "ultimo_uso": "2026-11-12",
    "saude": "saudavel"
  }
]
```
`saude`: `"inativo"` se o agente está desativado; senão `"critico"` se a taxa de erro passa de 15%, `"atencao"` se passa de 6%, e `"saudavel"` nos outros casos.

#### `GET /monitoramento/alertas`
Sem `?dias`. Lista de alertas ativos, os mais graves e recentes primeiro. **Falhas repetidas viram um alerta só**, com `ocorrencias` somando
(conteúdo pedido pela QA no slide 41: agente, falha, etapa, horário, o que fazer).
```json
[
  {
    "id": "al-1",
    "nivel": "erro",
    "agente": { "id": "ag-cobranca", "nome": "Cobrança e Multas" },
    "falha": "integracao_indisponivel em consultar_transacoes_cliente (core de pagamentos fora do ar)",
    "etapa": "Passo 4: USAR consultar_transacoes_cliente",
    "quando": "2026-11-12T09:41:00-03:00",
    "ocorrencias": 3,
    "o_que_fazer": "Aguardar o core voltar. O agente avisou o usuário e seguiu com o restante do pedido."
  },
  {
    "id": "al-limite",
    "nivel": "aviso",
    "agente": null,
    "falha": "Gasto do mês em 82% do seu limite",
    "etapa": "Limite de gasto",
    "quando": "2026-11-12T10:00:00-03:00",
    "ocorrencias": 1,
    "o_que_fazer": "Ao chegar em 100%, novas mensagens precisam de aprovação do seu gestor."
  }
]
```
- `nivel`: `"erro"` \| `"aviso"` \| `"info"`.
- `agente: null` para alertas da própria conta (como o de gasto acima de 80%, que vira `"erro"` em 100%).
- Quem vê: `Colaborador` → alertas dos agentes **que criou** + os da própria conta; `Supervisor` → agentes da área; `AdminGlobal` → todos.
- O Painel também chama esta rota (para o contador de alertas), mas funciona sem ela.

---

## 7. Dados de seed para a demo

### 7.1 Back-end real: contas vindas do diretório do mock
Decidido em 25/11: o back-end **não** usa as contas inventadas do 7.2. Cada conta é um funcionário do mock
(`mock/gerar.py`), porque é dele que saem cargo, nível N1/N2, carteiras e situação, e só assim as quatro checagens
de acesso rodam com dados reais. O seed (`cd backend && python -m app.seed --senha <senha>`) cria uma conta por
funcionário, com o nome e o e-mail sintéticos do mock (`<nome>.<sobrenome>@stonesim.example`), mais uma conta de
`GestorDeAcessos`, que não tem cargo no mock. A senha da demo fica no `.env` (`SEED_SENHA_DEMO`), fora do Git.
Lojistas são `M00001` a `M00020` (não `CLI-0001`).

| id | Cargo (mock) | Perfil | Área | Carteira | Uso na demo |
| --- | --- | --- | --- | --- | --- |
| `F0001` | atendente_n1 | Colaborador | AtendimentoCliente | varejo | Lojista de fora da carteira (ex.: `M00005`) é **negado** |
| `F0002`, `F0003`, `F0005` | especialista_n2 | Colaborador | AtendimentoCliente | do time | N2 só vê a carteira do time |
| `F0004` | atendente_n1 | Colaborador | AtendimentoCliente | pme | |
| `F0006` | supervisor_atendimento | Supervisor | AtendimentoCliente | todas | |
| `F0007` | analista_ouvidoria | Colaborador | AtendimentoCliente | todas | |
| `F0008`, `F0009`, `F0010` | analistas do financeiro | Colaborador | Financeiro | todas | |
| `F0011` | coordenador_financeiro | Supervisor | Financeiro | todas | |
| `F0012` | auditor_compliance | Auditor | | | Não usa agentes |
| `F0013` | admin_plataforma | AdminGlobal | | | Vê agentes, não executa |
| `F0014`, `F0015` | desligado e afastada | | | | Login **negado** mesmo com a senha certa |
| `G0001` | (sem cargo) | GestorDeAcessos | AtendimentoCliente | | Não vê agentes nem ferramentas |

Os agentes da demo no back-end real entram com o seed de agentes (KAN-60), usando os nomes atuais do catálogo.

### 7.2 Modo mock do front
O roteiro da demo em modo mock (`frontend/README.md`) usa estas contas e agentes, que existem só no navegador.
Senha de todas: `stone123` (dado sintético, só para a demo).

| id | Nome | E-mail | Perfil | Área | Carteira | Limite/mês |
| --- | --- | --- | --- | --- | --- | --- |
| `u-ana` | Ana Ribeiro | ana@stonelab.test | AdminGlobal | Financeiro | | R$ 50 |
| `u-bruno` | Bruno Martins | bruno@stonelab.test | Supervisor | AtendimentoCliente | | R$ 40 |
| `u-fernanda` | Fernanda Costa | fernanda@stonelab.test | Supervisor | Financeiro | | R$ 40 |
| `u-carla` | Carla Souza | carla@stonelab.test | Colaborador | AtendimentoCliente | CLI-0001, CLI-0002, CLI-0003 | R$ 20 |
| `u-diego` | Diego Alves | diego@stonelab.test | Colaborador | Financeiro | CLI-0004, CLI-0005, CLI-0007 | R$ 20 |
| `u-gabriela` | Gabriela Lima | gabriela@stonelab.test | GestorDeAcessos | AtendimentoCliente | | |

| id | Nome | Área | Dono | Convidados | Ferramentas | Ativo |
| --- | --- | --- | --- | --- | --- | --- |
| `ag-atendimento` | Assistente de Atendimento | AtendimentoCliente | u-bruno | u-carla | as 5 ativas (`consultar_cliente`, `consultar_transacoes_cliente`, `calcular_multa_atraso`, `consultar_endereco_cep`, `solicitar_ferramenta_ausente`) | sim |
| `ag-cobranca` | Cobrança e Multas | Financeiro | u-diego | | `consultar_cliente`, `consultar_transacoes_cliente`, `calcular_multa_atraso`, `listar_faturas_em_atraso`, `solicitar_ferramenta_ausente` | sim |
| `ag-chamados` | Resumo de Chamados | AtendimentoCliente | u-carla | | `consultar_cliente`, `listar_tickets_cliente`, `consultar_ticket`, `solicitar_ferramenta_ausente` | sim |
| `ag-relatorio` | Relatório Semanal Financeiro | Financeiro | u-fernanda | u-diego | `resumir_receita_periodo`, `consultar_transacoes_cliente`, `enviar_email`, `solicitar_ferramenta_ausente` | sim |
| `ag-conciliacao` | Conciliação de Transações (v1) | Financeiro | u-ana | | `consultar_transacoes_cliente` | **não** |

Objetivos dos agentes, na mesma ordem:
1. "Tira dúvidas sobre clientes, transações, multas e endereços durante o atendimento."
2. "Calcula multa e juros de faturas em atraso e consulta o histórico do lojista."
3. "Resume os chamados abertos de um cliente antes do contato."
4. "Monta o resumo semanal de receita e envia por e-mail ao time."
5. "Versão antiga da conciliação. Substituída pelo Relatório Semanal."

Observações:
- Clientes e transações são os de `ferramentas/dados_sinteticos.py`.
- No mock, `enviar_email` funciona (para demonstrar a confirmação). No back-end real ela continua `planejada` até a Sprint 3.
- No mock, o `CLI-0007` simula o core de pagamentos fora do ar (`integracao_indisponivel`), para mostrar um alerta.

---

## 8. Para combinar com o grupo

| # | Assunto | Com quem | Impacto no front |
| --- | --- | --- | --- |
| 1 | Trajetória como objeto (4.7) em vez de string | Frente 3 | Nenhum: o front aceita os dois. Com objeto, aparecem `pensamento` e o status exato |
| 2 | `PERGUNTAR` sem `input()` e histórico por parâmetro | Frente 3 | **Sem isso, `tipo: "pergunta"` não funciona** |
| 3 | Correspondência perfil → nível de ferramenta | Brenno e Pedro | `liberada` e `motivo` de `/ferramentas` e da ficha |
| 4 | Valor do limite de gasto por perfil e o que acontece em 100% | Milene | O front já trata `402 limite_atingido` e o aviso em 80% |
| 5 | `uso_mes` em `/me` já na Sprint 2 | Back-end | Barato de calcular; liga o aviso de 80% em todas as telas |
| 6 | Tela do `GestorDeAcessos` (atribuir e remover perfis) | PO e Interface | Ainda não desenhada: hoje o Painel só mostra um aviso para esse perfil |
| 7 | Eventos que viram alerta (`eventos_erro`) | Enrico | Formato de 6.5 |
