# Registro de decisões

Este arquivo guarda o que foi decidido nesta integração (segurança, mock, ferramentas, agentes), por quem, por
quê e onde está no código. Serve a quem chega depois e precisa saber se uma regra é escolha da equipe ou acidente.

Como ler:

- "Quem" diz de quem foi a decisão. D1 a D10 e H1 a H5 são do Pedro (H é a sigla das cinco decisões da noite de 11/11 que não estão no PLANO). O1 a O13 foram tomadas pelo orquestrador (o Claude que
  coordenou as etapas) a partir da crítica ao plano e estão registradas para o Pedro ver. Nenhum arquivo do projeto
  mostra que o Pedro tenha aprovado as O por escrito, exceto onde a entrada diz o contrário.
- "Quando" vem do `PLANO.md` v2 ou da data do commit. Uma data marcada "(commit)" foi deduzida do histórico do Git,
  porque ninguém anotou a hora da conversa.
- "Motivo" só traz o que está escrito numa fonte. Quando a fonte não diz, a entrada diz "motivo não registrado".
- "No código" aponta o arquivo ou o commit. Para os detalhes, vá ao `CLAUDE.md` da pasta citada.
- Siglas: KAN-nn é um card do Jira. DOC-MOCK é o documento da Stone simulada (KAN-28). Os números de tabelas e
  seções (§) são dele. A, B, C... das etapas são as etapas de implementação (A mock, segurança e agentes; B
  ferramentas; C back-end; E verificação; F documentação).

## Decisões do Pedro (D1 a D10)

### D1. Base do trabalho
- Decisão: partir da `main` mais os PRs abertos mesclados na cópia local. O PR nosso só sai depois que os deles entrarem.
- Quem e quando: Pedro, 11/11 à noite (PLANO).
- Motivo: não registrado.
- No código: branch `integracao/seguranca-banco` (PR #10 de `seguranca/`, PR #11 do esqueleto do back-end, PR #12 do
  `CLAUDE.md` do Marcelo).

### D2. Decorators e type hints liberados
- Decisão: usar decorator e type hint onde forem melhores para o produto. O código continua legível para quem está no
  2º período. A regra antiga "sem decorators, sem type hints em `ferramentas/`" foi revogada.
- Quem e quando: Pedro, 11/11 à noite (PLANO; BRIEFING, decisão 2).
- Motivo: "fazer o que for melhor para o produto final" (BRIEFING).
- No código: `exige_permissao` em `seguranca/envelope.py`; `Plataforma | None` e outros type hints em `seguranca/`.

### D3. Visibilidade de agente
- Decisão: o criador escolhe entre privado, convidados e público. Publicar não exige aprovação. Público quer dizer
  todos os funcionários das duas áreas. O supervisor não vê agente privado de outra pessoa. O Admin opera (pausa) e
  não vê agente privado nem dado de lojista.
- Quem e quando: decisão do grupo, registrada pelo Pedro, 11/11 à noite (PLANO; KAN-28, KAN-33, KAN-69).
- Motivo: vem das decisões do grupo no Jira. O PLANO não repete os motivos.
- No código: `Visibilidade` e as regras de cada perfil em `seguranca/permissoes.py` (commit 570604b). A tabela completa
  está em `seguranca/CLAUDE.md`. Pendente: o `README` de `seguranca/` ainda marca a decisão 3 como "a confirmar" para o
  supervisor (ele gerencia e executa os agentes abertos da própria área).

### D4. Só duas áreas
- Decisão: a plataforma tem as áreas `atendimento` e `financeiro`. `dados` e `tecnologia` saíram.
- Quem e quando: Pedro, 11/11 à noite (PLANO; BRIEFING, decisão 4).
- Motivo: só funcionários dessas duas áreas usam a plataforma (BRIEFING).
- No código: `AREAS` em `mock/regras.py`; `ferramentas/governanca.py` usa a mesma lista.

