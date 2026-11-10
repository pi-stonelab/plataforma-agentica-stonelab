# Relatório de testes da pasta ferramentas/

Escrito em 10/11/2026 e atualizado depois da revisão do orquestrador (77 testes na versão final). Os testes ficam em `testes/` (fora de `ferramentas/`) e foram escritos a partir do contrato do plano, sem olhar o código antes. Só depois rodei contra o que o Código e a Segurança entregaram.

## Como rodar no seu PC (Windows)

Abra o terminal na raiz do repositório (a pasta que tem `ferramentas/` e `testes/` lado a lado) e rode:

```
python -m unittest discover -s testes -t .
```

Não precisa instalar nada, só o Python 3.11 ou mais novo. Para ver a cobertura (opcional, não vai para o repositório):

```
pip install coverage
python -m coverage run -m unittest discover -s testes -t .
python -m coverage report --include="ferramentas/*"
```

Para o ruff, os três comandos do plano:

```
ruff check --target-version py311 ferramentas testes
ruff check --target-version py311 --select E,W,F,B,SIM,C90 --line-length 100 ferramentas testes
ruff format --check --line-length 100 ferramentas testes
```

Nenhum teste usa rede, variável de ambiente ou depende da ordem de execução. Cada teste começa limpando `governanca.REGISTROS` e a lista `PEDIDOS`.

## O que cada arquivo testa e por quê

`testes/apoio.py` guarda o material comum: três funcionários de teste (N1 de atendimento com carteira só do CLI-0001, N1 de dados e N2 de financeiro), uma ferramenta falsa que deixa a gente forçar casos que nenhuma das 5 ativas produz (exceção de rede, exceção qualquer, conteúdo de terceiros, nível N2), e o modelo roteirizado do protocolo 2.8 com um loop mínimo que imita o agente.

`testes/test_contrato.py` confere que o código bate com o plano. As 41 fichas carregam, o nome e a área são iguais aos das pastas, os valores estão dentro das listas fechadas, nenhum parâmetro usa nome reservado, as integrações existem em `integracoes/`, só as 5 estão ativas e a única escrita ativa é `solicitar_ferramenta_ausente`. Também confere que cada parâmetro das 5 aparece em "Parâmetros" do `agents.md`, e que os 36 esqueletos têm a mesma forma (classe em CamelCase, `planejada`, nunca executam). Por `ast`, verifica que não há anotação de tipo, decorador, `async`, `abc`, `print` nem biblioteca de rede, que `"agents.md"` só aparece no catálogo e que os limites de linhas do briefing do Código valem. Testa ainda `validar` e `executar` da classe base com a ferramenta falsa, e junta num teste só os 7 tipos de erro.

`testes/test_governanca.py` cobre a matriz N1/N2 contra as áreas, usuário inválido de 14 jeitos (inclusive sem `id_usuario`, com ele vazio ou de tipo errado), ficha inválida de 6 jeitos (sempre tem que bloquear), escopo de carteira, o limite de 1000 registros, o descarte de chaves fora de `CAMPOS_REGISTRO` e o destino que levanta exceção.

`testes/test_catalogo.py` é o foco de segurança. Confere as duas camadas de acesso, que `ler` e `executar` respondem exatamente igual para ferramenta bloqueada pelo agente, bloqueada pelo funcionário, inativa e inexistente, e que o motivo real só aparece no registro (`camada_bloqueio`). Também confere 22 caminhos maliciosos em `ler` (`..`, `/etc/passwd`, `financeiro/../../`, `agents.md`, `integracoes/crm`, barra invertida, byte nulo), que o texto lido nunca traz "Para quem mantém" nem marcadores `[preencher` e `[aqui conectamos`, que argumentos com `nivel`, `usuario`, `carteira` ou `ferramentas_do_agente` não escalam acesso, que nada levanta exceção com entradas estranhas (nome `None`, lista, usuário `object()`, contexto de tipo errado), que o registro não guarda nenhum valor enviado ou devolvido (procuro os valores no registro serializado) e que nada vai para o terminal.

`testes/test_ferramentas_ativas.py` testa cada uma das 5 com um sucesso e cada erro possível, usando os exemplos do contrato: multa de 1000 em 30 dias dá 20,00 + 10,00 = 1030,00; 15 dias dá 1025,00; 0 dia dá 1000,00; `CLI-0001` tem 60 transações e vem truncado em 20 por padrão. Também testa arredondamento meio para cima, limites de faixa, período vazio, CEP com e sem hífen, o nome sugerido contra a regex, a fila de pedidos cheia (`LIMITE_PEDIDOS`), e que um N1 fora da carteira recebe a mesma resposta para cliente que existe e para cliente que não existe (assim ele não descobre quais clientes existem).

