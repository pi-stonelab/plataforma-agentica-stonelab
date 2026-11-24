# adicionar_nota_chamado

Prepara uma nota interna ou uma resposta ao lojista num chamado. Nada acontece antes da confirmação do funcionário.

## Quando usar

Use quando o funcionário pedir para registrar um resumo, uma observação ou a resposta que vai ao lojista num chamado existente. Escreva só com o que veio das outras ferramentas. O texto entra no histórico como escrito pelo agente e revisado por quem confirmou. Depois de usar, responda com FINAL dizendo que a prévia está esperando a confirmação na tela.

## Quando não usar

Não use para abrir um chamado novo (use `abrir_chamado`) nem para mudar a situação do chamado (use `atualizar_situacao_chamado`).

## Parâmetros

- `id_cliente` (texto, obrigatório): código do lojista. Exemplo: `M00001`.
- `id_chamado` (texto, obrigatório): código do chamado. Exemplo: `CH000061`.
- `texto` (texto, obrigatório, até 2000 caracteres): a nota ou a resposta, em português e sem CPF, cartão ou conta completos.
- `tipo` (texto, opcional): `nota_interna` (padrão, só a equipe vê) ou `resposta_ao_lojista` (vai pelo canal em que ele falou por último).

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em`, `id_cliente`, `id_chamado`, `tipo_da_nota` e `texto` (mascarado).

Erros possíveis: `parametro_invalido` (texto vazio, tipo desconhecido, chamado fechado na confirmação), `nao_encontrado` (chamado de outro lojista ou inexistente), `permissao_negada` (lojista fora da sua carteira) e `integracao_indisponivel` (CRM fora do ar).

## Para quem mantém

- Área: `atendimento`. Escrita em duas fases, listada em `governanca.ESCRITA_COM_CONFIRMACAO`.
- "Resumo gerado por IA só entra no histórico depois da revisão do atendente" (KAN-69): é exatamente a confirmação. A interação fica com autor `agente` e `id_funcionario` de quem confirmou (DOC-MOCK §6.8).
- Chamado fechado não recebe nada (§6.5): a gravação recusa.
- LGPD: texto pela máscara de texto livre antes da prévia; o registro guarda só metadados.
