# Automações: desenho escrito (Sprint 3)

Este arquivo descreve como uma automação pode funcionar. Não há código dela. A implementação é da Sprint 3.

Uma automação é um agente que roda sozinho, em horários marcados, no lugar da pessoa que o criou. Exemplo do DOC-MOCK §9
(pedido 1): a analista de cobrança quer que, toda segunda, o sistema ache as faturas vencidas há mais de cinco dias e
escreva as mensagens de lembrete, para ela conferir antes de enviar.

## O que tem fonte e o que é proposta

Leia sempre com esta divisão em mente.

Com fonte:

- Os pedidos 1, 3, 4 e 6 do onboarding do DOC-MOCK §9 pedem execução agendada: cobrança toda segunda (pedido 1), aviso
  diário de chargeback a 2 dias do prazo (pedido 3), relatório de sexta do supervisor (pedido 4) e conferência diária
  das liquidações que falharam (pedido 6). Os comentários K28-ATU e K69-EXC da KAN-69 dizem que essa execução "fica só
  descrita". Por isso este arquivo existe e não há código.
- Nenhuma ação sai sem confirmação humana (DOC-MOCK §9, pedido de borda sobre aprovar acordos sozinho). Os pedidos 1 e 6
  já trazem a confirmação da analista.
- O agente roda com as permissões de quem o usa, não de quem o criou (KAN-28, KAN-69 E24; `CLAUDE.md` da raiz).
- O registro de cada chamada de ferramenta não guarda conteúdo, e a auditoria guarda só o id da pessoa
  (`ferramentas/governanca.py`, `seguranca/`).
- A única automação com decisão própria é outra: os pedidos de ferramenta ausente acumulam e vão uma vez por semana
  para um card único do Jira (BRIEFING, decisão 12). Hoje só existe o marcador no código
  (`solicitar_ferramenta_ausente` guarda até 1000 pedidos em memória).

Proposta do orquestrador, sem fonte no projeto (o Pedro decide):

- Tudo que vem depois sobre tabelas, quem dispara, limites e riscos. Os números estão marcados como sugestão.
- O que o back-end é obrigado a fazer em cada execução. Isso vem da regra de permissão de quem usa, mas o desenho
  concreto é nosso.

## Gatilhos

Só um gatilho na Sprint 3: agenda. Frequências dos pedidos de exemplo: diária e semanal, num dia da semana e hora.

Fica de fora, por não ter pedido nas fontes: gatilho por evento (por exemplo, chamado novo) e execução manual de teste.
A execução manual ("rodar agora") ajudaria a conferir a automação antes de agendar; sugestão, sem fonte.

Uma automação só existe se o agente existe e o dono ainda pode executá-lo. Se o agente é pausado, apagado ou muda
de visibilidade de um jeito que tira o acesso do dono, a automação para (ver "Permissões").

## Quem roda e com que permissão

A execução é em nome do dono da automação, com o cargo que ele tem na hora da execução. O cargo do dia da criação
não vale.

