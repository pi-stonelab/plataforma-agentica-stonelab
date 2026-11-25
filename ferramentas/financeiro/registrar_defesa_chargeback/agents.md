# registrar_defesa_chargeback

Prepara o registro dos documentos de defesa de um chargeback do lojista. Nada é gravado antes da confirmação do funcionário.

## Quando usar

Use quando o funcionário de Disputas já tiver conferido os documentos que o lojista mandou e quiser registrá-los na defesa de um chargeback que ainda aguarda a defesa (veja o prazo e os documentos que faltam com `listar_contestacoes_cliente`). Com todos os documentos que o motivo exige, o caso segue para a análise; com menos, continua aguardando a defesa até o prazo. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use depois do prazo (a ferramenta recusa), para chargeback que já está em análise ou encerrado, nem para documento que o motivo não pede. Esta ferramenta não envia a defesa à bandeira: só registra no cadastro da Stone o que o lojista entregou.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00002`.
- `id_chargeback` (texto, obrigatório): código do chargeback. Exemplo: `CB00001`.
- `documentos` (texto, obrigatório): documentos a registrar, separados por vírgula, como a consulta de contestações os mostra. Exemplo: `Nota fiscal, Comprovante de entrega`.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_chargeback`, `motivo`, `prazo_defesa`, `documentos_a_registrar`, `documentos_ja_registrados`, `documentos_que_faltam` e `o_que_acontece`.

Erros possíveis: `parametro_invalido` (código fora do formato, documento desconhecido ou que o motivo não pede, documento já registrado, prazo vencido ou chargeback que já não aguarda a defesa), `nao_encontrado` (chargeback que não é do lojista), `permissao_negada` (lojista fora do escopo) e `integracao_indisponivel`.

## Para quem mantém

- Área: `financeiro`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- `mock/escritas.registrar_defesa_chargeback`: grava `documentos_enviados` e, quando não faltam documentos, muda a situação para `em_analise`. O privilégio de escrita é só nessas duas colunas de `chargebacks` (`PRIVILEGIOS_DE_ESCRITA`).