### D5. Mock reduzido ao necessário
- Decisão: a primeira fase do mock tem só o que a demo precisa.
- Quem e quando: Pedro, 11/11 à noite (PLANO).
- Motivo: não registrado. O PLANO só diz "fase 1".
- No código: `mock/gerar.py` (20 lojistas, 15 funcionários, cenários 1, 3, 5 e 7, falhas simuladas). O DOC-MOCK §11
  pede o mock completo (38 funcionários, 11 cenários); isso ficou para depois (divergência V12).

### D6. Seis ferramentas de leitura
- Decisão: escrever as ferramentas de leitura que os cenários 1, 3, 5 e 7 pedem (cerca de seis). Outras só quando o
  Pedro pedir.
- Quem e quando: Pedro, 11/11 à noite (PLANO). Aprovação da lista final das seis: 11/11 à noite (commit 76e3798); nenhum
  texto registra a conversa.
- Motivo: sem essas ferramentas os quatro cenários da demo não rodam (CRIT, ponto P2 da crítica ao plano).
- No código: `consultar_liquidacoes_cliente`, `listar_chamados_cliente`, `consultar_historico_contato`,
  `listar_faturas_em_atraso`, `calcular_parcelas`, `consultar_contatos_lojista`. Hoje são 11 ferramentas ativas em 43.

