# verificar_identidade_contato

Confere se o telefone ou o e-mail de quem fala está no cadastro do cliente, sem mostrar o contato.

## Quando usar

Use antes de mostrar dado confidencial ou de encaminhar qualquer mudança, sempre que não estiver claro que quem fala é do lojista, e principalmente quando alguém pedir troca da conta de recebimento ou tiver pressa (é o golpe mais comum). Passe o telefone ou o e-mail que a pessoa usou para falar.

## Quando não usar

Para ver os contatos cadastrados do cliente, use `consultar_contatos_lojista` (e só se o usuário precisar deles para trabalhar). Esta ferramenta não troca a conta nem manda código de confirmação.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00006`.
- `telefone` (texto, opcional): o telefone de quem fala, com DDD. Exemplo: `(21) 90000-0606`.
- `email` (texto, opcional): o e-mail de quem fala. Exemplo: `contato@loja.example`.

Informe pelo menos um dos dois.

## O que devolve

Em `dados`: `codigo`, `confere` (verdadeiro ou falso), `papel` (o papel do contato que conferiu, como `financeiro`, ou vazio) e `orientacao` (o que fazer agora). Siga a `orientacao`. Se `confere` for falso, não mostre nenhum dado do cliente, não diga qual é o contato certo e, se houver pedido de troca de conta, recomende encaminhar o chamado ao N2 como suspeita de fraude.

Erros possíveis: `parametro_invalido` (id fora do formato, telefone sem DDD, e-mail inválido ou nenhum dos dois), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `atendimento` (cenário 6 do DOC-MOCK, o golpe da troca de conta; regra de identidade do §6.6).
- Acesso: leitura.
- Integração:
  - `crm` (ver `integracoes/crm/README.md`): `contato_confere` do mock compara só os dígitos do telefone e o e-mail sem caixa, e nunca devolve o contato.
- Permissão: categoria `contato` e escopo de carteira vêm do cargo (`mock/regras.py`). O telefone e o e-mail informados não vão para o registro (só metadados).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
