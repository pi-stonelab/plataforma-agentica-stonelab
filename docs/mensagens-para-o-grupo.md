# Mensagens para o grupo

Textos prontos para o Pedro mandar. Cada mensagem diz o que mudou na pasta da pessoa ou no que ela usa, o que ajudaria
fazer e o que pode quebrar. Nada aqui foi enviado nem postado. O Pedro lê, ajusta e decide quando mandar.

## Mensagens do fechamento das ferramentas (bloco F, 24/11)

Uma mensagem por pessoa, curtas, para o Pedro colar no Jira ou no grupo. Nada foi enviado. Os números de linha vêm de
`python -m ferramentas.pendencias` em 24/11; se o código mudar, rode de novo (`grep -rn "A FAZER (Marcelo"` também serve).
O estado geral está em `docs/estado-final-ferramentas.md`.

### Para a Larissa e o professor (interface)

Oi, Larissa e professor. O catálogo fechou em 56 ferramentas, todas com lógica. Nada de `frontend/` foi alterado. O que
a tela ainda precisa para mostrar tudo isso:

1. Tela de conectores: botão "Conectar conta" e "Desconectar" para Google e Microsoft (a conta é de cada pessoa). O
   estado de cada integração vem de `estado_integracoes()` (campos `modo`, `saude` e `credencial`, que é `pessoa` nessas
   duas). Quem não conectou recebe da ferramenta `integracao_indisponivel` com a frase "conta não ligada"; a tela deve
   mostrar a frase como veio. Referências: `ferramentas/integracoes/oauth.py:20`, `google_workspace/README.md:54`.
2. Cartão de confirmação das escritas: cada prévia (`Confirmacao`, §4.9) agora traz `expira_em` (ISO, horário de
   Brasília; sugestão de texto "Vale até 20:04") e `aviso` (texto de modo de demonstração, ou o que sai da plataforma;
   pode ser `null`). Marcador em `ferramentas/confirmacoes.py:294`. Botões enviar e descartar; a prévia vale 15
   minutos. São 16 escritas em duas fases e todas usam o mesmo cartão.
3. Caixa de saída simulada (sugestão, opcional): em modo simulado, Slack, Telegram e Jira guardam o que "mandariam"
   (`ferramentas/integracoes/simuladas.py`). Uma tela só de demonstração que lista esses itens ajudaria a mostrar que a
   mensagem saiu. Precisa de uma rota do Marcelo, que ainda não existe; só vale se sobrar tempo.
4. Montar agente: `GET /ferramentas` devolve o catálogo filtrado pela permissão de quem pede (`liberada` e `motivo`
   em linguagem simples). A tela de criação guiada pode mostrar as não liberadas desabilitadas, com o motivo, em vez de
   escondê-las. Ferramentas com integração desligada vêm `inativa`.
5. Anexos do chat (txt, csv, xlsx, docx e pdf, até 5 MB) e o link de download do arquivo que o agente entrega
   (`arquivo_id` na resposta da ferramenta `entregar_arquivo`): `ferramentas/integracoes/anexos/README.md:39`.
6. Nomes antigos no mock do front: `frontend/js/mock/ferramentas.js` ainda tem `abrir_ticket`, `adicionar_nota_ticket`,
   `atualizar_status_ticket`, `consultar_ticket`, `listar_tickets_cliente` e `resumir_volume_tickets` (hoje são
   `*_chamado`) e `consultar_saldo_conta`, que saiu do catálogo. Faltam 22 ferramentas novas no mock. O arquivo se gera
   sozinho: `python frontend/scripts/gerar_catalogo_mock.py` na raiz. O `CONTRATO_API.md:674` também cita
   `listar_tickets_cliente` e `consultar_ticket` no agente de exemplo.

### Para o Marcelo e a Isabel (back-end)

Oi, Marcelo e Isabel. Nada de `backend/app/` foi alterado. O que ficou marcado como `[A FAZER (Marcelo...)]` no código:

- Rotas de login da conta de cada pessoa: `GET /integracoes/{servico}/autorizar` e `.../callback`
  (`ferramentas/integracoes/oauth.py:16`; detalhes em `google_workspace/README.md:50` e `microsoft_365/README.md:48`).
