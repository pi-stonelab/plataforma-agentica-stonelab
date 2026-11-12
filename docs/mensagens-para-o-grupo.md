# Mensagens para o grupo

Textos prontos para o Pedro mandar. Cada mensagem diz o que mudou na pasta da pessoa ou no que ela usa, o que ajudaria
fazer e o que pode quebrar. Nada aqui foi enviado nem postado. O Pedro lê, ajusta e decide quando mandar.

O que vale para todas:

- O trabalho está na branch `integracao/seguranca-banco`. Por decisão do Pedro (D1), o PR nosso só sai depois que os PRs
  #10, #11 e #12 entrarem.
- Código de `backend/` não foi alterado. O que entrou em `backend/` são testes, em `backend/tests/`.
- Os comentários sugeridos para o Jira ficam no fim, um por assunto. Nenhum foi postado.

## Para o Marcelo

Oi, Marcelo. Montamos a parte de ferramentas, mock, segurança e agentes em cima do seu esqueleto e do seu `CLAUDE.md`.
Não mexemos em nada de `backend/app/`.

O que mudou e te afeta:

- O `CLAUDE.md` da raiz foi alinhado ao código que existe hoje, com a autorização do Pedro. Corrigimos só o que
  contradizia o código (por exemplo, `MAX_PASSOS` agora é 10, o agente roda por `rodar_turno`, a `Plataforma` é criada
  por pedido, e há 43 ferramentas, 11 ativas). Acrescentamos duas seções: "Como as quatro pastas se encaixam" e "O que a
  etapa do back-end precisa fazer". Se algum trecho não fizer sentido para você, pode desfazer ou reescrever.
- A segunda dessas seções lista doze pontos que o back-end liga: `montar_acesso`, `Plataforma` por pedido com
  `carregar_agente`, orquestrador decorado, `adicionar_destino` e `ao_registrar`, o `LLMClient` com a assinatura
  `(prompt_sistema, prompt)`, o `stop` em `"Observação:"`, o estado da conversa guardado no servidor, entre outros. Os
  nomes que ainda não existem no código (`montar_acesso`, `executar_agente`, `gravar_evento`) são do rascunho da
  arquitetura e podem mudar como você achar melhor.
- Os dados do mock moram em outro banco (`MOCK_DATABASE_URL`, criado por `python -m mock.gerar`). Por isso as tabelas
  `clientes` e `transacoes` saíram do plano.
- Entraram testes novos em `backend/tests/` (arquivos `test_*.py` e apoios). Rodam com `cd backend && python -m pytest -q`.
- Sobre a sua branch `backend/llm-client`: o motor do agente agora aceita as duas formas de `chamar_modelo`, a de um
  argumento, `(prompt)`, que o seu `como_chamar_modelo(sistema=...)` devolve, e a de dois, `(prompt_sistema, prompt)`.
  Então o primeiro teste de `test_agente_com_llm_client.py` passa sem você mudar nada. O segundo precisa de três
  ajustes nos dados do teste, porque a ferramenta e o usuário mudaram: usar o lojista `M00001` no lugar de `CLI-0001`,
  montar o usuário com `governanca.usuario_do_cargo("F0011", "coordenador_financeiro", ())` e chamar
  `apoio_agente.mundo()` antes, para ligar o mock às ferramentas. Para o modelo não inventar o resultado da ferramenta,
  passe `opcoes={"temperature": 0, "stop": ["Observação:"]}` ao `como_chamar_modelo`.

O que pode quebrar:

- O CI (`.github/workflows/ci.yml`) só roda gitleaks e ruff. Os testes novos não rodam lá ainda.
- `pyjwt` e `bcrypt` estão no `requirements.txt` da raiz e não no de `backend/`.
- O `create_all` não cria as tabelas do mock.
- Se `usuarios` guardar cargo e carteira, as duas fontes podem divergir do diretório do mock. A pergunta está no fim da
  seção de tabelas do `CLAUDE.md`.

Dúvida que fica com você: o `POST /conversas/{id}/mensagens` terá chave de pedido para não rodar duas vezes? Não achamos
isso desenhado.

## Para a Isabel

Oi, Isabel. Resumo do que muda nas tabelas e no seed.

