# conferir_liquidacoes

Confere, dia a dia, se cada depósito de um cliente (lojista) pagou o que a agenda mandava, e aponta as diferenças.

## Quando usar

Use quando o usuário quiser conferir as transações de um lojista e achar divergências, ou quando o lojista disser que um depósito veio menor ou não veio. Sem datas, confere os últimos 30 dias até ontem. Para cada divergência, diga o dia, quanto a agenda mandava, quanto foi pago e a explicação.

## Quando não usar

Para a lista de depósitos, use `consultar_liquidacoes_cliente`. Para as parcelas da agenda, use `consultar_agenda_recebiveis`. Esta ferramenta não corrige nada nem refaz a liquidação.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do cliente, `M` seguido de cinco dígitos. Exemplo: `M00013`.
- `data_inicio` (data, opcional): primeiro dia a conferir, no formato AAAA-MM-DD. Se faltar, são 30 dias até a `data_fim`. Exemplo: `2026-10-01`.
- `data_fim` (data, opcional): último dia a conferir, no formato AAAA-MM-DD. Se faltar, ontem; hoje nunca entra. Exemplo: `2026-10-14`.
- `limite` (inteiro, opcional): quantas divergências trazer, de 1 a 50. Se faltar, vêm 20. Exemplo: `5`.

## O que devolve

Em `dados`: `codigo`, `dias_conferidos` (quantos dias tinham agenda ou depósito), `divergencias`, `total_de_divergencias`, `truncado` e `janela_dias`. Cada divergência tem `data`, `agenda` (o que devia cair), `pago` (o que caiu), `diferenca` (pago menos agenda; negativa quando veio menos), `situacao` (`falhou`, `devolvida`, `sem_liquidacao` ou `paga`), `motivo_falha` e `explicacao` (o que aconteceu e o próximo passo). Lista vazia: todos os dias bateram. Valores em reais são texto como `-R$ 15,00`: repita sem converter.

Erros possíveis: `parametro_invalido` (id fora do formato, limite fora de 1 a 50 ou data_inicio depois de data_fim), `permissao_negada` (cliente fora da sua carteira, ou período antes da janela do seu cargo) e `nao_encontrado` (só para quem vê todas as carteiras).

## Para quem mantém

- Área: `financeiro` (KAN-14, caso de uso 5: conferir transações e apontar divergências; DOC-MOCK §7.2 e §7.3).
- Acesso: leitura.
- Integração:
  - `sql` (ver `integracoes/sql/README.md`): `agenda_e_liquidacoes_por_dia` do mock (seção do bloco C de `mock/consultas.py`): agenda do dia sem as parcelas antecipadas contra a soma das liquidações pagas.
- Permissão: categorias `agenda_recebiveis` e `liquidacao`, escopo de carteira e janela de 90 dias do atendente N1 vêm do cargo (`mock/regras.py`).
- Regra: o mock não desconta fatura da liquidação (decisão do bloco A), então qualquer diferença é divergência. Se um dia o mock descontar faturas, a conferência precisa somar esses descontos.
- Conteúdo de terceiros na saída: não.
- Situação: ativa, dados sintéticos (divergências plantadas: M00001 em 14/10, M00007 em 04/09 e M00013 em 14/10).
