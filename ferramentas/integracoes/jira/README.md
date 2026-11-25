# Jira

O Jira Cloud da Stone: chamados internos entre times (pedido ao time de recebíveis, falha num sistema, acesso a
um relatório). Não é o CRM dos lojistas: chamado de lojista é `CH000001`, chamado interno é `KAN-123`.

## Ferramentas que usam

- `chamados_internos/consultar_chamado_jira` (leitura)
- `chamados_internos/abrir_chamado_jira` (escrita em duas fases)
- `chamados_internos/comentar_chamado_jira` (escrita em duas fases)

## Conector

`conector.py` (`ConectorJira`) fala com a REST API v3 do Jira Cloud pelo cliente HTTP comum
(`integracoes/cliente_http.py`), com autenticação Basic (e-mail e token de API da conta de serviço). Descrições e
comentários chegam em ADF, o formato de texto rico do Jira, e `adf.py` os converte em texto simples (sem URL de
link, sem e-mail de ninguém). Pedidos:

- `GET /rest/api/3/issue/{chave}?fields=summary,status,issuetype,priority,created,updated,description,project`
- `GET /rest/api/3/issue/{chave}/comment?orderBy=-created&maxResults=5`
- `POST /rest/api/3/issue` com `project`, `issuetype`, `summary` e `description` (ADF)
- `POST /rest/api/3/issue/{chave}/comment` com `body` (ADF)
- `GET /rest/api/3/myself` e `GET /rest/api/3/project/{chave}` só no `testar`

Fonte: https://developer.atlassian.com/cloud/jira/platform/rest/v3/ e a estrutura do ADF em
https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/.

Regras: só projetos de `JIRA_PROJETOS` (inclusive para ler: a chave tem de ser de um projeto liberado) e só tipos
de `JIRA_TIPOS` para abrir. O modelo nunca escolhe o site. Resumo, descrição e comentário que saem passam pela
máscara de texto livre antes da prévia. 404 do Jira é "não encontrado"; outros 4xx são recusa (nada foi criado);
5xx, tempo esgotado e queda contam no disjuntor; escrita sem resposta vira "pode ter saído".

## Ligação

1. Crie (ou use) uma conta de serviço no Jira com acesso aos projetos liberados (permissões de ver, criar e
   comentar chamados).
2. Com essa conta, crie um token de API em id.atlassian.com, em Segurança > Tokens de API.
3. No `.env`: `JIRA_URL=https://empresa.atlassian.net`, `JIRA_EMAIL=<e-mail da conta>`, `JIRA_TOKEN=<token>`,
   `JIRA_PROJETOS=KAN` (chaves separadas por vírgula) e `JIRA_TIPOS=Tarefa` (o primeiro é o padrão; use o nome do
   tipo como aparece no Jira do projeto).
4. `MODO_TERMINAL=1 python -m ferramentas.integracoes testar jira`: confere a conta e se cada projeto existe, sem
   criar nada.

Sem token, a integração fica desligada e as três ferramentas somem do que o modelo vê. `JIRA_MODO=simulado` liga
um Jira em memória (projeto `PLAT`, dois chamados de exemplo) para demo e testes; toda resposta diz isso em
`fonte`.

## Hoje

Conector real pronto. Nos testes, um servidor HTTP local no formato da API v3
(`backend/tests/apoio_integracoes_externas.py`). O sistema `jira` de `mock.falhas` derruba a integração na demo.
