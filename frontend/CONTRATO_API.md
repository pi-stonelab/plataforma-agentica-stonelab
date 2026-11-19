# Contrato da API (o que a interface espera do back-end)

Este arquivo lista **todas as rotas que a interface chama**, com o formato de entrada e saída.
O modo mock do front (`frontend/js/mock/servidor.js`) já responde exatamente isto, dentro do navegador.
Ele serve de implementação de referência: na dúvida sobre um campo, leia a rota correspondente lá.

Quando o back-end implementar uma rota, a interface passa a usá-la sem mudar nenhuma tela:
basta abrir com `?mock=0`.

> Regra: se o back-end precisar mudar algum formato, mude **aqui e em `js/api.js`** no mesmo PR.

## Convenções

| Item | Regra |
| --- | --- |
| Formato | JSON (`Content-Type: application/json`), datas em ISO 8601 (`2026-11-12T14:03:00-03:00`), dias como `YYYY-MM-DD` |
| Login | `Authorization: Bearer <token>` em todas as rotas, exceto `/health` e `/auth/login` |
| Perfil | **Sempre do token + banco.** O front nunca manda perfil, área, nível ou carteira |
| Erros | Padrão do FastAPI: `{"detail": "mensagem legível"}` ou `{"detail": {"codigo": "...", "mensagem": "..."}}`. A interface mostra `mensagem` direto para a pessoa, então escreva em português |
| 401 | Token ausente, inválido ou expirado. O front volta para o login |
| 403 | Logado, mas sem permissão (ex.: `AcessoNegado` do `seguranca`) |
| 404 | Não existe **ou a pessoa não pode ver**. Agente de outra pessoa responde 404, não 403, para não revelar que existe |
| 422 | Validação (o pydantic já faz) |
| Valores em dinheiro | `number` em reais (`16.42`), preço **simulado** por token |

### Como servir o front
Duas opções (escolham uma):

1. **Mesma origem (recomendado para a demo):** o FastAPI serve a pasta `frontend/`.
   ```python
   # backend/app/main.py, DEPOIS de incluir as rotas
   from fastapi.staticfiles import StaticFiles
   app.mount("/app", StaticFiles(directory="../frontend", html=True), name="frontend")
   ```
   Abrir `http://localhost:8000/app/?mock=0`. Não precisa de CORS.
2. **Origens separadas:** front em `python -m http.server 5500` (dentro de `frontend/`) e back-end em `:8000`.
   Abrir `http://localhost:5500/?mock=0&api=http://localhost:8000`. Precisa de CORS no back-end:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5500"],
                      allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
   ```

---

## Sprint 2 (KAN-60): o mínimo para a demo de 19/11

Com estas 7 rotas, Login, Painel e Chat funcionam com o back-end real.

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /auth/login`
Entrada:
```json
{ "email": "carla@stonelab.dev", "senha": "..." }
```
Saída `200`:
```json
{ "token": "eyJhbGciOi...", "tipo": "bearer" }
```
Erro `401`: `{"detail": "E-mail ou senha inválidos."}` (a mesma mensagem para e-mail inexistente e senha errada).

### `GET /me`
```json
{
  "id": "u-carla",
  "nome": "Carla Souza",
  "email": "carla@stonelab.dev",
  "perfil": "Colaborador",
  "area": "AtendimentoCliente",
  "areas_extras": [],
  "carteira": ["CLI-0001", "CLI-0002", "CLI-0003"],
  "uso_mes": { "gasto": 16.42, "limite": 20.0 }
}
```
- `perfil`: `AdminGlobal` | `Supervisor` | `Colaborador` | `GestorDeAcessos` (nomes das classes do `seguranca`).
- `area`: `Financeiro` | `AtendimentoCliente`.
- `uso_mes` é **opcional na Sprint 2**. Sem ele, a faixa de aviso de 80% e o medidor do Painel somem. Vem de `uso_modelo` (soma do mês) + limite do perfil.

### `GET /agentes`
Agentes que a pessoa **pode ver** (`usuario.pode(Acao.VER, agente)`). O `GestorDeAcessos` recebe `[]`.
```json
[
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
]
```
- `acoes`: para cada `Acao`, incluir se `usuario.pode(acao, agente)`. O front mostra o botão **Conversar** só com `EXECUTAR`.
  Agente desativado (`ativo: false`) só tem `VER` (regra já existente no `seguranca`).
- `relacao`: `dono` | `admin` | `supervisor` (agente da área dele) | `convidado`. Só para o selo do cartão.

### `GET /agentes/{id}`
Mesmo objeto acima. `404` se não existe ou a pessoa não pode ver.

