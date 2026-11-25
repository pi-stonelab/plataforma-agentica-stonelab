# listar_acordos

Lista os acordos de renegociação de dívidas com a Stone, de um cliente (lojista) ou de todos, por situação.

## Quando usar

Use quando o usuário perguntar pelos acordos de um lojista ou pelos acordos que esperam aprovação (`situacao` `pendente_aprovacao`). Diga a alçada de cada um: `analista`, `coordenador` ou `dupla_aprovacao` (duas pessoas aprovam e quem pediu nunca aprova).

## Quando não usar

Para montar uma proposta de acordo, use `calcular_parcelas`. Para as faturas em atraso, use `listar_faturas_em_atraso`. Esta ferramenta não aprova nem recusa acordo.

## Parâmetros

- `id_cliente` (texto, opcional): código do cliente, `M` seguido de cinco dígitos. Sem ele, vêm os acordos de todos os lojistas (só para quem vê todas as carteiras). Exemplo: `M00013`.
- `situacao` (texto, opcional): `pendente_aprovacao`, `ativo`, `quitado`, `quebrado` ou `recusado`. Exemplo: `pendente_aprovacao`.
- `limite` (inteiro, opcional): quantos acordos trazer, de 1 a 50. Se faltar, vêm 20. Exemplo: `10`.

## O que devolve

Em `dados`: `acordos`, `total_encontrado` e `truncado`. Cada acordo tem `codigo` (como `AC0001`), `id_cliente`, `faturas` (códigos), `valor_original`, `valor_renegociado`, `entrada`, `numero_de_parcelas`, `perdao_encargos`, `desconto_principal`, `alcada`, `id_solicitante`, `id_aprovador` (vazio enquanto ninguém aprovou), `criado_em` e `situacao`. Vêm do maior valor renegociado para o menor. Repita os valores sem converter.

Erros possíveis: `parametro_invalido` (id fora do formato, situação desconhecida, limite fora de 1 a 50, ou falta o id_cliente para quem só vê a própria carteira), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (onboarding 8 do DOC-MOCK: acordos esperando o coordenador; alçadas no §7.9).
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): tabela `acordos` do mock (`buscar_acordos`), lida por `dados_sinteticos.py`.
- Permissão: categoria `cobranca` e área `financeiro` (analista de cobrança e coordenador financeiro). Sem id_cliente, só quem vê todas as carteiras lista.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
