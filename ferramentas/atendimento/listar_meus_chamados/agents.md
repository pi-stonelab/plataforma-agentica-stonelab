# listar_meus_chamados

Lista os chamados abertos que estão atribuídos ao próprio funcionário, do prazo mais curto para o mais longo.

## Quando usar

Use quando o funcionário perguntar o que tem na sua fila, o que vence primeiro ou o que está atrasado. Para ver o histórico de um lojista, use `listar_chamados_cliente`.

## Quando não usar

Não use para a fila de outra pessoa (a ferramenta só devolve a de quem pergunta) nem para chamado resolvido ou fechado.

## Parâmetros

- `limite` (inteiro, opcional): quantos chamados devolver.

## O que devolve

Em `dados`: `chamados` (cada um com `codigo`, `protocolo`, `id_cliente`, `categoria`, `prioridade`, `situacao`, `aberto_em`, `prazo_em`, `dias_em_aberto` e `prazo_estourado`), `total_encontrado`, `truncado` e `atrasados`. Só entram lojistas da carteira do cargo.

Erros possíveis: `parametro_invalido` e `integracao_indisponivel`.

## Para quem mantém

- Área: `atendimento`, integração `crm`. A pessoa vem do `Usuario` montado pelo back-end, nunca do argumento.
