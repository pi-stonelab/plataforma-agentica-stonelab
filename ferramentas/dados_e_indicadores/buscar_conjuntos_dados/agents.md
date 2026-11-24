# buscar_conjuntos_dados

Procura as tabelas de dados da Stone pelo assunto e diz de que sistema cada uma é e se guarda dado restrito.

## Quando usar

Use quando o usuário perguntar onde fica um dado ("em que tabela ficam os chargebacks?") ou quais tabelas um sistema tem. Depois, use as outras ferramentas do dicionário para ver colunas, responsável e origem.

## Quando não usar

Esta ferramenta não lê nenhum dado, só descreve as tabelas. Para o dado de um lojista, use as ferramentas de atendimento e de financeiro.

## Parâmetros

- `termo` (texto, opcional): palavra no nome ou na descrição da tabela. Exemplo: `chargeback`.
- `sistema` (texto, opcional): só as tabelas de um sistema: `cadastro`, `core`, `cobranca`, `disputas`, `crm`, `diretorio` ou `analitica`. Exemplo: `disputas`.
- `limite` (inteiro, opcional): quantas trazer, de 1 a 20. Se faltar, vêm 10. Exemplo: `5`.

## O que devolve

Em `dados`: `conjuntos` (cada um com `tabela`, `sistema`, `nome_do_sistema`, `descricao_da_tabela`, `quantidade_de_colunas` e `tem_coluna_restrita`), `total_encontrado` e `truncado`.

Erros possíveis: `parametro_invalido` (sistema desconhecido ou limite fora de 1 a 20).

## Para quem mantém

- Área: `dados_e_indicadores`.
- Acesso: leitura.
- Integração:
  - `datahub` (ver `integracoes/datahub/README.md`): o dicionário gerado do esquema do mock (`dados_sinteticos.dicionario_de_dados`, via `ferramentas/dicionario.py`). Não lê linha nenhuma.
- Permissão: categoria `metadado` (todo cargo com área).
- Conteúdo de terceiros na saída: não.
- Situação: ativa.