### `GET /conversas`
Conversas **da pessoa logada**, mais recente primeiro.
```json
[
  {
    "id": "cv-123",
    "agente": { "id": "ag-atendimento", "nome": "Assistente de Atendimento" },
    "titulo": "Qual a situação do cliente CLI-0002?",
    "criada_em": "2026-11-12T10:00:00-03:00",
    "atualizada_em": "2026-11-12T10:01:09-03:00"
  }
]
```
`titulo`: primeiros ~60 caracteres da primeira mensagem (ou `null` → o front mostra "Nova conversa").

### `POST /conversas`
Entrada: `{ "agente_id": "ag-atendimento" }`. Checa `EXECUTAR` (primeira checagem de permissão).
Saída `201`: o mesmo objeto de `GET /conversas/{id}`, com `mensagens: []`.
Erros: `404` (agente invisível), `403` (pode ver mas não executar, ex.: agente desativado).

### `GET /conversas/{id}`
```json
{
  "id": "cv-123",
  "agente": {
    "id": "ag-atendimento", "nome": "Assistente de Atendimento", "objetivo": "...",
    "ferramentas": ["consultar_cliente"], "ativo": true, "pode_executar": true
  },
  "criada_em": "2026-11-12T10:00:00-03:00",
  "mensagens": [
    { "id": "m-1", "autor": "usuario", "texto": "Qual a situação do cliente CLI-0002?", "criada_em": "..." },
    {
      "id": "m-2", "autor": "agente", "texto": "Mercearia Horizonte (CLI-0002)...",
      "tipo": "final", "trajetoria": [ ... ], "uso": { ... }, "confirmacao": null, "criada_em": "..."
    }
  ]
}
```
`404` se a conversa não é da pessoa. `pode_executar: false` desliga a caixa de texto (ex.: perdeu o convite).

### `POST /conversas/{id}/mensagens`
Entrada: `{ "texto": "Calcule a multa de R$ 1.250,00 com 15 dias de atraso" }` (1 a 2.000 caracteres).

Saída `200`:
```json
{
  "id": "m-9",
  "resposta": "Para uma fatura de R$ 1.250,00 com 15 dias de atraso:\n• Multa (2%): R$ 25,00\n...",
  "tipo": "final",
  "trajetoria": [ ... ],
  "uso": { "chamadas_modelo": 5, "tokens_entrada": 7400, "tokens_saida": 410, "latencia_ms": 4300, "custo": 0.078 },
  "confirmacao": null,
  "criada_em": "2026-11-12T21:06:00-03:00"
}
```
- `tipo`:
  - `final`: resposta do `FINAL`.
  - `pergunta`: o agente usou `PERGUNTAR`. **O turno termina aqui** (sem `input()`). A próxima mensagem da pessoa é a resposta, e o back-end precisa passar o histórico ao agente (ajuste pedido à Frente 3).
  - `bloqueio` (Sprint 3): barrado pelas travas da Frente 6 (instrução maliciosa, golpe da troca de conta). O front pinta de vermelho.
  - `confirmacao` (Sprint 3): ferramenta de escrita esperando a pessoa. Ver `confirmacao` abaixo.
- `resposta` e `texto` (do histórico) são **texto puro**. O front nunca interpreta HTML. Quebras de linha (`\n`) são respeitadas.
- `uso` é opcional; se vier, aparece embaixo da mensagem. Mesmos números gravados em `uso_modelo`.
- Erros: `403` (perdeu acesso ao agente), `402` com `{"detail": {"codigo": "limite_atingido", "mensagem": "..."}}` (Sprint 3), `504` (modelo não respondeu).

O back-end grava a mensagem da pessoa, roda o agente, grava a resposta + `trajetoria` (JSONB em `mensagens`), as execuções (`governanca.adicionar_destino`) e o `uso_modelo`.

#### Formato da `trajetoria`
**Proposta** (um objeto por passo do agente):
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
- `acao`: `LER` | `USAR` | `PERGUNTAR` | `FINAL` (e, na Sprint 3, `BLOQUEIO` | `CONFIRMAR`).
- `status`: `ok` | `erro` | `bloqueado` (bloqueado = `permissao_negada`, pinta de vermelho com cadeado).
- `tipo_erro`: os 7 de `ferramentas/base.py` ou `null`.
- `pensamento`: o texto de `PENSAMENTO:` do modelo (opcional).
- **Nunca** coloque argumentos com dados de cliente nem o resultado da ferramenta no `resumo`.

