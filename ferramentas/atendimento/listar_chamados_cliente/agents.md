# listar_chamados_cliente

Lista os chamados de um cliente (lojista), do mais recente para o mais antigo, com categoria, prioridade, situação e há quantos dias estão abertos.

## Quando usar

Use quando o usuário quiser saber se o cliente já tem chamado aberto, qual a prioridade dele e há quanto tempo está parado, e você já tiver o id_cliente. Também serve para achar o `codigo` do chamado antes de ler as mensagens dele com `consultar_historico_contato`.

## Quando não usar

Para ler as mensagens de um chamado, use `consultar_historico_contato`. Esta ferramenta não traz o resumo nem o texto dos chamados, de propósito. Ela só lista: não abre, não atualiza nem fecha chamado.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00001`.
- `limite` (inteiro, opcional): quantos chamados trazer, de 1 a 50. Se faltar, vem 20. Exemplo: `5`.

## O que devolve

Em `dados`: `codigo`, `chamados`, `total_encontrado` e `truncado`. Cada chamado tem `codigo` (como `CH000061`), `protocolo`, `categoria`, `prioridade`, `situacao`, `aberto_por` (sistema, lojista ou funcionario), `aberto_em`, `dias_em_aberto` (vazio quando o chamado está fechado), `id_liquidacao` e `id_fatura` (preenchidos quando o chamado nasceu de uma liquidação ou de uma fatura; senão vazios). Se `truncado` for verdadeiro, há mais chamados do que o limite.

Erros possíveis: `parametro_invalido` (id fora do formato ou limite fora de 1 a 50), `permissao_negada` (o cliente está fora da sua carteira; a resposta é a mesma quando o código não existe) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `atendimento`.
- Acesso: leitura.
- Integração:
  - `crm` (ver `integracoes/crm/README.md`): banco simulado do mock (`mock/consultas.py`), lido por `dados_sinteticos.py`
- Permissão: nível e área na ficha em func.py; categoria `chamado` e escopo de carteira vêm do cargo (`mock/regras.py`) [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Conteúdo de terceiros na saída: não (sem resumo e sem mensagens, só códigos e listas fechadas).
- Situação: ativa, código em func.py, dados sintéticos. Antes se chamava `listar_tickets_cliente`; o nome mudou porque o mock, o DOC-MOCK e os gabaritos dizem "chamado".
