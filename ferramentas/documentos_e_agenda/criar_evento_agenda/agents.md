# criar_evento_agenda

Prepara um evento na agenda do próprio funcionário e deixa a prévia esperando a confirmação dele; nesta etapa nada é criado.

## Quando usar

Use quando o funcionário pedir para marcar uma reunião, um lembrete ou um bloqueio na agenda dele, com dia e hora
definidos. Convide só quem ele citar. Depois de usar, responda com FINAL dizendo que a prévia está esperando a
confirmação na tela. Nunca diga que o evento foi criado ou que os convites foram enviados: quem confirma é o
funcionário.

## Quando não usar

Não use para ver a agenda (`listar_eventos_agenda`), para agenda de outra pessoa nem para convidar lojistas ou
gente de fora da Stone: só e-mails dos domínios liberados nesta plataforma são aceitos. Não coloque CPF, cartão,
conta ou telefone de lojista no título nem na descrição; cite o código do lojista (como `M00001`).

## Parâmetros

- `titulo` (texto, obrigatório, uma linha, até 120 caracteres): o nome do evento.
- `data` (data, obrigatório): o dia, AAAA-MM-DD, de hoje até um ano à frente.
- `hora_inicio` (texto, obrigatório): HH:MM no horário de Brasília. Exemplo: `14:30`.
- `duracao_minutos` (inteiro, opcional): de 5 a 480. Padrão: 30.
- `convidados` (texto, opcional): até 5 e-mails separados por vírgula, dos domínios liberados.
- `local` (texto, opcional, até 100 caracteres): sala ou link da reunião.
- `descricao` (texto, opcional, até 500 caracteres): a pauta. A assinatura do funcionário é acrescentada.
- `servico` (texto, opcional): `google` ou `microsoft`. Só use se a ferramenta pedir.

## O que devolve

Em `dados`: `confirmacao_id`, `situacao` (`aguardando_confirmacao`), `expira_em` (a prévia vale 15 minutos),
`servico` (a conta), `titulo`, `quando`, `local`, `convidados`, `texto` e `aviso` (modo de demonstração e
convite que sai da plataforma).

Erros possíveis: `parametro_invalido` (hora fora do formato, data no passado ou longe demais, convidado fora dos
domínios liberados, mais de 5 convidados), `integracao_indisponivel` (conta não ligada, sem a permissão de
escrever na agenda, serviço fora do ar ou prévias demais esperando confirmação).

## Para quem mantém

- Área: `documentos_e_agenda`. Acesso: escrita em duas fases (`ferramentas/confirmacoes.py`), listada em
  `governanca.ESCRITA_COM_CONFIRMACAO`. Categoria `agenda_pessoal`.
- Fase 2: `efetivar` cria o evento na conta da pessoa (`calendar.events` no Google, `Calendars.ReadWrite` na
  Microsoft), com um id nosso para o pedido repetido não duplicar. O Google avisa os convidados por e-mail.
- Convidados: o domínio tem de estar em `ESCRITORIO_DOMINIOS` (`exigir_destino`), na prévia e de novo ao criar.
- Integração: `google_workspace` ou `microsoft_365`, alternativas; conta OAuth de cada pessoa.
- Situação: ativa. Nos testes, servidores locais no formato das duas APIs.
