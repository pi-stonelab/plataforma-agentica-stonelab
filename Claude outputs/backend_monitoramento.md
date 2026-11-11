# Registro de chamadas, destinos e executor

Para: Marcelo e Isabel (back-end), Enrico (monitoramento). De: Pedro (frente 4).
Nada aqui altera `app/`. Descreve o que nossa pasta entrega e o que vocês podem ligar.

## Formato do registro

Cada chamada de ferramenta gera um dict com exatamente estes campos (`CAMPOS_REGISTRO`):

- `momento`: data e hora em UTC, ISO, até os segundos.
- `execucao_id`, `passo`, `agente_id`: vêm do loop do agente (podem ser `None`).
- `ferramenta`: nome no catálogo, ou `"inexistente"`. Nunca o texto que o modelo enviou.
- `id_usuario`: identificador interno do funcionário.
- `integracoes`, `acesso`, `categorias_dados`: da ficha da ferramenta.
- `status` (`ok` ou `erro`) e `tipo_erro` (um dos 7 tipos padrão ou `None`).
- `camada_bloqueio`: `None`, `"agente"`, `"usuario"`, `"inativa"` ou `"desconhecida"`.
- `duracao_ms`.

Nunca entram argumentos, dados devolvidos, mensagem nem texto de exceção. `governanca.registrar`
descarta qualquer chave fora dessa lista.

## Como ligar o back-end e o monitoramento

    from ferramentas import governanca
    governanca.adicionar_destino(minha_funcao)   # recebe o dict do registro

Cada destino recebe uma cópia. Se o destino levantar erro, a chamada da ferramenta não cai e os outros
destinos continuam. Sem destino, o registro fica só na lista `governanca.REGISTROS` (últimas 1000,
em memória).
[aqui conectamos com o back-end: destino que grava no banco]
[aqui conectamos com o monitoramento (Enrico): destino que alimenta o painel]

## Sugestão de tabela

Uma linha por chamada, com uma coluna para cada campo acima e índice em `momento`, `id_usuario` e
`camada_bloqueio`. Não crie coluna para argumentos ou resposta.
[preencher: prazo de retenção da tabela, definir com Brenno]

## Sinal de tentativa bloqueada

Quando `camada_bloqueio` não é `None`, o modelo pediu algo que não podia. Para o modelo e o usuário, a
resposta é sempre "ferramenta inexistente"; para vocês, o campo diz o motivo real. Sugestão de alerta:
muitas chamadas bloqueadas do mesmo `id_usuario` ou `agente_id` em pouco tempo.
Atenção: `"desconhecida"` pode ser só o modelo errando o nome de uma ferramenta.

## Pedidos de ferramenta ausente

`solicitar_ferramenta_ausente` guarda os pedidos na lista `PEDIDOS` do `func.py` dela, em memória, e
os perde ao reiniciar.
[aqui conectamos com o back-end e o Jira: persistir pedidos, KAN-27]

## O executor chamando o catálogo

O executor do back-end deve chamar só `catalogo.executar(nome, argumentos, usuario,
ferramentas_do_agente, contexto)` e devolver o dict como está. Não chame `func.py` direto, porque
é o catálogo que aplica as duas camadas de acesso e o registro.
O `usuario` vem da sessão autenticada, nunca do corpo do pedido do modelo.
[aqui conectamos com o back-end: executor e registro de ferramentas, KAN-60 e KAN-32]