### D7. Back-end segue o CLAUDE.md do Marcelo
- Decisão: login, tabelas e rotas seguem à risca o `CLAUDE.md` do Marcelo (PR #12), e esse arquivo é atualizado com o
  que foi feito.
- Quem e quando: Pedro, 11/11 à noite (PLANO).
- Motivo: o back-end é de Marcelo e Isabel; o que a equipe constrói em cima respeita o padrão deles (BRIEFING).
- No código: ainda não feito. A etapa C (back-end) não rodou. O `CLAUDE.md` da raiz já foi alinhado ao código das
  outras pastas e lista o que o back-end precisa fazer ("O que a etapa do back-end precisa fazer").

### D8. Tabela cargo para perfil
- Decisão: aprovada a tabela que liga cada um dos 10 cargos do mock a um perfil da segurança, com as correções de B3
  (o nível N1 ou N2 vem do cargo, não do perfil).
- Quem e quando: Pedro, 11/11 à noite (PLANO).
- Motivo: a proposta anterior era dedução sem fonte (FATOS, L9). Dois colaboradores (`atendente_n1` e
  `especialista_n2`) têm o mesmo perfil e níveis diferentes.
- No código: campo `perfil_padrao` de cada cargo em `mock/regras.py`. A tabela está no `CLAUDE.md` da raiz.
  `GestorDeAcessos` não corresponde a nenhum cargo do mock (SEM FONTE).

### D9. Quem lê a auditoria
- Decisão: o Auditor de compliance lê a auditoria. O Admin não.
- Quem e quando: Pedro, 11/11 à noite (PLANO). Concorda com o comentário K28-ATU do Jira.
- Motivo: o comentário K28-ATU do Jira diz que a leitura da auditoria é do auditor de compliance.
- No código: `Plataforma.autorizar_leitura_auditoria` e `pode_ler_auditoria` em `seguranca/permissoes.py`. O método
  só autoriza; a leitura da tabela `auditoria` é do back-end e ainda não existe (divergência V9).

### D10. Ferramentas ficam no código, não no banco
- Decisão: as ferramentas não vão para o banco e não são listadas para a pessoa. Continuam no código (catálogo e
  `agents.md`), vistas só pelo agente, filtradas pela permissão. A pessoa vê só as integrações, na aba de
  conectores. A conexão por usuário (ex.: ligar o Gmail) fica para a Sprint 3.
- Quem e quando: Pedro, 11/11, 22h (PLANO).
- Motivo: o PLANO não escreve um motivo. Ele registra a consequência: nada de tabela de ferramentas e nada de rota que liste fichas.
- No código: `ferramentas/catalogo.py`. Consequência: não existe tabela `ferramentas` nem rota que liste fichas para a
  interface.

## Decisões também tomadas na noite de 11/11 e de manhã em 12/11 (Pedro, ao longo das etapas)

Estas cinco aparecem no pedido de documentação e nos commits. Nenhuma está no `PLANO.md`. A data é a dos commits.

### H1. O cenário 7 fica em M00009
- Decisão: a mensagem com a instrução escondida (cenário 7) fica no lojista M00009, chamado CH000062. O nome fantasia
  armadilha fica em M00012.
- Quem e quando: Pedro, 11/11 à noite (commits 1be1243, 4713f5f).
- Motivo: o DOC-MOCK §9 não diz qual lojista (FATOS, L1). O gabarito da KAN-69 usava M00001.
- No código: `_plantar_cenario_7` em `mock/gerar.py`. Detalhes em `mock/CLAUDE.md`.

### H2. O mock é a referência
- Decisão: quando o gabarito da KAN-69 e o mock divergem, vale o mock. A suíte de regressão segue o mock.
- Quem e quando: Pedro, 11/11 à noite (commit e41889e).
- Motivo: não registrado.
- No código: `backend/tests/gabaritos.py` (constantes escritas à mão, iguais ao mock). `docs/regressao.md` explica.

### H3. Agente geral já na Sprint 2
- Decisão: existe um agente geral, padrão do chat, com todas as ferramentas do catálogo. O que cada pessoa alcança
  continua sendo decidido pelo cargo.
- Quem e quando: Pedro, 11/11 à noite (commits 7d8401d, ba2bc99). O motivo não está escrito; o pedido veio pelo
  orquestrador.
- Motivo: não registrado.
- No código: `agentes/agente_geral/agente.py` e `Agente.da_plataforma` em `seguranca/permissoes.py`.
  Ver `docs/agente-geral-e-especificos.md`.

### H4. Ferramentas de leitura aprovadas
- Decisão: as seis ferramentas de leitura de D6 foram aprovadas e ficaram ativas. Escrita continua inativa.
- Quem e quando: Pedro, 11/11 à noite (commit 76e3798).
- Motivo: ver D6.
- No código: `status = "ativa"` nas fichas de `ferramentas/*/*/func.py`.

### H5. Convite em agente privado e em convidados
- Decisão: o dono convida em `PRIVADO` e em `CONVIDADOS`. Em `PUBLICO` o convite é negado, porque todos já usam. A lista de
  convidados vale nos dois níveis, então `PRIVADO` e `CONVIDADOS` hoje se comportam igual.
- Quem e quando: Pedro, 12/11 (substitui a regra de 11/11, commit 6a775c2, que só deixava convidar em `CONVIDADOS`).
- Motivo: os testes do Brenno (PR #10) convidam em agente recém-criado, que nasce privado.
- No código: `_gerencia` e `_usa` em `seguranca/permissoes.py`. Em aberto: manter os dois níveis separados ou juntar.

### H6. O parâmetro de lojista continua `id_cliente`
- Decisão: o nome que o modelo preenche nas ferramentas de lojista continua `id_cliente`. Por dentro é `codigo` ou
  `codigo_lojista`, e nas tabelas `id_lojista`. Nenhum código muda.
- Quem e quando: Pedro, 12/11 de manhã.
- Motivo: os gabaritos da KAN-69 já usam `id_cliente`; renomear quebraria fichas, testes e gabaritos.
- No código: `ferramentas/lojista.py` (docstring com os três nomes).

### H7. O banco em memória do mock só é usado por uma thread por vez
- Decisão: `mock/banco.py` ganhou `trava_de_acesso(engine)`; `mock/consultas.py` a segura ao abrir sessão sobre um
  engine SQLite em memória. Bancos em arquivo ou Postgres não usam trava.
- Motivo: o banco em memória tem uma conexão só (StaticPool) dividida entre threads. No PC do Pedro (Windows, Python
  3.15) o teste a20 de dois funcionários ao mesmo tempo falhou uma vez; sob carga, no sandbox, apareceu o aviso
  "Double checkin" do SQLAlchemy. Não muda nada para quem usa o mock em arquivo.
- Teste: `test_banco_em_memoria_nunca_e_usado_por_duas_threads_ao_mesmo_tempo` (falha sem a trava).
- Também: removidos os `noqa` sem efeito e `timezone.utc` virou `UTC` (o ruff mais novo, que o CI instala, acusava).

### H8. Alinhamento com o PR #10 do Brenno
- Decisão: agente desativado só aceita `VER`, para todos; `autorizar` devolve o agente do cadastro e o decorator o passa à
  função; do objeto recebido só vale o id; o método de pausar se chama `deprecar` (evento `DEPRECAR`), e `desativar` deixou
  de existir. Os testes dele em `testes/seguranca/` foram ajustados aos ids (`dono_id`, `convidados_ids`, `id_usuario`), e o
  teste do Supervisor abre o agente antes de pausar (Supervisor não vê privado de outra pessoa).
- Quem e quando: Pedro, 12/11 ("prefira a regra dele").
- Motivo: o PR #10 já está na `main`; o código tem uma regra só.
- No código: `Plataforma.autorizar`, `_decidir`, `_registrado`, `deprecar`, `seguranca/envelope.py`.

### H9. Postgres local do mock, em compose separado
- Decisão: oferecer um Postgres só do mock (opção B), em `mock/docker-compose.yml`, sem mexer no `docker-compose.yml` da
  raiz (do Marcelo). O SQLite local continua o padrão, nos testes e no CI.
- Quem e quando: Pedro, 12/11 ("pode começar").
- Motivo: dar a todos um SQL de verdade com o mesmo conteúdo, sem arriscar o banco da plataforma.
- No código: `mock/docker-compose.yml`, `tests/test_mock_postgres.py`, `MOCK_TESTE_POSTGRES_URL` em `apoio_ferramentas.py`.
- Verificado: o gerador e a suíte inteira do back-end contra um Postgres 16 (servidor instalado, sem Docker): 2173 passam,
  1 pulado (NUL). O arquivo do compose foi validado com `docker compose config`; o container em si não foi subido.

### H10. O SQLite local do mock é gerado sozinho na primeira vez
- Decisão: ninguém precisa rodar `python -m mock.gerar` para começar. A fachada monta `dados_locais/mock.sqlite` na
  primeira consulta, a partir do SQL pronto (H11), se o arquivo não existe, está vazio ou é de outra versão do esquema.
- Quem e quando: Pedro, 12/11 ("a intenção é não ter que gerar toda vez").
- Motivo: o erro "diretório de funcionários indisponível" no terminal, com o arquivo ainda não gerado.
- No código: `mock/gerar.py` (`garantir_mundo_local`), `ferramentas/dados_sinteticos.py` (`_engine`), `tests/test_mock_primeira_vez.py`.
- Não muda: o mundo é o mesmo (mesma semente); banco externo e `--permitir-banco-externo` seguem como antes.

### H11. Esquema redesenhado e SQL pronto no Git
- Decisão: o mock vira SQL pronto, versionado em `mock/sql/` (esquema e dados, para SQLite e Postgres), que qualquer
  pessoa carrega sem rodar Python. O esquema foi redesenhado mantendo os nomes de tabela e coluna que ferramentas,
  consultas e testes usam: chaves estrangeiras de verdade (também no SQLite), listas de valores e regras entre colunas
  em CHECK, índices nas buscas, nomes previsíveis e comentários de sensibilidade. O Postgres do compose sobe já
  preenchido e com dois papéis: `mock` (dono) e `mock_leitura` (só SELECT, o das ferramentas).
- Quem e quando: Pedro, 12/11 ("redesenhar e retestar, mantendo a coesão; SQL pronto para o pessoal baixar e testar
  sem rodar código; pronto em cada máquina").
- Motivo: um banco pronto para todo mundo, que se defende sozinho além da aplicação, e com o acesso das ferramentas
  separado de quem pode alterar o mock.
- No código: `mock/modelos.py` (`VERSAO_DO_ESQUEMA = 2`), `mock/exportar.py`, `mock/sql/`, `mock/docker-compose.yml`,
  `mock/gerar.py` (`garantir_mundo_local`), `mock/banco.py` (FK no SQLite); testes `test_mock_esquema.py`,
  `test_mock_sql.py`, `test_mock_postgres.py`.
- Não adotado, de propósito: um schema por sistema (DOC-MOCK §11.6) e Row-Level Security para a carteira. Só fazem
  sentido quando o back-end conectar com um papel por cargo; hoje as quatro camadas ficam na aplicação.
- A fonte da verdade continua sendo o código; o SQL é gerado (`python -m mock.exportar`) e um teste barra divergência.

### H12. Instalador do Postgres do mock, sem Docker
- Decisão: `python -m mock.instalar_postgres` instala o mock num Postgres que já roda na máquina, com o mesmo resultado
  do compose (banco `stonelab_mock`, dono `mock`, papel `mock_leitura`). O padrão do repositório continua o SQLite local;
  o Postgres único para todos fica para depois, quando o back-end conectar com um papel por cargo.
- Quem e quando: Pedro, 12/11 (sem Docker na máquina; instalou o Postgres oficial na porta 5433).
- Motivo: o `pgserver` não tem pacote para o Python 3.15 e o Docker não é dependência do `requirements.txt`; o
  Postgres oficial dispensa os dois.
- No código: `mock/instalar_postgres.py`, `backend/tests/test_mock_instalar_postgres.py`. Só aceita host local, valida
  nomes de banco e papéis, não imprime senha e não altera nada se o banco já existe sem `--recriar`.
- Verificado: contra um Postgres 16 em Linux (instalação, repetição, `--recriar`, leitura pelas ferramentas, escrita
  negada). Não foi rodado no Windows; a primeira execução real é a do Pedro.

## Decisões do orquestrador (O1 a O13)

Todas de 11/11, PLANO v2, escritas depois da crítica ao plano. "Para o Pedro ver" quer dizer que ele leu; só a O10
está marcada "confirmar com o Pedro".

### O1. Regras de dado por cargo
- Decisão: cada cargo tem em `mock/regras.py` a área, o perfil padrão, o nível de ferramenta, o escopo de lojistas
  (carteiras do time, todas ou nenhum), a janela em dias (90 só para `atendente_n1`), as categorias de dado e se usa
  ferramentas. A checagem de categoria entra em `motivo_bloqueio`: a ferramenta some do `catalogo.ler`.
- Motivo: a divisão em só N1 e N2 não dava para o DOC-MOCK §8.2 (crítica B2 e B3).
- No código: `RegraCargo` em `mock/regras.py`; `ferramentas/governanca.py` (`motivo_bloqueio`, `janela_dias`).

### O2. Dado restrito sai mascarado para todos, uma vez só
- Decisão: ninguém vê o dado restrito completo na Sprint 2 (nem o N2). A máscara roda uma vez, em
  `Ferramenta.executar`, falhando fechado. CPF e cartão em texto livre também são mascarados. Nome fantasia e
  interações viram conteúdo de terceiros.
- Motivo: ver o dado completo exige motivo escrito, chamado e auditoria (decisão 9 do BRIEFING), que não existem ainda.
- No código: `ferramentas/mascara.py` e `ferramentas/base.py`. Divergência V2.

### O3. Quem liga as quatro pastas
- Decisão: a ponte de acesso fica em `backend/app/permissoes.py` e a entrada decorada em `backend/app/orquestrador.py`.
  `ferramentas/`, `seguranca/` e `agentes/` não importam umas às outras.
- Motivo: são os lugares que o `CLAUDE.md` do Marcelo já prevê.
- No código: dois testes protegem a separação: `agentes/` não importa `mock/` (`test_agente_terminal.py`) e nenhum
  `func.py` importa `mock` nem `sqlalchemy` (`test_regressao_contrato.py`). Os dois arquivos do back-end ainda não
  existem.

### O4. Liquidação entra nas categorias do `atendente_n1`
- Decisão: o N1 lê liquidações, dentro da carteira e dos 90 dias.
- Motivo: o cenário 1, que é critério da demo, exige. O DOC-MOCK §8.2 não lista liquidação para o N1. Divergência V16.
- No código: `categorias_dado` do cargo em `mock/regras.py`.

### O5. Admin e Auditor são perfis próprios
- Decisão: Admin sem área obrigatória; Auditor não cria nem executa agente e só lê a auditoria. Nenhum dos dois tem
  ferramentas de dado na Sprint 2.
- Motivo: KAN-69 E8 e E27.
- No código: `AdminGlobal` e `Auditor` em `seguranca/permissoes.py`; `usa_ferramentas = False` nos dois cargos do mock.

### O6. O que fica para a Sprint 3
- Decisão: REPLICAR agente, ver restrito completo, alçadas executáveis, ferramentas de escrita, SSE, limite de gasto e
  o volume completo do mock. Ficam na Sprint 2: visibilidade (D3), agente ativo ou não, evento só com id e
  `AcessoNegado` sem nome.
- Motivo: o PLANO só diz "cortes para a Sprint 3". A demo da Sprint 2 é em 19/11.
- No código: `Acao` não tem `REPLICAR`; escrita é inativa em `ferramentas/base.py` (`esta_ativa`).

### O7. Pessoas reais só como mecanismo
- Decisão: existe o caminho (CSV local fora do Git, `.gitignore`, senha definida por comando, aviso de LGPD). Nenhuma
  pessoa real está cadastrada.
- Motivo: decisão 11 do BRIEFING (testar com colegas respeitando a LGPD).
- No código: `ler_pessoas_teste` em `mock/gerar.py`; `mock/CLAUDE.md` descreve o passo a passo.

### O8. Dinheiro em centavos e "hoje" fixo
- Decisão: valores inteiros em centavos. O "hoje" do mock é 15/10/2026 (`HOJE_DO_MOCK`), nunca `date.today()`. Sem
  Faker: listas fixas e `random.Random(semente)`. O mundo sai sempre igual.
- Motivo: os gabaritos dos cenários precisam de valores exatos (por exemplo R$ 330,67 no cenário 3).
- No código: `HOJE_DO_MOCK` em `mock/regras.py`; `SEMENTE` em `mock/gerar.py`.

### O9. Falha fechada na auditoria
- Decisão: se o evento de acesso ao agente ou o registro da chamada não puder ser gravado, a ação não acontece. Engines
  com `hide_parameters=True`. Erro de banco nas ferramentas vira `integracao_indisponivel`.
- Motivo: KAN-69 E52 (a escrita não segue sem auditoria). Divergência V14.
- No código: `RegistroIndisponivel` em `ferramentas/governanca.py`; `ferramentas/base.py` registra a intenção antes de
  escrever.

### O10. Testes novos em `backend/tests/`
- Decisão: os testes novos ficam em `backend/tests/` (rastreados), onde o CI e a QA os enxergam. Os de `testes/`
  continuam locais.
- Motivo: a QA (Enrico) só vê testes rastreados. Marcado "confirmar com o Pedro" no PLANO.
- No código: `backend/tests/`. O CI de hoje (`.github/workflows/ci.yml`) roda só gitleaks e ruff, ainda não roda pytest.
  Divergência V13.

### O11. Limites da KAN-38 no agente
- Decisão: 10 passos por turno. A mesma ferramenta com os mesmos argumentos 3 vezes seguidas para o turno.
  `PERGUNTAR` devolve a pergunta e o estado, sem `input()`. Logs sem argumentos nem respostas.
- Motivo: valores iniciais da KAN-38, citados na KAN-69; a QA ajusta depois de medir o modelo.
- No código: `MAX_PASSOS` e `MAX_REPETICOES` em `agentes/agente_atendimento/agente.py`. Foi acrescentado um prazo de
  120 s por turno (`SEGUNDOS_POR_TURNO`), que não tem fonte.

### O12. Modo terminal só com `MODO_TERMINAL=1`
- Decisão: o modo terminal exige essa variável e um banco SQLite local. O `.env` guarda só `ID_USUARIO`; nível, área
  e carteira vêm do diretório do mock.
- Motivo: o próprio `agentes/terminal.py` diz que o modo não serve ao produto, onde o back-end monta o usuário.
- No código: `agentes/terminal.py`.

### O13. Lojista fora do escopo
- Decisão: a ferramenta busca a carteira do lojista e a governança decide (função pura). Fora do escopo é
  `permissao_negada`. Para quem só vê a carteira do time, lojista inexistente recebe a mesma resposta; quem vê todas
  recebe `nao_encontrado` para código inexistente.
- Motivo: o N1 não pode descobrir por tentativa quais códigos existem (crítica I3, ataque A-15).
- No código: `lojista.exigir_acesso` e `governanca.lojista_no_escopo`.

## Divergências abertas com a KAN-69 (V1 a V14, mais V15 a V18)

A KAN-69 é o catálogo de casos de teste do Pedro no Jira. As divergências estão em `pesquisa/kan69_testes.md` §5, que
lista 18 (V1 a V18); as quatro últimas entram aqui porque também afetam a demo. Cada linha diz o que o Jira pede, o que
o código faz hoje e o que falta decidir.

- V1. Alçadas e escrita (E15 a E20). A KAN-69 quer alçada testável. Sem escrita na Sprint 2, os casos N3, N6 e N7 valem
  "por construção" (a ferramenta não existe). A proposta P-1 (calcular quem aprova) foi atendida: `calcular_parcelas`
  devolve `analista`, `coordenador` ou `proibido`. As alçadas moram em `ferramentas/financeiro/calcular_parcelas/func.py`,
  não em `mock/regras.py`. O Pedro não registrou aprovação da P-1 (SEM FONTE).
- V2. Dado restrito completo para o N2. Adiado (O2). A demo deve avisar que o N2 também vê mascarado.
- V3. "3 níveis da KAN-33" (E9). Superado pela regra por cargo (O1). O caso E9 vale como "cargo desconhecido é negado".
- V4. Replicar e onboarding guiado. Fora da Sprint 2 (O6). Não há `REPLICAR` em `Acao`.
- V5. Aviso ao dono quando o agente para por limite. O motor para e responde com mensagem fixa. O aviso ao dono e a
  tabela `eventos_erro` são Sprint 3.
- V6. Alerta de acesso de funcionário desligado ou afastado. A decisão é checar a situação a cada pedido, lendo o
  banco (isso é do back-end e ainda não existe). O alerta ao monitoramento é Sprint 3.
- V7. Timeouts (2 min por etapa, 10 min no total, `timeout_segundos` na ficha). Hoje só há 120 s por turno, sem fonte.
  Não existe `timeout_segundos` nas fichas. Decisão pendente do Pedro.
- V8. Nomes dos tipos de erro. A KAN-69 usa `bloqueada_por_politica`, `tempo_esgotado` e outros; o código usa os 7 tipos
  de `ferramentas/base.py`. Os testes seguem o código.
- V9. Admin e Auditor sem área. Resolvido nos perfis. A leitura da auditoria pelo Auditor não tem rota (falta no
  back-end).
- V10. Inexistente contra fora do escopo. Resolvido em `lojista.exigir_acesso` (ver O13).
- V11. A data do mock no prompt. Nada no código diz ao modelo que "hoje" é 15/10/2026. A janela de 90 dias é calculada
  pelo código; o cálculo de "últimos 30 dias" feito pelo modelo fica sem referência. A sugestão da pesquisa é o
  orquestrador injetar a data no contexto do turno. Em aberto.
- V12. Tamanho do mock. Reduzido de propósito (D5).
- V13. Onde ficam os testes. `backend/tests/`, mas o CI ainda não roda pytest (O10).
- V14. Registro que não grava. Resolvido: `governanca.registrar` levanta `RegistroIndisponivel` e a ferramenta nega a
  resposta (O9).
- V15. Idempotência (mesmo pedido enviado duas vezes) e SSE. Sem desenho; pergunta ao Marcelo.
- V16. Liquidação para o N1. Resolvido pela O4.
- V17. Ficha de `consultar_transacoes_cliente`. Janela e carteira agora existem (`lojista.preparar`).
- V18. Prazos. A KAN-69 e a KAN-58 já tinham vencido quando a pesquisa foi feita. Situação atual no Jira: não verificada
  para este arquivo.

## Perguntas abertas

Cada pergunta tem a resposta que o código dá hoje. Quem decide está entre parênteses quando a fonte diz.

1. O dia 90 da janela é inclusivo? O código aceita `data_inicio` igual a `HOJE_DO_MOCK - 90 dias` (17/07/2026) e
   nega 16/07 (`ferramentas/lojista.periodo_permitido`). A pesquisa deixou a confirmação para o Pedro.
2. A entrada de 20% está dentro das parcelas ou vem antes? Hoje `calcular_parcelas` cobra a entrada à parte: do valor
   negociado tira a entrada e divide o resto em N parcelas. O DOC-MOCK §7.9 não diz qual é o certo (L2 da pesquisa),
   e o gabarito do cenário 3 depende disso.
3. Quem aprova entrada abaixo de 20%? O código manda para o coordenador (`quem_aprova`). O DOC-MOCK só diz que o analista
   exige 20% no mínimo. SEM FONTE sobre o aprovador da exceção.
4. E-mail e telefone digitados em texto livre são mascarados? Hoje não. A máscara de texto livre só cobre sequências de
   11 dígitos (CPF) e de 13 a 19 dígitos (cartão); 12 dígitos ou mais de 19 viram `***`. O DOC-MOCK §8.3 só pede
   "detectados e mascarados" para CPF e cartão.
5. `id_cliente` ou `codigo_lojista`? Decidido em H6: continua `id_cliente` para o modelo.
6. Formato da máscara do nome do sócio. Hoje: inicial de cada parte e `***` (`J*** S***`). O DOC-MOCK §8.3 não define
   (SEM FONTE).
7. Alçadas em `mock/regras.py`. Hoje ficam na ferramenta, com a pendência anotada no próprio arquivo. Mover deixa as
   regras todas num lugar só.
8. Escopo por chamados atribuídos. O DOC-MOCK §3.2 fala em carteira, fila e chamados atribuídos; o código só usa as
   carteiras do time (L11 da pesquisa).
9. Reativar um agente pausado. `Plataforma.deprecar` existe; não existe método que reative. Nenhuma fonte diz se pode.
10. Lista de ferramentas do agente de atendimento (KAN-55). Está fixa em 5, sem as 6 novas. O comentário no código diz que
    a lista virá da configuração do agente (KAN-55); falta isso ser feito.
11. Retenção do registro de chamadas e da auditoria. O valor está em branco no código (`[preencher: prazo de retenção]`
    em `governanca.py`) e nos cards (KAN-34, trava 8). SEM FONTE.
12. Preço simulado por token e limite mensal por pessoa (Sprint 3). A regra vem da KAN-16; os números não.
13. O prazo de 120 s por turno do agente vale? Foi escolhido para a demo e ainda não foi medido com o modelo real.