- Token da pessoa cifrado: tabela `credenciais_externas` e um `ProvedorNoBanco` (`ferramentas/integracoes/credenciais.py:17`
  e `conector.py:223`). Hoje o provedor é em memória e some quando reinicia.
- Gravar `execucoes_ferramenta`: `governanca.adicionar_destino(gravar_execucao)` uma vez no `lifespan`, com sessão própria
  e erro se não gravar (`ferramentas/governanca.py:196`).
- Prévias de escrita: tabela e rotas de listar, confirmar e cancelar (`ferramentas/confirmacoes.py:71`), a prévia na
  resposta do turno (`:336`), 409 e 404 da rota de confirmação (`:356` e `:377`).
- Rotas de ferramentas e de integrações: `GET /ferramentas` (`ferramentas/catalogo.py:175`) e `GET /integracoes`
  (`ferramentas/integracoes/registro.py:45`).
- Anexos: `POST /conversas/{id}/anexos` e `GET /arquivos/{arquivo_id}` (`ferramentas/integracoes/anexos/conector.py:19`).
- `pypdf` no `requirements.txt` do back-end, senão PDF anexado volta `integracao_indisponivel`
  (`ferramentas/integracoes/formatos.py:354`). Hoje nenhum dos dois `requirements.txt` o tem.
- `CLAUDE.md` da raiz está desatualizado: a linha 37 diz "43 ferramentas em 8 áreas, 11 ativas"; hoje são 56 ativas (a
  lista sai de `catalogo.carregar()`). Não mexemos no arquivo de vocês.
- Sobre o índice: ele já sai compacto (cabe em 5800 caracteres) e a data de hoje vem do motor. Nada a fazer aí; só não
  mudem `MAX_CHARS_MD` sem avisar.

### Para o Brenno (segurança)

Oi, Brenno. Decisões nossas sem fonte, que precisam do seu olho:

- Categorias de dado novas para todo cargo com área: `chamado_interno` (Jira), `comunicacao_interna` (Slack e Telegram),
  `agenda_pessoal` e `documento_de_trabalho` (Google, Microsoft e anexos). Admin, auditor e gestor de acessos ficam de
  fora (E1 e G1 em `docs/decisoes.md`). Vocês concordam que qualquer funcionário use?
- E-mail e telefone escritos no meio de um texto livre que sai (corpo de e-mail, mensagem de Slack) não são mascarados;
  só CPF e cartão são (pergunta aberta 4). É decisão de produto.
- Alçadas: `calcular_parcelas` e `registrar_acordo` usam as de `mock/regras.py` (analista até 6 parcelas e entrada
  mínima de 20%, coordenador até 12 parcelas, desconto no principal só do coordenador e até 10%, perdão de encargos do
  analista até R$ 2.000, dupla aprovação acima de R$ 10.000). `executar_antecipacao` é de N2. Se algum número difere do
  que vocês desenharam, é uma linha em `regras.py`.
- Em aberto no `enviar_email`: o supervisor pode confirmar a prévia de outra pessoa? Hoje só quem pediu confirma. E como
  impedir que o corpo leve dado de outro lojista (`ferramentas/comunicacao/enviar_email/agents.md:39` e `:40`).
- Contas pessoais (G3): o login do Google e da Microsoft usa PKCE, leitura por padrão e escrita só quando a pessoa usa
  uma ferramenta de escrita, sem permissão `.All`. O token fica por pessoa e o back-end precisa guardá-lo cifrado, o que
  ainda não existe. O Admin global não alcança nenhuma ferramenta de dado.
- Risco de oráculo em `verificar_identidade_contato` (pergunta aberta 15): quem chuta telefones descobre qual confere.
  Falta limite de tentativas e alerta; precisa de decisão sua e do Enrico.

### Para o Enrico (QA)

Oi, Enrico. A suíte está em `backend/tests/` com 3800+ testes (`python -m pytest backend/tests -q`). Duas falhas são
aceitas: e-mails `@stonelab.dev` em `frontend/` (o teste de LGPD varre o repositório todo). Regressão por bloco:

- Mock fase 2: `test_mock_consultas_fase2.py`, `test_mock_fase2.py`.
- Leituras e cálculos (blocos A a C): `test_ferramentas_bloco_c_*.py`, `test_ferramentas_novas_matriz.py` (cargo, escopo, parâmetros
  e falha do mock para cada ferramenta), `test_regressao_cenarios.py` (cenários 1, 3, 5 e 7).