- A tabela `agentes` precisa de `visibilidade` (`privado`, `convidados`, `publico`), `dono_id` e `area` que pode ficar
  vazia (o agente geral não tem área). A tabela `auditoria` guarda `id_usuario` e `execucao_id`, nunca o nome da pessoa.
  Os campos estão no `CLAUDE.md` da raiz.
- Cargo, área, carteiras e situação (ativo, afastado, desligado) do funcionário vêm do diretório do mock
  (`buscar_funcionario`). O `seed` da plataforma pode ler daí para criar os `usuarios`. Se a tabela guardar uma cópia,
  vale combinar com o Marcelo qual das duas fontes manda.
- Pessoa real só se for necessário. Para testar com colegas existe o mecanismo no mock (um CSV local fora do Git,
  descrito em `mock/CLAUDE.md`). Nome e e-mail reais não entram no Git nem no seed.
- Os dados sintéticos não vão para as tabelas da plataforma. Vão para o banco do mock (`MOCK_DATABASE_URL`).

O que pode quebrar:

- Sem Alembic na Sprint 2, mudar uma tabela quer dizer apagar o banco e rodar o seed de novo (regra do `CLAUDE.md`).
- A branch `misabelalbponte-crypto-patch-2` ainda não foi alinhada à estrutura nova. Posso ajudar se quiser.

Não conseguimos ler o conteúdo dos PDFs da KAN-32. Se existir uma versão em texto do modelo de dados, nos ajudaria a
conferir.

## Para o Brenno

Oi, Brenno. Mexemos em `seguranca/` com a liberação do Pedro, para encaixar com ferramentas e agentes. A demo
(`python seguranca/permissoes.py`) continua rodando e há testes novos em `backend/tests/test_seguranca_*.py`.

O que mudou:

- Visibilidade: `PRIVADO`, `CONVIDADOS` e `PUBLICO`, escolhida pelo dono. Convidar só vale em `CONVIDADOS`.
- Dois perfis novos: `Auditor`, que lê a auditoria e mais nada, e `AdminGlobal` mais restrito, que pausa agentes
  e não executa nem vê privado. Área é opcional para os dois.
- A `Plataforma` agora vale para um pedido. O back-end cria uma por pedido, com `carregar_agente` para agentes que vêm
  do banco e `ao_registrar` para gravar a auditoria.
- `Evento` guarda só o id da pessoa, mais o `execucao_id`. Nunca o nome.
- `autorizar` decide sobre o agente registrado e nega agente forjado ou não registrado.
- Mudar visibilidade e deprecar passam por métodos que autorizam e gravam evento.
- Existe agente geral: `Agente.da_plataforma(nome)`.
- O decorator aceita `plataforma` e `execucao_id` como parâmetros da função decorada.

O que pode quebrar:

- Quem usava `Agente.dono` ou `Agente.convidados` precisa trocar por `dono_id` e `convidados_ids` (ids em texto).
- `Usuario.criar_agente` e `eh_dono_ou_convidado` saíram. Criar agente é `Plataforma.registrar`.
- `Evento.usuario` virou `Evento.id_usuario`.
- O inteiro `nivel` ficou sem uso, e a ordem dele é a inversa de N1 e N2. Não o compare com as ferramentas.

Para você decidir: o `README` ainda marca como "a confirmar" se o Supervisor da área executa os agentes abertos ou só os
gerencia (hoje executa). A mudança, se vier, é em `_gerencia`.
Pendências para a Sprint 3: `REPLICAR`, limpar convidados ao sair de `CONVIDADOS`, reativar agente pausado.
O resumo de tudo está em `seguranca/CLAUDE.md`.

## Para o Christopher e o Isack

Oi, Christopher e Isack. Mexemos em `agentes/` com a liberdade que o Pedro tem nessa pasta e deixamos tudo anotado
em `agentes/CLAUDE.md`. Vale uma olhada.

O que mudou no motor (`agentes/agente_atendimento/agente.py`):

- Um turno por chamada: `rodar_turno(pergunta, usuario, ferramentas_do_agente, chamar_modelo, historico, estado,
  contexto, prompt_sistema)`, que devolve `Turno(resposta, tipo, trajetoria, estado, motivo)`.
