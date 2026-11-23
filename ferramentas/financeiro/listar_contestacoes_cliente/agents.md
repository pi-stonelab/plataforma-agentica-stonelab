# listar_contestacoes_cliente

Lista os chargebacks e as devoluções de Pix (MED) de um cliente (lojista), com prazo, documentos pedidos e valor retido.

## Quando usar

Use quando o usuário perguntar por uma contestação de venda no cartão (chargeback) ou por um pedido de devolução de Pix, pelo prazo de defesa ou pelos documentos que o lojista precisa mandar. Destaque o prazo quando `dias_para_o_prazo` for pequeno.

## Quando não usar

Para as vendas, use `consultar_transacoes_cliente`. Para a taxa de chargeback da Stone no mês, use `consultar_taxa_contestacao_mensal`. Esta ferramenta não envia a defesa.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00002`.
- `limite` (inteiro, opcional): quantos de cada tipo trazer, de 1 a 50. Se faltar, vêm 20. Exemplo: `5`.

## O que devolve

Em `dados`: `codigo`, `chargebacks`, `total_de_chargebacks`, `casos_pix`, `total_de_casos_pix` e `truncado`. Cada chargeback tem `codigo` (como `CB00001`), `id_venda`, `motivo`, `data_notificacao`, `prazo_defesa`, `dias_para_o_prazo` (vazio quando o prazo já não corre), `valor` (o contestado), `valor_retido` (o líquido da venda, preso na agenda), `documentos_exigidos`, `documentos_enviados` e `situacao`. Cada caso de Pix tem `codigo` (como `PX00001`), `id_venda`, `data_abertura`, `prazo_contestacao`, `dias_para_o_prazo`, `valor` (o bloqueado), `motivo_alegado`, `tem_comprovante_entrega` e `situacao`. A defesa do chargeback vale até `prazo_defesa`; a contestação do Pix só vale para fraude ou golpe, nunca para arrependimento.

Erros possíveis: `parametro_invalido` (id fora do formato ou limite fora de 1 a 50), `permissao_negada` (cliente fora da sua carteira) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (cenários 2 e 10 do DOC-MOCK; regras no §7.6 e §7.7).
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): tabelas `chargebacks` e `casos_pix` do mock (sistema Disputas), lidas por `dados_sinteticos.py`.
- Permissão: categoria `disputa` (analista de disputas, especialista N2, supervisor de atendimento e coordenador financeiro, decisão A1) e escopo de carteira vêm do cargo (`mock/regras.py`).
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos.