- D, escritas no mock: `test_ferramentas_escritas_mock.py` (prévia não grava, confirmar grava uma vez, cancelar e expirar
  não gravam, outra pessoa não confirma).
- E1 e E2, integrações: `test_integracoes_*.py`, contra servidores locais falsos; nenhum teste sai da máquina.
- F, índice, agente e avaliação: `test_catalogo_indice.py`, `test_agente_atendimento_ferramentas.py`,
  `test_agente_data_de_hoje.py`, `test_agentes_avaliacao.py`.

O que vale testar à mão: o índice de cada um dos 10 cargos com todas as integrações ligadas; uma escrita até a
confirmação; prévia expirada (15 min); a mesma pergunta com cargos diferentes; o corte de resposta grande (5000
caracteres). Pendente para você: contar prévias aguardando, confirmadas, canceladas e expiradas a partir do registro
(`ferramentas/confirmacoes.py:16`). O CI ainda só roda gitleaks e ruff, não o pytest.

### Para o Christopher e o Isack (agentes)

Oi, Christopher e Isack. Três mudanças que tocam o motor ou os prompts, todas pequenas e testadas:

- Índice acima de 6000 caracteres: o corte de `MAX_CHARS_MD` (6000) escondia o fim do índice do agente geral (até 9500
  caracteres para um supervisor). Resolvemos do nosso lado, em `ferramentas/catalogo.py`: o catálogo mede o índice e
  encurta as frases para caber em 5800. O motor não mudou. Se mudarem `MAX_CHARS_MD`, `catalogo.LIMITE_DO_INDICE` precisa
  ficar abaixo (o teste `test_catalogo_indice.py` confere).
- Data de hoje no prompt: o `montar_prompt` ganhou uma linha (`catalogo.data_de_hoje()`), antes da pergunta. No simulado
  é 15/10/2026 21h; com uma integração real, o dia de Brasília. Os dois `SISTEMA` ganharam a regra de dizer sempre a data
  da cotação ou da consulta.
- Lista de ferramentas do atendimento: agora tem 33 das 56 (`FERRAMENTAS_DO_AGENTE`, decisão F2). Continua fixa no
  código; ler da configuração do agente é de vocês (marcador `agentes/agente_atendimento/agente.py:46`, KAN-55). Falta
  também avisar no `Turno` que há prévia aguardando (`ferramentas/comunicacao/enviar_email/agents.md:38`).
- A avaliação cresceu para 27 cenários, com as escritas em duas fases (`agentes/avaliacao.py`). A rodada com o modelo
  real fica com o Pedro.

## Mensagens anteriores (bloco de 12/11 a 24/11)

Estas já foram escritas antes do fechamento. Onde um número ficou velho, está corrigido.

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
  por pedido, e havia 43 ferramentas, 11 ativas; hoje são 56, todas ativas). Acrescentamos duas seções: "Como as quatro pastas se encaixam" e "O que a
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

- Banco do mock (12/11): o mock agora vem como SQL pronto em `mock/sql/` e tem um Postgres próprio em
  `mock/docker-compose.yml` (porta 5433, já sobe preenchido, papel `mock_leitura` só com SELECT). Não mexemos no seu
  `docker-compose.yml` nem no banco da plataforma. Sugestão para você decidir: acrescentar ao `.env.example` as linhas
  `MOCK_POSTGRES_PASSWORD=` e `MOCK_LEITURA_PASSWORD=` (vazias), com o comentário "só para o Postgres opcional do mock".
  Quando o back-end usar o mock em Postgres, a URL dele deve ser a do `mock_leitura`, nunca a do dono.

- Funcionário inativo (12/11): `governanca.usuario_do_cargo` não confere a situação do funcionário. A checagem agora
  está em `ferramentas/diretorio.py`, `buscar_usuario(id)`, que devolve o `Usuario` só se a situação for exatamente
  `ativo` e `None` caso contrário. Sugestão para o seu `montar_acesso`: chamar essa função em vez de montar o usuário
  com `usuario_do_cargo` direto, para desligado e afastado não passarem mesmo com token válido. Se o diretório
  estiver fora do ar ela levanta `ConnectionError`, que dá o 503 que o `CLAUDE.md` já descreve.

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

