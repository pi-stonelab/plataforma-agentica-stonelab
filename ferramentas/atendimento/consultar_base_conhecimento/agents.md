# consultar_base_conhecimento

Procura a resposta de uma dúvida frequente de lojista nos artigos de ajuda da Stone.

## Quando usar

Use quando o usuário trouxer uma dúvida geral, que vale para qualquer lojista, e quiser saber o que responder. Procure com uma ou duas palavras do assunto (`maquininha`, `antecipação`, `segunda via`). Responda com o que o artigo diz, com as suas palavras, e cite o código do artigo (como `KB015`).

## Quando não usar

Para o caso de um lojista específico (por que o dinheiro dele não caiu, quanto ele deve), use as ferramentas de lojista, como `consultar_liquidacoes_cliente` ou `listar_faturas_em_atraso`. Se nenhum artigo responder, diga que não encontrou: não responda de memória e não invente prazo, taxa ou regra.

## Parâmetros

- `termo` (texto, obrigatório): palavras do assunto, de 3 a 100 caracteres. Exemplo: `maquininha não liga`.
- `categoria` (texto, opcional): restringe a uma categoria de chamado, como `Maquininha`, `Recebimento` ou `Fatura e aluguel`. Exemplo: `Recebimento`.
- `limite` (inteiro, opcional): quantos artigos trazer, de 1 a 10. Se faltar, vêm 3. Exemplo: `2`.

## O que devolve

Em `dados`: `artigos`, `total_encontrado` e `truncado`. Cada artigo tem `codigo` (como `KB015`), `titulo_artigo`, `categoria`, `texto_artigo` e `atualizado_em` (AAAA-MM-DD). Os artigos vêm do mais relevante para o menos relevante. Lista vazia quer dizer que nenhum artigo trata do assunto.

Erros possíveis: `parametro_invalido` (termo com menos de 3 letras ou limite fora de 1 a 10).

## Para quem mantém

- Área: `atendimento` (KAN-14, caso de uso 1: responder dúvidas frequentes).
- Acesso: leitura.
- Integração:
  - `crm` (ver `integracoes/crm/README.md`): tabela `artigos_ajuda` do mock (`mock/consultas.py`, `buscar_artigos`, com busca por palavra inteira e sinônimos), lida por `dados_sinteticos.py`.
- Permissão: categoria `base_conhecimento`, comum a todos os cargos (`mock/regras.py`); qualquer área.
- Conteúdo de terceiros na saída: não (texto público escrito pela equipe).
- Situação: ativa, dados sintéticos (artigos KB001 a KB018, parafraseados das regras do DOC-MOCK).
