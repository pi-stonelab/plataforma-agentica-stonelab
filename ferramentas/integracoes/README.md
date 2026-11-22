# Integrações

Uma pasta por sistema que as ferramentas usam. Este material é para quem mantém o código. O agente não lê esta
pasta: ele só enxerga as ferramentas pelo catálogo.

## Como funciona

- `conector.py`: a classe `Conector`. Cada integração tem um, com o mesmo nome usado em `integracoes` nas fichas.
  O modo vem do .env, na hora de cada uso: `real` (fala com o serviço de verdade), `simulado` (sem rede, dados fixos)
  ou `desligado`. Valor estranho no .env desliga (falha fechada). Toda chamada de rede passa por
  `chamar(etapa, funcao, servico=...)`: 3 falhas seguidas pausam o serviço por 60 s, e passada a pausa uma chamada
  testa de novo. O log leva só integração, serviço, etapa e tipo do erro.
- `http.py`: o cliente HTTP de todos os conectores (httpx). HTTPS obrigatório fora do localhost; URL base do .env sem
  usuário, senha, parâmetro nem fragmento; redirecionamento só para a mesma origem; teto de 1 MB; 429, 5xx, JSON
  quebrado e tempo esgotado viram `ConnectionError` ou `TimeoutError` (a ferramenta responde
  `integracao_indisponivel`, sem detalhe).
- `registro.py`: a lista dos conectores e `estado_integracoes()`, uma linha por integração com `nome`, `rotulo`,
  `tipo` (`interno` ou `externo`), `modo`, `configurado`, `saude` (`ok`, `pausada`, `indisponivel` ou `desligada`) e
  as `ferramentas` que usam. Nenhum valor do .env aparece.
- `sistemas_internos.py`: os sistemas da Stone, que aqui são o mock (modo sempre `simulado`); a saúde vem de
  `mock.falhas`.
- `planejados.py`: as integrações que as fichas citam e que ainda não têm conector (aparecem `desligada`).

Terminal, na raiz do repositório:

    python -m ferramentas.integracoes estado
    MODO_TERMINAL=1 python -m ferramentas.integracoes testar apis_publicas

## Integrações

Internas (o mock, a Stone simulada):

- `crm/`: CRM de atendimento (cadastro e chamados).
- `sql/`: core de pagamentos, cadastro e cobrança.
- `bigquery/`: base analítica (ainda sem ferramenta ativa).
- `datahub/`: dicionário de dados (ainda sem ferramenta ativa).

Externas:

- `apis_publicas/`: ViaCEP e PTAX do Banco Central. Real.
- `email/`: envio por SMTP. Real.
- `jira/`, `slack/`, `telegram/`, `google_workspace/`, `microsoft_365/`, `anexos/`: ainda sem conector.

## Conector novo

1. Pasta `<nome>/` com `__init__.py`, `README.md` e `conector.py`: subclasse de `Conector` com `nome`, `rotulo`,
   `tipo`, `variaveis` (os nomes do .env que lê), `variavel_modo` e `servicos` se fizer sentido,
   `conferir_configuracao(ambiente)` (levanta `ConfiguracaoInvalida("VARIAVEL")`) e `testar(ambiente)` (chamada de
   verdade, sem dado de lojista). Cada chamada de rede vai em `self.chamar(...)` e usa `http.pedir`.
2. `CONECTOR = registrar(SeuConector())` no fim do arquivo e o import em `integracoes/__init__.py`. Tire a linha
   dele de `planejados.py`.
3. Variáveis novas no `.env.example`, sem valor.
4. Testes contra um servidor local no formato do serviço real (`backend/tests/apoio_http.py`). O `conftest.py`
   aponta a suíte para servidores locais e recusa conexão fora do 127.0.0.1.
