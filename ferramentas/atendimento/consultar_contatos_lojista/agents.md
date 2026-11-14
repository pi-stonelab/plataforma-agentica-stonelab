# consultar_contatos_lojista

Lista as pessoas de contato de um cliente (lojista), com nome, CPF, telefone e e-mail sempre mascarados.

## Quando usar

Use quando o usuário perguntar quem são os contatos do cliente ou pedir o CPF do sócio, e você já tiver o id_cliente. O CPF sai no formato `***.456.789-**`: repita assim, sem tentar completar.

## Quando não usar

Para os dados cadastrais (nome fantasia, segmento, cidade), use `consultar_cliente`. Esta ferramenta não devolve o dado completo para ninguém: se o usuário insistir no CPF, telefone ou e-mail inteiros, explique que a plataforma só mostra mascarado e não tente contornar. Não use para tarefas que não precisam de contato, como investigar uma liquidação.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00001`.

## O que devolve

Em `dados`: `codigo`, `contatos` e `total_encontrado`. Cada contato tem `id`, `papel` (socio, financeiro ou operador_caixa) e os campos mascarados `nome` (iniciais, como `F*** B***`), `cpf` (como `***.456.789-**`), `telefone` (como `(21) *****-4321`) e `email` (como `f***@lojistas.example`).

Erros possíveis: `parametro_invalido` (id fora do formato), `permissao_negada` (o cliente está fora da sua carteira; a resposta é a mesma quando o código não existe) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `atendimento`.
- Acesso: leitura.
- Integração:
  - `crm` (ver `integracoes/crm/README.md`): banco simulado do mock (`mock/consultas.py`), lido por `dados_sinteticos.py`
- Permissão: nível e área na ficha em func.py; categoria `contato` e escopo de carteira vêm do cargo (`mock/regras.py`) [aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62].
- Máscara: a ferramenta devolve o dado em claro e `Ferramenta.executar` mascara por campo (`CLASSIFICACAO_CAMPOS`); ver `mascara.py`. Na Sprint 2 ninguém vê o dado completo (O2).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, código em func.py, dados sintéticos.