- Visibilidade: `PRIVADO`, `CONVIDADOS` e `PUBLICO`, escolhida pelo dono. O dono convida em privado e em convidados; em público o convite é negado.
- Dois perfis novos: `Auditor`, que lê a auditoria e mais nada, e `AdminGlobal` mais restrito, que pausa agentes
  e não executa nem vê privado. Área é opcional para os dois.
- A `Plataforma` agora vale para um pedido. O back-end cria uma por pedido, com `carregar_agente` para agentes que vêm
  do banco e `ao_registrar` para gravar a auditoria.
- `Evento` guarda só o id da pessoa, mais o `execucao_id`. Nunca o nome.
- `autorizar` decide sobre o agente registrado e nega agente forjado ou não registrado.
- Mudar visibilidade e `deprecar` passam por métodos que autorizam e gravam evento.
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

Atualização de 12/11, depois que o seu PR #10 entrou na `main`: alinhamos o nosso `seguranca/` com as suas duas
correções (`e0b5eac` e `827290c`). O que ficou igual ao seu: agente desativado só aceita `VER`, para todos;
`autorizar` devolve o agente do cadastro e o decorator o passa para a função; só o id do objeto recebido vale; o método
de pausar é `deprecar` (evento `DEPRECAR`; o nosso `desativar` saiu). Os seus testes em `testes/seguranca/` continuam
lá e passam, com três ajustes que precisamos fazer neles por causa do modelo com ids:

- `dono=`, `convidados=` e `Evento.usuario` viraram `dono_id=`, `convidados_ids=` e `Evento.id_usuario`.
- `test_supervisor_da_area_desativa`: o Supervisor não vê agente privado de outra pessoa (decisão do grupo), então o
  teste abre o agente (`CONVIDADOS`) antes. Se você preferir que o Supervisor possa pausar até o privado da área dele,
  é uma mudança pequena em `_gerencia`; diga qual você quer.
- Agora o dono convida mesmo em agente privado, como os seus testes esperavam. Por isso `PRIVADO` e `CONVIDADOS` se
  comportam igual hoje. Fica para a gente decidir se juntamos os dois níveis.

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
- A lista `FERRAMENTAS_DO_AGENTE` do atendimento tinha 5 nomes (KAN-55); hoje tem 33 das 56 (decisão F2).
- A suíte do agente mudou de lugar: `backend/tests/test_agente_*.py`.

Perguntas para vocês: o que acontece quando o turno passa de 10 passos (hoje devolve uma mensagem fixa e o motivo
`max_passos`)? Como querem guardar o `Turno.estado` entre mensagens? Fica com o back-end, por conversa.

## Para o Marcelo, a Isabel e a Larissa: agenda, planilhas, documentos e anexos (bloco E2)

Oi, pessoal. Entraram em `ferramentas/` o Google Workspace, o Microsoft 365 e os anexos do chat, com nove ferramentas
novas em `documentos_e_agenda` (o catálogo tem 56 ferramentas, todas com lógica). Nada em `backend/app/` nem em `frontend/` foi alterado: o que falta
de cada lado está marcado no código com `[A FAZER (...)]`, nos pontos exatos de ligação.

Para o Marcelo e a Isabel (back-end, Sprint 3):

- Conta de cada pessoa (OAuth2): rotas `GET /integracoes/{servico}/autorizar` (chama `FluxoOAuth.iniciar` com o
  `id_usuario` do token e devolve o endereço de consentimento) e `GET /integracoes/{servico}/callback` (recebe `state`
  e `code`, chama `concluir`). O `servico` é `google_workspace` ou `microsoft_365`; o `FluxoOAuth` sai de
  `CONECTOR.fluxo()`. O `id_usuario` vem sempre do token, nunca do corpo ou da URL. Marcador em
  `ferramentas/integracoes/oauth.py`.
- Guardar os tokens: uma tabela `credenciais_externas` (id_usuario, serviço, escopos, expiração e os dois tokens
  cifrados com uma chave do `.env`) e um `ProvedorNoBanco(ProvedorDeCredencial)` com `ler`, `guardar` e `apagar`;
  `credenciais.usar(provedor)` no `lifespan`. Hoje o provedor é `ProvedorEmMemoria` (some quando reinicia). Marcador em
  `ferramentas/integracoes/credenciais.py`.