**Hoje** o `agente.py` devolve strings como `"Passo 4: USAR -> 'calcular_multa_atraso' executada: sucesso"`.
O front **aceita os dois formatos** (converte a string sozinho), então a Sprint 2 pode sair com strings.
Pedido à Frente 3: devolver o objeto acima (é só montar um `dict` onde hoje se monta a string).

---

## Sprint 3

### Confirmação de ferramentas de escrita
Quando o agente pede uma ferramenta de `acesso = "escrita"` (fora `solicitar_ferramenta_ausente`), o back-end **não executa**.
Ele responde `tipo: "confirmacao"` com:
```json
"confirmacao": {
  "id": "cf-77",
  "ferramenta": "enviar_email",
  "titulo": "Enviar e-mail",
  "campos": [
    { "rotulo": "Para", "valor": "time-financeiro@stonelab.dev" },
    { "rotulo": "Assunto", "valor": "Resumo semanal de receita" },
    { "rotulo": "Mensagem", "valor": "Olá, time..." }
  ],
  "situacao": "pendente"
}
```
O back-end guarda os argumentos do lado dele (o front só mostra `campos`).

#### `POST /conversas/{id}/confirmacoes/{confirmacao_id}`
Entrada: `{ "aprovar": true }` ou `{ "aprovar": false }`.
Saída: mesmo formato de `POST /conversas/{id}/mensagens` (a nova mensagem do agente: "E-mail enviado…" ou "Envio cancelado…").
Erros: `404`, `409` se já foi decidida. A execução passa de novo pelo `catalogo.executar` (segunda checagem).

### Streaming (SSE)
Mesma rota `POST /conversas/{id}/mensagens`, com cabeçalho `Accept: text/event-stream`. Eventos:
```
event: passo
data: {"passo": 1, "acao": "LER", "alvo": "", "resumo": "índice lido", "status": "ok", "tipo_erro": null}

event: passo
data: {...}

event: mensagem
data: {"id": "m-9", "resposta": "...", "tipo": "final", "trajetoria": [...], "uso": {...}, "confirmacao": null, "criada_em": "..."}
```
Erro no meio: `event: erro` com `data: {"status": 504, "mensagem": "..."}`.
O front já sabe ler isso: abrir com `?sse=1`. Sem SSE, ele espera a resposta inteira (Sprint 2).
Implementação sugerida: `StreamingResponse` + um callback no agente chamado a cada passo (o ajuste "`print` vira callback" pedido à Frente 3).

### `GET /ferramentas`
Catálogo inteiro (41 fichas), cada uma marcada para a pessoa logada. Usado na criação guiada.
```json
[
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
]
```
`liberada` / `motivo` = `governanca.motivo_bloqueio(ferramenta, usuario_camada2)`. `403` para `GestorDeAcessos`.

### Criação guiada (8 etapas do slide 11)
Um **rascunho** guarda o progresso. Formato:
```json
{
  "id": "rs-1",
  "etapa": "perguntas",
  "descricao": "Todo dia recebo pedidos de lojistas...",
  "area": "AtendimentoCliente",
  "entendimento": {
    "objetivo": "Calcular multa de faturas atrasadas",
    "quando": "Todo dia",
    "sistemas": ["CRM simulado", "SQL simulado"],
    "dados": ["Cadastro de clientes", "Faturas, multas e cobrança"]
  },
  "perguntas": [
    {
      "id": "dados", "texto": "Quais dados o agente precisa consultar?", "multipla": true,
      "opcoes": [{ "valor": "clientes", "rotulo": "Cadastro de clientes" }],
      "sugestao": ["clientes"]
    }
  ],
  "respostas": {},
  "ficha": null,
  "mensagem": "Entendi o pedido. Faltam alguns detalhes.",
  "testado": false
}
```
`etapa`: `perguntas` → `proposta` → `aprovado`. Quando há ficha:
```json
"ficha": {
  "nome": "Assistente de Cobrança",
  "objetivo": "...",
  "area": "AtendimentoCliente",
  "passos": ["Entender o pedido...", "Consultar cadastro de clientes", "..."],
  "ferramentas": [
    { "nome": "consultar_cliente", "area": "atendimento", "descricao": "...", "acesso": "leitura",
      "sensibilidade": "pessoal", "status": "ativa", "liberada": true, "motivo": null }
  ],
  "risco": "medio",
  "usos_mes_estimados": 50,
  "custo_estimado_mes": 2.75,
  "economia_horas_mes": 13,
  "permissoes": {
    "ok": true,
    "avisos": [{ "nivel": "aviso", "texto": "listar_faturas_em_atraso ainda está planejada..." }]
  }
}
```
- `risco`: `baixo` | `medio` (dados pessoais/sigilosos) | `alto` (tem ferramenta de escrita).
- `avisos[].nivel`: `info` | `aviso` | `erro`. `permissoes.ok = false` bloqueia a aprovação.