- `PERGUNTAR` devolve a pergunta e encerra o turno, sem `input()`. O estado da conversa volta para quem chamou.
- Limites da KAN-38: 10 passos, 3 repetições iguais seguidas. Acrescentamos um prazo de 120 s por turno, que não tem
  fonte e precisa ser medido com o modelo real.
- Logs e `trajetoria` sem conteúdo: só ação, nome da ferramenta e resultado.
- `BASE_URL` e `MODELO` saíram do motor. O `chamar_modelo` recebe `(prompt_sistema, prompt)`.
- O modo terminal foi para `agentes/terminal.py`, só roda com `MODO_TERMINAL=1` e lê o usuário do diretório do mock
  pelo `ID_USUARIO` do `.env`.
- Existe um agente geral em `agentes/agente_geral/`, que usa o mesmo motor com todas as ferramentas do catálogo.
- Os prompts mandam escolher a ferramenta na lista do índice e ler a ficha direto.

O que pode quebrar:

- Quem chamava `agente(pergunta, usuario, chamar_modelo)` ainda funciona (a função ficou para testes e terminal), mas o
  caminho do produto é `rodar_turno`.
- `NIVEL`, `AREA` e `CARTEIRA` do `.env` não valem mais. O nível, a área e a carteira vêm do cargo.
- A lista `FERRAMENTAS_DO_AGENTE` do atendimento continua com 5 nomes (KAN-55). As seis ferramentas novas só entram se
  vocês as incluírem.
- A suíte do agente mudou de lugar: `backend/tests/test_agente_*.py`.

Perguntas para vocês: o que acontece quando o turno passa de 10 passos (hoje devolve uma mensagem fixa e o motivo
`max_passos`)? Como querem guardar o `Turno.estado` entre mensagens? Fica com o back-end, por conversa.

## Comentários sugeridos para o Jira (não postados)

Um por assunto. O Pedro decide se posta, onde e com que texto. Os números dos cards vêm do `CLAUDE.md` da raiz e dos
documentos da pesquisa. O Pedro confere cada um antes.

1. Segurança (card da frente 6, KAN-62).

   > Integramos `seguranca/` com ferramentas e agentes, na branch de integração. Entraram visibilidade
   > (privado, convidados, público), perfis Auditor e Admin, `Plataforma` por pedido com gancho de auditoria, agente geral
   > e eventos só com id. A demo continua rodando. Alguns nomes mudaram (`dono_id`, `convidados_ids`, `Evento.id_usuario`).
   > Detalhes em `seguranca/CLAUDE.md`. Pendências: REPLICAR, reativar agente pausado e rota de leitura da auditoria.

2. Back-end (rotas, KAN-60; arquitetura, KAN-31).

   > O `CLAUDE.md` da raiz lista agora doze pontos que o back-end liga (acesso por pedido, `Plataforma` por pedido,
   > orquestrador decorado, registro, `LLMClient`, estado da conversa). Nenhum código de `backend/app/` foi alterado.
   > Pergunta aberta: o POST de mensagens terá chave de pedido?

3. Agentes (limites, KAN-38; lista de ferramentas, KAN-55).

   > O motor roda por `rodar_turno`, com 10 passos, 3 repetições e prazo de 120 s por turno. O prazo não tem fonte e
   > precisa ser medido. `PERGUNTAR` devolve o estado. A lista de ferramentas do agente de atendimento continua fixa em 5
   > (KAN-55). Existe um agente geral sobre o mesmo motor.

4. Testes e divergências (KAN-69).

   > A suíte de regressão cobre os cenários 1, 3, 5 e 7 e os ataques da KAN-69, em `backend/tests/`. As divergências com
   > o gabarito estão em `docs/decisoes.md`. Entre elas: o cenário 7 ficou em M00009 (o gabarito dizia M00001), o dado
   > restrito sai mascarado para todos na Sprint 2, e o CI ainda não roda pytest.

5. Ferramentas e mock (modelo de dados e dados sintéticos).

   > O mock (20 lojistas, 15 funcionários, cenários 1, 3, 5 e 7) vive em banco próprio (`MOCK_DATABASE_URL`) e as
   > ferramentas leem dele. Seis ferramentas de leitura novas estão ativas (11 ativas em 43). Dado restrito é mascarado
   > na saída da ferramenta. Ver `ferramentas/CLAUDE.md` e `mock/CLAUDE.md`.