- Anexos: `POST /conversas/{id}/anexos` (multipart, até 5 MB, chama `anexos.guardar_entrada(id_usuario_do_token, nome,
  bytes)` e devolve o `anexo_id`; liste os anexos da conversa para o agente com `listar_entradas`) e
  `GET /arquivos/{arquivo_id}` (chama `anexos.abrir_saida`, com `Content-Disposition: attachment` e
  `X-Content-Type-Options: nosniff`). Marcador em `ferramentas/integracoes/anexos/conector.py`.
- `.env`: `GOOGLE_*`, `MICROSOFT_*`, `ESCRITORIO_DOMINIOS`, `ANEXOS_MODO` e `ANEXOS_DIRETORIO` (nomes em `.env.example`,
  sem valores). `GOOGLE_REDIRECT_URI` e `MICROSOFT_REDIRECT_URI` precisam ser o endereço da rota de retorno de vocês.
- Pode quebrar: `catalogo.executar` agora devolve `integracao_indisponivel` "conta não ligada" se a pessoa ainda não
  conectou a conta; a interface precisa mostrar isso.

Para a Larissa (interface, Sprint 3):

- Botão "Conectar conta" e "Desconectar" por serviço na tela de conectores (`estado_integracoes()` já diz o `modo` e a
  `saude`). Conectar abre o endereço devolvido pela rota `autorizar`.
- Botão de anexar no chat (txt, csv, xlsx, docx e pdf, até 5 MB) e o link de download do arquivo que o agente entrega,
  com o `arquivo_id` que vem na resposta de `entregar_arquivo`.
- As ferramentas de escrita (`criar_evento_agenda`, `adicionar_linha_planilha`, `criar_planilha`) pedem a confirmação em
  duas etapas que já existe para `enviar_email`.

Importante para todos: o Google e a Microsoft **não foram testados contra o serviço de verdade** (sem conta nem app
registrado, só dado sintético); os testes usam servidores locais falsos. O Pedro roda
`MODO_TERMINAL=1 python -m ferramentas.integracoes testar google_workspace` (e `microsoft_365`) quando houver o app.

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
   > precisa ser medido. `PERGUNTAR` devolve o estado. A lista de ferramentas do agente de atendimento é fixa em 33
   > (KAN-55, decisão F2). Existe um agente geral sobre o mesmo motor.

4. Testes e divergências (KAN-69).

   > A suíte de regressão cobre os cenários 1, 3, 5 e 7 e os ataques da KAN-69, em `backend/tests/`. As divergências com
   > o gabarito estão em `docs/decisoes.md`. Entre elas: o cenário 7 ficou em M00009 (o gabarito dizia M00001), o dado
   > restrito sai mascarado para todos na Sprint 2, e o CI ainda não roda pytest.

5. Ferramentas e mock (modelo de dados e dados sintéticos).

   > O mock (20 lojistas, 15 funcionários, cenários 1, 3, 5 e 7) vive em banco próprio (`MOCK_DATABASE_URL`) e as
   > ferramentas leem dele. As ferramentas leem do mock e hoje são 56, todas ativas. Dado restrito é mascarado
   > na saída da ferramenta. Ver `ferramentas/CLAUDE.md` e `mock/CLAUDE.md`.

6. Back-end (OAuth por pessoa e anexos, KAN-60; arquitetura, KAN-31).

   > Entraram o Google Workspace, o Microsoft 365 e os anexos do chat em `ferramentas/integracoes/`, com as nove
   > ferramentas de `documentos_e_agenda`. Falta ao back-end: rotas `/integracoes/{servico}/autorizar` e `/callback`,
   > um `ProvedorNoBanco` com tokens cifrados e as rotas de envio e download de anexos (marcadores `[A FAZER (Marcelo...)]`).
   > Não testado contra o Google e a Microsoft de verdade; ver `testar` nos READMEs.

7. Interface (conectores e chat, KAN-60).

   > A tela de conectores precisa do botão "Conectar conta" por serviço, e o chat, do botão de anexar e do link de
   > download do arquivo que o agente entrega (marcadores `[A FAZER (Larissa...)]`). As escritas novas usam a
   > confirmação em duas etapas.