| Rota | Etapa | O que faz |
| --- | --- | --- |
| `POST /rascunhos` `{descricao}` | 1–3 | Modelo extrai o `entendimento` e gera poucas `perguntas` com opções. `422` se a descrição for curta demais. `403` para `GestorDeAcessos` |
| `GET /rascunhos/{id}` | | Retoma um rascunho (o front guarda o id na URL) |
| `POST /rascunhos/{id}/respostas` `{respostas: {id_pergunta: valor}}` | 4–5 | Monta a `ficha` e checa permissões de cada ferramenta |
| `POST /rascunhos/{id}/ajustes` `{texto}` | 6 | Ajuste em linguagem simples ("adicione e-mails", "chame de X"). Devolve o rascunho com `mensagem` dizendo o que mudou |
| `PATCH /rascunhos/{id}` `{ficha: {nome?, objetivo?, ferramentas?: [nomes]}}` | 6 | Edição direta pela tela |
| `POST /rascunhos/{id}/simulacao` `{exemplo}` | 7 | Roda o agente com as ferramentas da ficha. **Escrita não executa.** Devolve `{resposta, tipo, trajetoria, uso, simulacao: true}` e marca `testado` |
| `POST /rascunhos/{id}/aprovar` | 8 | Cria o agente (área e dono = quem aprovou) e devolve o objeto de `GET /agentes/{id}`. `403` se `permissoes.ok` for falso |

Tabelas: `rascunhos` (nova, JSONB para `entendimento`, `perguntas`, `respostas`, `ficha`) e `agente_historico` na aprovação.

### Monitoramento
Escopo decidido pelo back-end: `Colaborador` → o próprio uso; `Supervisor` → agentes da(s) área(s); `AdminGlobal` → tudo; `GestorDeAcessos` → `403`.
Todas aceitam `?dias=7` ou `?dias=30` (padrão 30).

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
`gasto_mes` / `limite_mes` são sempre **da pessoa** (o limite é por pessoa); o resto é do escopo.

#### `GET /monitoramento/uso-diario`
Um item por dia do período, **inclusive dias sem uso** (com zeros), do mais antigo ao mais novo:
```json
[{ "dia": "2026-11-12", "custo": 1.89, "execucoes": 17, "erros": 2, "tokens": 98000 }]
```

#### `GET /monitoramento/agentes`
```json
[{
  "agente_id": "ag-atendimento", "nome": "Assistente de Atendimento", "area": "AtendimentoCliente", "ativo": true,
  "execucoes": 636, "taxa_sucesso": 0.94, "latencia_media_ms": 1100, "tokens": 3100000, "custo": 31.2,
  "ultimo_uso": "2026-11-12", "saude": "saudavel"
}]
```
`saude`: `saudavel` | `atencao` | `critico` | `inativo` (regra sugerida: erro > 6% atenção, > 15% crítico).

#### `GET /monitoramento/alertas`
Conteúdo pedido pela QA (slide 41): agente, falha, etapa, horário, o que fazer; repetidos agrupados.
```json
[{
  "id": "al-1",
  "nivel": "erro",
  "agente": { "id": "ag-cobranca", "nome": "Cobrança e Multas" },
  "falha": "integracao_indisponivel em consultar_transacoes_cliente",
  "etapa": "Passo 4: USAR consultar_transacoes_cliente",
  "quando": "2026-11-12T09:41:00-03:00",
  "ocorrencias": 3,
  "o_que_fazer": "Aguardar o core voltar..."
}]
```
`agente: null` para alertas da própria conta (ex.: "gasto em 85% do limite"). Vem de `eventos_erro`.

---

## Para combinar com o grupo
1. **Trajetória como objeto** (Frente 3): formato acima. Até lá o front converte as strings.
2. **`PERGUNTAR` sem `input()` e histórico por parâmetro** (Frente 3): sem isso, o `tipo: "pergunta"` não funciona.
3. **Correspondência perfil → nível** (Brenno e Pedro): o front não depende disso, mas `liberada`/`motivo` de `/ferramentas` sim.
4. **Limite de gasto** (Milene): valor por perfil e o que acontece em 100% (o front já trata `402 limite_atingido`).
5. **`uso_mes` em `/me`**: barato de calcular e alimenta o aviso de 80% em todas as telas.
6. **Tela do `GestorDeAcessos`** (atribuir/remover perfis): ainda não desenhada; o Painel mostra só um aviso para esse perfil.
