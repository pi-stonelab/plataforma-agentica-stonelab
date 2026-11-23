# atualizar_situacao_chamado

Prepara mudança de situação, encaminhamento ou suspeita de fraude num chamado. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando o funcionário pedir para pegar, pausar, resolver ou reabrir um chamado, para subir o chamado de nível, ou para marcar suspeita de fraude. Marque suspeita de fraude quando alguém fora do cadastro pede troca de conta ou dados (confira com `verificar_identidade_contato`): o chamado sobe para o N2 e nenhum dado é passado ao contato. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use para escrever no histórico (use `adicionar_nota_chamado`). Fechar o chamado não é com você: o sistema fecha 7 dias depois de resolvido. O caso da ouvidoria só a ouvidoria resolve.

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00006`.
- `id_chamado` (texto, obrigatório): código do chamado. Exemplo: `CH000063`.
- `nova_situacao` (texto, opcional): `em_atendimento`, `aguardando_lojista`, `aguardando_area_interna` ou `resolvido`.
- `encaminhar_para` (texto, opcional): `N2` ou `supervisor` (só para cima).
- `suspeita_fraude` (texto, opcional): `sim` para marcar suspeita de fraude.

Mande ao menos um dos três opcionais.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_chamado`, `situacao_atual`, `nova_situacao`, `encaminhar_para` e `suspeita_fraude`.

Erros possíveis: `parametro_invalido` (nada a mudar, situação ou destino desconhecidos; na confirmação, passagem fora do ciclo), `permissao_negada` (lojista fora da carteira; na confirmação, chamado de nível acima do seu ou caso da ouvidoria), `nao_encontrado` e `integracao_indisponivel`.

## Para quem mantém

- Área: `atendimento`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- As regras do ciclo (§6.5, `regras.TRANSICOES_DO_CHAMADO`), do nível de quem mexe, da ouvidoria (cenário 9) e da suspeita (§6.6, cenário 6) ficam em `mock/escritas.atualizar_chamado` e são conferidas na confirmação, com o cargo lido do diretório.
