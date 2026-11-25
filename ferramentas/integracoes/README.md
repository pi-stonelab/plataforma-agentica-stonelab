# Integrações

Uma pasta por sistema que as ferramentas usam. Este material é para quem mantém o código. O agente não lê esta
pasta: ele só enxerga as ferramentas pelo catálogo.

## Como funciona

- `conector.py`: a classe `Conector`. Cada integração tem um, com o mesmo nome usado em `integracoes` nas fichas.
  O modo vem do .env, na hora de cada uso: `real` (fala com o serviço de verdade), `simulado` (sem rede, dados fixos)
  ou `desligado`. Valor estranho no .env desliga (falha fechada). Toda chamada de rede passa por
  `chamar(etapa, funcao, servico=...)`: 3 falhas de rede seguidas pausam o serviço por 60 s, e passada a pausa uma
  chamada testa de novo. Pedido recusado (4xx) e erro do nosso código não contam. O log leva só integração,
  serviço, etapa e tipo do erro. `credencial` diz se a conta é uma só da plataforma (.env) ou de cada pessoa
  (OAuth2 por pessoa, `credenciais.py`; as rotas de ligação são do back-end); `exigir_destino` só aceita canal, chat ou projeto da lista permitida
  do .env; `aviso_desligada` é o que o agente ouve quando a integração está desligada (nunca fala do .env).
- `cliente_http.py`: o cliente HTTP de todos os conectores (httpx). HTTPS obrigatório fora do localhost; URL base
  do .env sem usuário, senha, parâmetro nem fragmento; `montar_url(base, *segmentos)` codifica cada pedaço do caminho
  e não deixa sair da base; redirecionamento só para a mesma origem; prazo total do pedido (não só por leitura);
  teto de 1 MB. 429, 5xx, JSON quebrado e tempo esgotado viram `ConnectionError` ou `TimeoutError` (a ferramenta
  responde `integracao_indisponivel`, sem detalhe); 401 e 403, `CredencialRecusada`; outros 4xx,
  `parametro_invalido`. Escrita (POST, PUT, PATCH, DELETE) que chegou e ficou sem resposta, ou recebeu 500, 502 ou
  504, vira `base.EfeitoIncerto` ("pode ter saído"): ninguém repete sozinho. Os loggers do httpx e do httpcore
  ficam em WARNING, porque no INFO eles gravam a URL inteira.
- `registro.py`: a lista dos conectores e `estado_integracoes()`, uma linha por integração com `nome`, `rotulo`,
  `tipo` (`interno` ou `externo`), `credencial`, `modo`, `configurado`, `saude`, `servicos` (a saúde de cada
  serviço) e as `ferramentas` que usam. Saúde, da pior para a melhor: `desligada`, `configuracao_invalida`,
  `indisponivel` (falha simulada ou falha de rede há menos de 5 minutos), `pausada`, `sem_chamadas` (ninguém chamou
  ainda desde que a plataforma subiu) e `ok`. Nenhum valor do .env aparece.
- `sistemas_internos.py`: os sistemas da Stone, que aqui são o mock (modo sempre `simulado`); a saúde vem de
  `mock.falhas`.
- `credenciais.py` e `oauth.py`: a conta OAuth2 de cada pessoa (Google e Microsoft): `ProvedorDeCredencial`
  (quem guarda os tokens; hoje em memória, o back-end troca) e `FluxoOAuth` (autorizar com PKCE, concluir, renovar,
  desligar). `escritorio.py` e `escritorio_simulado.py`: a base dos dois conectores de escritório e o mundo simulado.
  `formatos.py`: leitura e escrita de txt, csv, xlsx, docx e pdf, com limites.

Terminal, na raiz do repositório:

    python -m ferramentas.integracoes estado
    MODO_TERMINAL=1 python -m ferramentas.integracoes testar apis_publicas

## Integrações

Internas (o mock, a Stone simulada):

- `crm/`: CRM de atendimento (cadastro e chamados).
- `sql/`: core de pagamentos, cadastro, cobrança e disputas.
- `bigquery/`: base analítica (ainda sem ferramenta ativa).
- `datahub/`: dicionário de dados (ainda sem ferramenta ativa).

A QA derruba qualquer uma (inclusive as externas: `apis_publicas`, `email`, `email_leitura`, `jira`, `slack`,
`telegram`, `google_workspace`, `microsoft_365` e `anexos`) com `MOCK_FALHAS` no .env.

Externas:

- `apis_publicas/`: ViaCEP e PTAX do Banco Central. Real.
- `email/`: envio por SMTP. Real.
- `email_leitura/`: leitura da caixa da plataforma por IMAP. Real.
- `jira/`: chamados internos (Jira Cloud REST v3). Real.
- `slack/`: mensagem em canal interno (Web API). Real.
- `telegram/`: aviso em chat interno (Bot API). Real.
- `google_workspace/`: agenda, planilhas, documentos e arquivos da conta Google de cada pessoa (OAuth2). Real.
- `microsoft_365/`: o mesmo, pelo Microsoft Graph (Outlook, OneDrive, Excel e Word). Real.
- `anexos/`: os arquivos do chat, numa pasta da plataforma. Interna, sem rede.

Jira, Slack, Telegram, a leitura de e-mail, o Google, o Microsoft e os anexos ficam desligados até o token (ou o
host, o app OAuth, a pasta) ser preenchido; cada um tem `<SISTEMA>_MODO=simulado` para demo e testes, e destino só da
lista do .env. No Google e no Microsoft o `testar` só confere o app do .env; a conta é de cada pessoa. Nenhum dos dois foi
testado contra o serviço de verdade (README de cada um).

## Conector novo

1. Pasta `<nome>/` com `__init__.py`, `README.md` e `conector.py`: subclasse de `Conector` com `nome`, `rotulo`,
   `tipo`, `variaveis` (os nomes do .env que lê), `credencial`, `mensagem_desligada`, `como_ligar`, `dicas`
   (variável -> como corrigir), `variavel_modo` e `servicos` se fizer sentido, `conferir_configuracao(ambiente)`
   (levanta `ConfiguracaoInvalida("VARIAVEL")`) e `testar(ambiente)` (chamada de verdade, sem dado de lojista).
   Cada chamada de rede vai em `self.chamar(...)`, monta a URL com `cliente_http.montar_url` e usa
   `cliente_http.pedir`. Destino que vem do modelo passa por `self.exigir_destino(valor, lista_do_env)`.
2. `CONECTOR = registrar(SeuConector())` no fim do arquivo e o import em `integracoes/__init__.py`. 
3. Variáveis novas no `.env.example`, sem valor.
4. Testes contra um servidor local no formato do serviço real (`backend/tests/apoio_http.py`). O `conftest.py`
   aponta a suíte para servidores locais e recusa conexão fora do 127.0.0.1.
