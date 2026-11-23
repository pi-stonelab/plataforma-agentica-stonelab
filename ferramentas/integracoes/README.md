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
  (OAuth, Sprint 3, marcado para o back-end); `exigir_destino` só aceita canal, chat ou projeto da lista permitida
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
- `planejados.py`: as integrações que as fichas citam e que ainda não têm conector (aparecem `desligada`).

Terminal, na raiz do repositório:

    python -m ferramentas.integracoes estado
    MODO_TERMINAL=1 python -m ferramentas.integracoes testar apis_publicas

## Integrações

Internas (o mock, a Stone simulada):

- `crm/`: CRM de atendimento (cadastro e chamados).
- `sql/`: core de pagamentos, cadastro, cobrança e disputas.
- `bigquery/`: base analítica (ainda sem ferramenta ativa).
- `datahub/`: dicionário de dados (ainda sem ferramenta ativa).

A QA derruba qualquer uma (inclusive `apis_publicas` e `email`) com `MOCK_FALHAS` no .env.

Externas:

- `apis_publicas/`: ViaCEP e PTAX do Banco Central. Real.
- `email/`: envio por SMTP. Real.
- `jira/`, `slack/`, `telegram/`, `google_workspace/`, `microsoft_365/`, `anexos/`: ainda sem conector.

## Conector novo

1. Pasta `<nome>/` com `__init__.py`, `README.md` e `conector.py`: subclasse de `Conector` com `nome`, `rotulo`,
   `tipo`, `variaveis` (os nomes do .env que lê), `credencial`, `mensagem_desligada`, `como_ligar`, `dicas`
   (variável -> como corrigir), `variavel_modo` e `servicos` se fizer sentido, `conferir_configuracao(ambiente)`
   (levanta `ConfiguracaoInvalida("VARIAVEL")`) e `testar(ambiente)` (chamada de verdade, sem dado de lojista).
   Cada chamada de rede vai em `self.chamar(...)`, monta a URL com `cliente_http.montar_url` e usa
   `cliente_http.pedir`. Destino que vem do modelo passa por `self.exigir_destino(valor, lista_do_env)`.
2. `CONECTOR = registrar(SeuConector())` no fim do arquivo e o import em `integracoes/__init__.py`. Tire a linha
   dele de `planejados.py`.
3. Variáveis novas no `.env.example`, sem valor.
4. Testes contra um servidor local no formato do serviço real (`backend/tests/apoio_http.py`). O `conftest.py`
   aponta a suíte para servidores locais e recusa conexão fora do 127.0.0.1.