A cada execução, o back-end faz o mesmo que em um pedido do chat (`seguranca/CLAUDE.md`, "O que o back-end chama a
cada pedido"). Nada da execução anterior é reaproveitado:

1. Relê o dono no banco e no diretório do mock. Se o funcionário está `desligado` ou `afastado`, ou o perfil não
   existe mais, a execução não acontece. A automação é pausada e vira um evento de acesso negado.
2. Monta `seguranca.Usuario` e `governanca.Usuario` (por `governanca.usuario_do_cargo`) com o cargo e as carteiras de
   agora. Se o cargo mudou, o escopo muda junto.
3. Cria uma `Plataforma` nova, carrega o agente com `carregar_agente` e confere `Acao.EXECUTAR` no agente. Negado:
   a execução não acontece e a automação é pausada.
4. Gera um `execucao_id` novo, que vai ao evento, ao `contexto` das ferramentas e ao registro. É o fio que liga os
   três.
5. Roda `rodar_turno` com a pergunta fixa da automação. Os limites do motor valem como no chat: 10 passos, 3
   repetições da mesma chamada e 120 s (`agentes/CLAUDE.md`).
6. Guarda o resultado, o `tipo` e o `motivo` do `Turno` e a `trajetoria` (sem conteúdo).

O catálogo e a ferramenta continuam fazendo as outras checagens: categoria de dado do cargo, lojista na carteira, janela
de dias e máscara. Uma automação não vê nada que o dono não veria ao perguntar no chat.

## Só leitura e rascunho

Sem alguém olhando, nenhuma escrita roda. A automação:

- usa só ferramentas com `acesso` igual a `leitura` ou `calculo`;
- nunca usa ferramenta de escrita, mesmo que o agente a liste. Escrita hoje é inativa em todo caso, e a regra
  "o agente propõe, a pessoa confirma" (`CLAUDE.md` da raiz) continua valendo;
- entrega um rascunho ou um resumo para o dono ler e decidir. É o que os pedidos 1 e 6 descrevem.

O catálogo não tem hoje uma função que filtre as ferramentas de um agente pelo campo `acesso`. Quem implementar escreve
essa função em `ferramentas/catalogo.py` (é nossa) e a usa antes de chamar `rodar_turno`. Sem ela, o filtro ficaria
espalhado no back-end.

## Limites (sugestão, sem fonte)

Os números abaixo são ponto de partida. A QA ajusta depois de medir o modelo, como nos limites da KAN-38.

- Frequência mínima de uma vez por dia. Os exemplos do DOC-MOCK são diários ou semanais.
- Um número máximo de automações ativas por pessoa. O valor fica para o Pedro e a Milene (produto) decidirem.
- Parar a automação depois de algumas falhas seguidas (limite de passos, repetição, tempo ou modelo indisponível), com um
  aviso ao dono. Hoje o aviso ao dono não existe (V5 em `docs/decisoes.md`), então a primeira versão pode só mostrar o
  estado na tela.
- Nenhuma execução atrasada é recuperada. Se o servidor ficou parado na segunda de manhã, a automação roda uma vez na
  próxima janela, não várias.
- O uso do modelo de cada execução conta no limite de gasto da pessoa (KAN-16: aviso em 80%, aprovação do gestor para
  passar). Os valores do limite não têm fonte.

## Auditoria e rastro

Cada execução deixa o mesmo rastro de um turno de chat, com uma marca a mais:

- Evento de acesso (`Plataforma.autorizar`) com o `execucao_id`.
- Um registro por chamada de ferramenta (13 campos, sem argumentos nem dados).
- A `trajetoria`, com ação e nome, sem conteúdo.
- Uma marca de origem "automacao" ao lado do `execucao_id`. O DOC-MOCK §5.2 pede o canal no evento de auditoria (tela,
  API ou agente). "Automação" seria um valor novo (proposta).

O resultado em si pode conter dado do lojista, já mascarado. A sugestão é guardá-lo como mensagem numa conversa do dono
(tabelas `conversas` e `mensagens`, já previstas), marcada como automática, para o dono ler quando entrar. Quanto tempo
guardar: SEM FONTE (o prazo de retenção está em branco no código e nos cards).

## Tabelas novas (sugestão)

Duas, para o back-end avaliar. Nomes seguem o resto do projeto.

- `automacoes`: id, `agente_id`, `dono_id`, `agenda` (dia e hora), `pergunta` (texto fixo, sem dado de lojista), `ativa`,
  `ultima_execucao`, `motivo_pausa`.
- `automacao_execucoes`: id, `automacao_id`, `execucao_id`, `quando`, `tipo`, `motivo`.

A `pergunta` é texto escrito pelo dono. Ele não pode trazer código de lojista nem dado pessoal; o agente descobre o que
ler por conta própria, dentro da carteira do dono. Quem valida isso na criação: SEM FONTE.

## O que a automação reaproveita

- O motor `rodar_turno` e seus limites (`agentes/`). Nada novo no motor.
- O catálogo, a governança e a máscara (`ferramentas/`). Só a função de filtro por `acesso`, acima.
- A `Plataforma` por pedido, `carregar_agente`, `autorizar` e o gancho `ao_registrar` (`seguranca/`).
- O `montar_acesso` e o `LLMClient` que o back-end ainda vai escrever. A automação é mais um chamador deles.
- A tabela de auditoria, as de execução de ferramenta e as de conversa e mensagem que o `CLAUDE.md` da raiz prevê.

Quem agenda: o `CLAUDE.md` do Marcelo deixa de fora Redis e Celery de propósito (a meta final é um Raspberry Pi). A saída
mais simples, e só uma sugestão, é um laço no processo do back-end, iniciado no `lifespan`, que a cada minuto olha as
automações vencidas e roda uma por vez. Com uma instância só, um bloqueio no banco basta para não rodar a mesma
automação duas vezes. A escolha é do Marcelo e da Isabel.

## Riscos

- Texto de terceiros dentro de uma execução sem ninguém olhando. Um nome fantasia ou uma mensagem de chamado pode trazer
  instrução (cenário 7). A defesa é a de sempre (dado de terceiros vem como dado, máscara, só leitura), e vale mais aqui
  porque ninguém vê o erro na hora.
- Permissão que muda. O dono sai da equipe ou muda de cargo. A releitura a cada execução resolve; sem ela, a automação
  seguiria com o poder antigo.
- Uso demais do modelo. Muitas automações no mesmo horário competem com o chat. O planejado para o `LLMClient` é limitar
  cerca de 8 chamadas ao mesmo tempo (`CLAUDE.md` do Marcelo); as automações precisam respeitar a mesma fila e, de preferência,
  ceder lugar ao chat.
- Rascunho que vira ação sem querer. Se um dia houver ferramenta de escrita, ela continua fora das automações até haver
  confirmação por execução. Decisão para depois.
- Execução duplicada depois de reinício. Quem implementar precisa registrar a execução antes de rodar.
- Automação esquecida. Sem aviso ao dono (V5), uma automação que falha sempre só aparece na tela. Mostrar o estado da
  última execução ajuda.
- Automação do sistema (pedidos de ferramenta ausente) roda sem pessoa dona. Ela não pode usar a regra "permissão de
  quem usa". Tem de ser tratada à parte, com identidade da plataforma e só os campos agregados do pedido (sem texto
  livre), como a regra do Telegram da KAN-49 pede para avisos.

## Perguntas para o Pedro e o grupo

1. A Sprint 3 inclui código de automação, ou o desenho escrito já atende ao "fica só descrita" do Jira?
2. Quem implementa: Marcelo e Isabel (agenda, tabelas) com o Pedro (filtro de ferramentas) e Christopher e Isack (nada no
   motor)?
3. A pessoa recebe o resultado só na interface? E-mail ou Telegram para essa finalidade não têm fonte.
4. Quantas automações por pessoa, e com que frequência mínima?
5. O resultado fica quanto tempo guardado?
