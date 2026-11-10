# Revisão do orquestrador (10/11/2026)

## Resultado

Aprovado, com as correções abaixo já feitas. A pasta `ferramentas/` está pronta para entrar na branch dos agentes. O que falta depende de outras frentes e ficou marcado com colchetes.

## O que foi aprovado sem mudança

- Estrutura: 41 `func.py` (5 ativas e 36 esqueletos com a mesma forma), `base.py`, `catalogo.py`, `governanca.py` e `dados_sinteticos.py`. Nada foi criado fora de `ferramentas/`, `testes/`, `passagem/` e `relatorios/`.
- Segurança: a checagem tem duas camadas, ferramentas do agente e permissão do funcionário. Ferramenta bloqueada, inativa ou inexistente responde igual, e o motivo real só aparece no registro. O escopo de carteira é checado antes de buscar o dado. As consultas têm teto de 50 linhas. O registro não guarda conteúdo, e nada é impresso no terminal. O caminho de arquivo nunca vem do texto do modelo.
- Texto que o modelo lê: li o resultado de `ler` como se eu fosse o modelo. Nas 5 ativas o texto diz quando usar e quando não usar, traz parâmetros com exemplo e lista os erros possíveis. Não sobra nenhum colchete.
- Dados: todos sintéticos. Não há CPF, CNPJ, e-mail, telefone, URL de servidor nem segredo, e conferi isso com grep.

## O que mudei e por quê

1. `governanca.py`: um usuário sem `id_usuario` passava na checagem. Agora a função `_usuario_valido` exige `id_usuario` em texto e não vazio, além de nível e área válidos. A mesma função serve para `motivo_bloqueio` e `cliente_no_escopo`, então a regra está escrita num lugar só. Separei também a validação da ficha (`_ficha_valida`), para cada função fazer uma coisa.
2. Ruff: tirei os 42 comentários `# noqa: RUF012` e criei `ferramentas/ruff.toml`. Esse arquivo mantém as regras padrão do ruff, que são as mesmas do CI, e só ignora o RUF012. A regra reclama de dicionário dentro de classe, mas `parametros` é dado fixo da ficha e ninguém o altera durante a execução. Tentei pôr um `ruff.toml` também em `testes/`, mas ele mudava sem querer a ordenação dos imports, então tirei. Os dois `noqa` que ficaram em `base.py` (BLE001 e DTZ007) marcam escolhas de propósito, cada uma na linha em que acontece.
3. `consultar_saldo_conta` e `consultar_taxa_contestacao_mensal` voltaram a exigir N2. Saldo de conta e taxa de contestação são mais sensíveis que o resto. Os dois `.md` voltaram a dizer "só N2", e o documento para o Brenno explica essa exceção.
4. Legibilidade: em `base.py`, o registro de chamada virou um dicionário escrito campo por campo. Antes era `dict(..., **campos)`, uma linha densa demais para revisar. As listas fechadas (`TIPOS_ERRO`, `CATEGORIAS_DADOS`, `CAMPOS_REGISTRO` e outras) agora aparecem uma por linha, e as funções do catálogo ganharam docstring de uma linha. Os arquivos centrais cresceram um pouco (base 123, catálogo 111, governança 142 linhas), mas agora dá para ler cada um de cima para baixo.
5. `montar_registro` virou pública em `base.py`. Antes o catálogo importava um nome privado (`_montar_registro`) de outro módulo.
6. `LIMITE_PEDIDOS` (1000) ficou em `solicitar_ferramenta_ausente`. Sem ele, a lista de pedidos em memória cresce sem fim. Ganhou um teste.
7. Testes: tirei dois testes do roteiro que repetiam casos já cobertos em `test_catalogo.py` e uma checagem que só testava a própria regex. Acrescentei três casos de usuário sem `id_usuario` e o teste da fila cheia. O teste de limite de linhas agora usa tetos que não quebram a cada ajuste: 150 nos centrais, 24 nos esqueletos, 60 nas ativas e 1.600 no total.
8. `passagem/agentes_encaixe.md`: reescrito para bater com o protótipo do Christopher e do Isack. O documento mostra que cada passo deles (ler INDEX.md, ler TOOL.md, verificação agente + usuário, executar) vira uma chamada nossa. Explica que os usuários são só funcionários e traz um exemplo curto de `main.py` com o `Usuario` vindo da sessão e a lista de ferramentas do agente. Também justifica o nível de área. A ligação no `agente.py` deles ficou como `[preencher]`.

## Números finais

- 77 testes, 77 passam, em cerca de 0,7 s.
- Cobertura de `ferramentas/`: 96% no total. `base.py`, `dados_sinteticos.py` e as 5 ativas estão em 100%, `catalogo.py` em 96% e `governanca.py` em 95%.
- 7 de 7 tipos de erro exercitados.
- Ruff: os três comandos do plano estão limpos. O `ruff check .` do CI também passa numa cópia só com `ferramentas/` e `testes/`. Na raiz do sandbox aparecem 6 avisos, todos na cópia antiga `plataforma-agentica-stonelab/`, que não vai para o repositório.
- A auditoria das fichas (`/tmp/auditoria.py`) aponta só as duas ferramentas N2, que são exceção de propósito.
- Linhas: cerca de 1.480 de Python em `ferramentas/` e 1.000 em `testes/`. A meta de 700 para os testes não foi atingida porque o que sobra são casos de segurança.
- Arquivos: `ferramentas/` tem 109 (46 `.py`, 62 `.md` e o `ruff.toml`), `testes/` tem 7, `passagem/` tem 3 e `relatorios/` tem 2.

## Pendências com outras frentes

- Agentes (Christopher e Isack): chamar `ler` e `executar` no `agente.py` e definir `ferramentas_do_agente` na configuração de cada agente. Também cabe a eles alinhar o nome do arquivo (`agents.md` ou INDEX.md/TOOL.md) e fazer a pausa de confirmação antes de qualquer escrita.
- Segurança (Brenno): níveis, áreas e a classe `Usuario` oficiais (KAN-62), mascaramento (KAN-63), escopo de carteira (KAN-69), cofre de credenciais por funcionário e prazo de retenção dos registros.
- Back-end (Marcelo e Isabel): banco simulado no lugar de `dados_sinteticos.py` (KAN-32), um destino de registro que grave no banco, persistência dos pedidos de ferramenta (KAN-27) e o executor chamando `catalogo.executar`.
- Monitoramento (Enrico): um destino de registro para o painel e um alerta para chamadas bloqueadas (`camada_bloqueio`).
- Nosso: confirmar com o financeiro as taxas de multa e juros e, depois da demo, dar lógica aos 36 esqueletos.