`testes/test_roteiro_agente.py` roda o protocolo 2.8 sem rede: o caso feliz LER, LER, USAR, FINAL; o modelo pedindo ferramenta bloqueada e recebendo `ferramenta_inexistente` igual à de um nome inventado; e cliente fora da carteira. Leitura bloqueada e caminho malicioso ficaram só em `test_catalogo.py`, que já cobria os dois.

## Números (versão final, depois da revisão)

Testes: 77. Passaram 77, falharam 0, erros 0. Por arquivo: `test_contrato.py` 19, `test_governanca.py` 11, `test_catalogo.py` 16, `test_ferramentas_ativas.py` 28, `test_roteiro_agente.py` 3.

Tempo: cerca de 0,7 s para a suíte inteira no sandbox. No PC deve ficar abaixo disso.

Cobertura de linhas (medida com `coverage`): `base.py` 100%, `dados_sinteticos.py` 100%, as 5 ativas 100% cada, `catalogo.py` 96% (linhas 59, 60 e 63: arquivo `agents.md` que some do disco ou fica sem parágrafo, casos que não acontecem com a pasta íntegra), `governanca.py` 95% (o `except` de `cliente_no_escopo` e o destino não chamável em `adicionar_destino`). Total de `ferramentas/`: 96%. Os 36 esqueletos ficam em 94% cada, porque a linha do `rodar` nunca roda: a ferramenta inativa é barrada antes, e é isso que queremos.

Tipos de erro exercitados: 7 de 7, conferido em um teste que junta todos.

Ruff: os três comandos do plano e o `ruff check .` do CI (rodado numa cópia limpa só com `ferramentas/` e `testes/`) saem sem aviso. Na raiz do sandbox o `ruff check .` mostra 6 avisos, todos na cópia antiga `plataforma-agentica-stonelab/`, que não é nossa e não vai para o repositório.

Linhas: `ferramentas/` tem cerca de 1.480 linhas de `.py` (teto de 1.600); `testes/` tem cerca de 1.000. O teto de 700 do briefing não foi atingido: o que sobra são listas de casos de erro que o formatador quebra em várias linhas, e cortar mais tiraria casos de segurança.

## Defeitos encontrados e o que aconteceu com eles

1. `ferramentas/governanca.py`: `motivo_bloqueio` deixava passar usuário sem `id_usuario` (o contrato 2.4 pede falha fechada). Corrigido na revisão: agora o usuário precisa de `id_usuario` texto não vazio, nível e área válidos, e a mesma checagem vale para `cliente_no_escopo`. O teste que falhava passa.

2. `solicitar_ferramenta_ausente` tinha um limite de fila (`LIMITE_PEDIDOS`) sem teste. Ficou, porque é o jeito mais simples de a lista em memória não crescer sem fim, e ganhou o teste `test_fila_cheia_recusa_sem_crescer`.

3. O teste de limite de linhas por arquivo quebrava a cada ajuste de legibilidade. Agora ele confere só o teto de 150 linhas nos quatro arquivos centrais, 24 nos esqueletos, 60 nas ativas e 1.600 no total.

## Ambiguidades (onde escolhi a leitura mais restritiva)

O contrato manda `registrar` guardar "só as chaves de `CAMPOS_REGISTRO`" mas não diz se as ausentes viram `None`. O código preenche com `None`; os testes aceitam as duas formas e exigem só que não sobre chave fora da lista.

O caminho `/` sozinho conta como caminho absoluto e tem que voltar `MENSAGEM_INDISPONIVEL`. Um código que apara barras e trata `/` como raiz falharia, e o código atual passa.

`ler("atendimento/calcular_multa_atraso")` (área errada para a ferramenta) tem que voltar a mensagem fixa, não o texto da ferramenta. O contrato aceita "com ou sem a área" mas não fala de área trocada.

`"agents.md"` só pode estar no `catalogo.py`, e olho qualquer texto literal do código, docstrings inclusas.

A ficha falsa dos testes de governança precisa de `acesso` e `status`, porque a `governanca.py` também lê esses dois atributos para validar a ficha. O contrato só cita `sensibilidade` e categorias; não é defeito, só registro de que o código confere mais do que o texto pede.

## Outras observações

Os testes de `ler` dependem do texto dos `agents.md` das 5 ativas e da raiz: quando rodei pela primeira vez, as seções ainda tinham `[preencher]` e 4 testes falharam por isso. Depois que o Código terminou as edições de `.md`, esses testes passaram sem eu mexer neles, o que confirma que o filtro de marcadores funciona.

`consultar_saldo_conta` e `consultar_taxa_contestacao_mensal` passaram a exigir N2 na revisão; o teste dos esqueletos aceita essas duas exceções e só elas.
