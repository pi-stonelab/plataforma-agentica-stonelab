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
- Revogada em parte pelo Pedro em 22/11 (H17): a pessoa passa a ver o catálogo filtrado para ela. Continua valendo
  que as ferramentas ficam só no código, nunca no banco.

### D11. Funcionário inativo é barrado em um lugar só
- Decisão: a checagem "o funcionário está ativo?" mora em `ferramentas/diretorio.py` (`buscar_usuario`). O modo terminal
  e o `montar_acesso` do back-end usam essa função. Tudo que não for exatamente `ativo` é negado; diretório fora do ar
  levanta `ConnectionError` e não vira "não encontrado".
- Quem e quando: Pedro, 12/11 ("quero", sobre o ponto 2 da revisão de riscos).
- Motivo: só o `agentes/terminal.py` conferia a situação; `usuario_do_cargo` não. Um `montar_acesso` que montasse o
  usuário por ele deixaria desligado e afastado entrarem.
- No código: `ferramentas/diretorio.py`, `agentes/terminal.py`, `backend/tests/test_ferramentas_diretorio.py`.
  O `montar_acesso` em si é do Marcelo (mensagem pronta em `docs/mensagens-para-o-grupo.md`).

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

### H12. enviar_email em duas fases já na Sprint 2
- Decisão: o `enviar_email` entra ativo na demo, em duas fases: o agente monta a prévia e só quem pediu confirma, fora
  do agente. Tira o `enviar_email` da O6; as outras escritas continuam para a Sprint 3.
- Quem e quando: Pedro, 15/11.
- Motivo: o passo 7 do MVP da demo (KAN-52) pede a prévia com confirmação, e a KAN-59 inclui o e-mail.
- No código: `ferramentas/confirmacoes.py`, `ferramentas/email_smtp.py` (H15), `governanca.ESCRITA_COM_CONFIRMACAO` e
  `agentes/terminal.py::revisar_previas`. Testes em `test_ferramentas_enviar_email.py` e `TestPreviasNoTerminal`.
- Revisão do Enrico no PR do e-mail (15 e 16/11): (1) a prévia só fica visível e confirmável depois que a resposta chega
  ao agente; se o registro final falha ou algo dá erro depois de guardá-la, ela sai da fila (`Ferramenta.concluir`, uma
  decisão só), para não ser confirmada nem duplicada por nova tentativa, e a mensagem ao agente não diz que a ação foi executada; (2) `assunto` e `corpo` saíram de `CAMPOS_NAO_RESTRITOS` e viraram
  `campos_liberados` da ficha do `enviar_email`, para uma ferramenta que leia e-mails continuar negando por padrão;
  uma lista fechada em teste diz quais ferramentas podem liberar quais campos (`test_ferramentas_campos_liberados.py`).
- Em aberto: se o supervisor pode confirmar a prévia de outra pessoa (marcador para o Brenno no `agents.md` da
  ferramenta).

### H13. Marcadores de pendência num formato só
- Decisão: `[A FAZER (quem, frente, card): o quê]` e `[DECIDIR (quem, frente, card): o quê]`, buscáveis por nome.
  `python -m ferramentas.pendencias` lista por pessoa. Os antigos (`[aqui conectamos ...]`, `[preencher ...]`)
  migram aos poucos.
- Quem e quando: Pedro, 15/11.
- No código: `ferramentas/pendencias.py`, `catalogo.PADRAO_MARCADOR` (tira os dois formatos do texto do modelo) e
  `test_ferramentas_pendencias.py`.

### H14. O terminal recebe a resposta do modelo em pedaços
- Decisão: `terminal.chamar_llm` usa `stream: true`. Só vale a resposta que termina com `done: true`; conexão que cai
  antes é `ModeloIndisponivel`, para o motor nunca agir sobre uma ação cortada. O prazo total da chamada é conferido a
  cada pedaço, porque o `timeout` do `requests` conta cada espera e não o total.
- Quem e quando: Pedro, 16/11.
- Motivo: o Cloudflare na frente do Ollama desiste aos ~100 s sem resposta (HTTP 524). Com `stream: false` e o prompt
  crescendo a cada passo, o terceiro passo de um pedido de e-mail estourou (18 s, 61 s e depois 524 aos 126 s) e o
  terminal só mostrava "Modelo indisponível".
- A causa (`HTTP 524`, `ReadTimeout`...) agora vai para o log do terminal, sem URL nem texto do servidor.
- No código: `agentes/terminal.py` (`chamar_llm`, `_juntar_pedacos`, `_modelo_indisponivel`). Testes em
  `TestChamarLlm`, incluindo resposta cortada e prazo total.
- Limite conhecido: o Ollama só manda o primeiro pedaço quando gera o primeiro token. Se a leitura do prompt sozinha
  passar de ~100 s, o 524 volta; aí o caminho é encurtar o prompt, não o streaming.

### H15. O enviar_email envia de verdade por SMTP
- Decisão: o envio do `enviar_email` é só por SMTP (`smtplib`, sem biblioteca nova), configurado no .env. A caixa de
  saída simulada saiu. Sem `EMAIL_SMTP_HOST` o envio fica desligado e o agente nem monta a prévia. Os testes usam um
  servidor SMTP local. Na ficha, `integracoes` continua `google_workspace` e `microsoft_365`. Gmail e Outlook pela
  conta de cada pessoa ficam para os conectores do Google e da Microsoft, que trazem ferramentas próprias.
- Quem envia: a conta da plataforma (`EMAIL_REMETENTE`), com o primeiro nome do funcionário que confirmou no
  remetente exibido ("Ana via Stone") e o e-mail dele no Reply-To: o lojista responde à pessoa. Pôr o e-mail dele no
  From faria o Gmail trocar ou recusar a mensagem. Nome e e-mail vêm de `buscar_contato_funcionario`, só no envio.
- Quem e quando: Pedro, 17/11.
- Motivo: o professor mostrou em aula que o envio não precisa da conta Google de cada pessoa. Assim o e-mail sai de
  verdade sem OAuth por pessoa.
- Segurança: TLS obrigatório fora do localhost, sem volta para texto puro, com o certificado conferido; remetente fixo;
  um destinatário só, do cadastro; assunto em uma linha (a fase 1 recusa quebra de linha, que injetaria cabeçalho);
  erros e logs só com etapa e tipo. Falha antes do envio diz "nada foi enviado"; queda depois do texto diz que o envio
  pode ter saído (`base.EfeitoIncerto`), em vez de mentir. `EMAIL_DESTINO_TESTE` manda tudo a um endereço de teste.
- No código: `ferramentas/email_smtp.py`, `EnviarEmail.efetivar`, `confirmacoes.MENSAGEM_EFEITO_INCERTO`. Testes em
  `test_ferramentas_email_smtp.py`, contra um servidor SMTP em socket local (`apoio_smtp.py`).

### H16. Conectores para as integrações, e as APIs públicas de verdade
- Decisão: cada integração das fichas tem um `Conector` em `ferramentas/integracoes/` (modo `real`, `simulado` ou
  `desligado` pelo .env, disjuntor de 3 falhas e 60 s por serviço, saúde sem segredo e `testar` para quem configura),
  e todas as chamadas HTTP passam por `integracoes/http.py` (hoje `cliente_http.py`, H17). `consultar_endereco_cep` passa a consultar o ViaCEP e
  `consultar_cotacao_moeda` fica ativa, com a PTAX do Banco Central. O modo `simulado` responde sem rede (os 3 CEPs
  de exemplo e cotações ilustrativas).
- O `enviar_email` passa a ter `integracoes = ("email",)`: o envio é por SMTP, e a ficha dizia Google e Microsoft
  (problema conhecido do plano antigo: com os dois na ficha, a queda de um bloqueava quem usa o outro).
- A categoria `cambio` vira comum a todos os cargos com área (`mock/regras.py::CATEGORIAS_COMUNS`), como o CEP:
  cotação oficial é dado público.
- Quem e quando: Pedro, 22/11 (integrações externas reais e completas, com modo simulado para testes).
- Segurança: HTTPS obrigatório fora do localhost; URL base fixa no .env, sem credencial, parâmetro ou fragmento;
  redirecionamento só para a mesma origem; teto de 1 MB; resposta fora do formato vira `integracao_indisponivel`;
  log só com integração, serviço, etapa e tipo. A suíte aponta para servidores locais e recusa conexão fora do
  127.0.0.1 (`backend/tests/conftest.py`).
- No código: `ferramentas/integracoes/`, `catalogo.listar_fichas` e `confirmacoes.confirmacoes_da_execucao`
  (adaptadores do contrato do front, §4.10 e §4.9). Testes em `test_integracoes_*.py` e `test_contrato_interface.py`.

### H17. Catálogo visível para a pessoa, data real na cotação e as correções da revisão do bloco B
- Decisão 1 (Pedro, 22/11): a D10 é revogada na parte "a pessoa não vê as ferramentas". Motivo: o front do professor
  lista o catálogo na criação guiada (`GET /ferramentas`, `frontend/CONTRATO_API.md` §4.10), com `liberada` e
  `motivo`. `catalogo.listar_fichas` devolve o catálogo filtrado para a pessoa, com a descrição para pessoas
  (`descricao_para_pessoa`, quando a ficha tem) e o motivo em linguagem simples (o motivo técnico de
  `governanca.motivo_bloqueio` fica no registro). As ferramentas continuam só no código.
- Decisão 2 (Pedro, 22/11): no modo `real`, a cotação usa a data de hoje de verdade (America/Sao_Paulo), porque é
  dado público real; no `simulado`, o `HOJE_DO_MOCK`, como o resto do mundo simulado. É o único relógio de verdade
  das ferramentas (`ConectorApisPublicas.agora_real`); a suíte o congela no `HOJE_DO_MOCK`. O agente sempre diz o
  dia da cotação.
- Decisões do orquestrador na mesma rodada (revisões de dev e de usuário do bloco B):
  - Integração desligada ou mal configurada tira a ferramenta do índice do modelo; se o modelo insistir, ouve que a
    integração não está ligada e que deve avisar o usuário (nada sobre o .env, que fica só no terminal).
  - O cliente HTTP passa a `cliente_http.py` (o nome `http.py` escondia o módulo do Python ao rodar o arquivo
    direto), com prazo total do pedido, `montar_url`, 4xx fora do disjuntor e escrita sem resposta como
    "pode ter saído".
  - Saúde por serviço, com `sem_chamadas` e `configuracao_invalida`; falha só acusa por 5 minutos sem chamada nova.
  - Uma `Confirmacao` por resposta (`confirmacao_da_execucao`, a mais recente) e a decisão lembrada por 1 hora,
    só com id, pessoa e situação, para o back-end separar 409 de 404. Envio que não saiu não fica como confirmado.
  - Máscara de texto livre: telefone com DDD entre parênteses ou com +55 e CNPJ com pontos e barra ganham a
    máscara do próprio tipo antes da regra por quantidade de dígitos. Risco residual (o mesmo número escrito como
    CPF e como telefone mostra partes diferentes) documentado em `mascara.py`. Revisão sugerida ao Brenno (KAN-63).
- No código: `ferramentas/integracoes/`, `ferramentas/catalogo.py`, `ferramentas/confirmacoes.py`,
  `ferramentas/mascara.py`, `ferramentas/base.py`. Testes em `test_integracoes_*.py`, `test_contrato_interface.py`,
  `test_ferramentas_mascara_texto.py` e `test_ferramentas_mensagens_de_parametro.py`.

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
- 15/11: o `enviar_email` saiu desta lista (H12).

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

## Decisões do bloco A: mock fase 2 e base analítica (22/11, A1 a A8)

Escolhas sem fonte no DOC-MOCK, tomadas para a fase 2 (plano `plano-ferramentas-final.md`, decisão 3 do Pedro).

### A1. Quem vê as categorias novas
- Decisão: `disputa` para o analista de disputas, o especialista N2, o supervisor de atendimento e o coordenador
  financeiro; `satisfacao` para o supervisor de atendimento e o analista de ouvidoria; `indicador_agregado` e
  `metadado` para todo cargo com área; `base_conhecimento` comum a todos.
- Motivo: DOC-MOCK §8.2 (disputas vê chargebacks e Pix; o supervisor vê os indicadores do time; a ouvidoria vê todo
  o histórico) e §6.3 (contestação é "N2 junto com Disputas"). A lista exata é SEM FONTE.
- No código: `mock/regras.py` (`CARGOS`, `CATEGORIAS_DE_QUEM_TEM_AREA`, `CATEGORIAS_COMUNS`).

### A2. Códigos sem prefixo no DOC-MOCK
- Decisão: `PX00001` (caso de Pix), `AC0001` (acordo) e `KB001` (artigo). `R0000001` e `CB00001` seguem o DOC-MOCK §4.
- No código: os CHECK de formato em `mock/modelos.py`.

### A3. O "agora" do mock
- Decisão: `AGORA_DO_MOCK` = 15/10/2026 às 21h, depois de toda venda sorteada. Serve ao cenário 11 ("venda de 10
  minutos atrás") e ao prazo do SLA de chamado aberto. Sem fuso: o mock é todo horário de Brasília.
- No código: `mock/regras.py`.

### A4. Prazo do SLA
- Decisão: dia útil de segunda a sexta, sem feriado (a mesma escolha da liquidação); o prazo conta da abertura e não
  para em "aguardando lojista"; a ouvidoria tem 10 dias úteis (sem a prorrogação de 15 dias).
- Motivo: o DOC-MOCK §6.4 diz que o relógio para, mas o mock não guarda o histórico de situações do chamado.
- No código: `regras.prazo_do_chamado`, `chamados.prazo_em`.

### A5. Antecipação do plano Negociado
- Decisão: 2,29% ao mês (o Volume menos 20 pontos-base, a mesma escolha do MDR). O DOC-MOCK §2.2 só diz "sempre abaixo
  do Volume". A antecipação só é simulada; não há tabela de antecipações executadas.
- No código: `regras.TAXA_ANTECIPACAO_PONTOS_BASE`.

### A6. Alçadas no mock
- Decisão: `regras.alcada_do_acordo` aplica o §7.9 (dupla aprovação acima de R$ 10.000; coordenador para desconto no
  principal, mais de 6 parcelas, entrada abaixo de 20% ou perdão de encargos em dívida acima de R$ 2.000; acima de 12
  parcelas ou de 10% de desconto sobre o principal, proibido).
  `calcular_parcelas` usa estas, pela fachada, desde o bloco C (C15); antes tinha as suas constantes.
- No código: `mock/regras.py`, `acordos.alcada`.

### A7. Base analítica agregada
- Decisão: a base analítica guarda agregados (vendas por dia e modalidade, chamados por dia, fila e prioridade,
  contestações por mês e lojista), não a cópia linha a linha. Vai até ontem; a falha "dado desatualizado" tira mais
  3 dias. Assim ela atende indicadores e relatórios sem carregar dado de pessoa.
- Motivo: DOC-MOCK §4 ("serve para indicadores e relatórios, nunca para atender um lojista agora"). O formato é SEM
  FONTE.
- No código: tabelas `analitica_*`, `consultas.totais_de_vendas`, `chamados_por_fila`, `contestacoes_por_mes`.

### A8. Satisfação e base de conhecimento
- Decisão: 60% dos chamados resolvidos respondem a pesquisa, metade com comentário (restrito, texto livre). Os
  artigos de ajuda (18 depois da A10) são texto da equipe a partir das regras do DOC-MOCK, públicos, com os números
  de `regras.py`.
- No código: `gerar.criar_pesquisas_satisfacao`, `mock/base_conhecimento.py`.

## Correções do bloco A depois da revisão em dois olhares (23/11, A9 a A14)

### A9. Receitas e despesas no relatório semanal (KAN-14 caso 4)
- Decisão: o mock não tem despesa nem pagamento de fatura. O relatório semanal mostra o resultado da Stone:
  receitas são o MDR das vendas e o aluguel e as tarifas faturados (pelo vencimento); perdas são a inadimplência nova
  (o que venceu no período e segue vencido), as concessões em acordos ativos, quitados ou quebrados (perdão de
  encargos e desconto no principal, pelo dia do acordo) e os chargebacks perdidos ou aceitos (pelo aviso). A maior
  venda do período acompanha, para explicar picos.
- Motivo: SEM FONTE; o caso de uso só diz "receitas e despesas". A Milene (produto) valida.
- No código: `analitica_resultado_diario`, `consultas.resultado_por_periodo`, `dados_sinteticos.resumo_de_resultado`.

### A10. Base de conhecimento falando com o lojista
- Decisão: os artigos são de uma central de ajuda pública ("você"), sem procedimento interno, e a busca conta as
  palavras inteiras da pergunta (sem acento, sem plural simples, sem palavras vazias) no título, na categoria, no
  texto e em sinônimos escritos pela equipe, com o título valendo o dobro.
- Motivo: o caso de uso 1 da KAN-14 é responder a dúvida do lojista; a busca por trecho achava "médio" para "med" e
  não achava "minha maquininha não liga".
- No código: `mock/base_conhecimento.py`, `consultas.buscar_artigos`, `consultas.palavras_de_busca`.

### A11. Antecipação: o que entra e como o desconto é calculado
- Decisão: entram as parcelas previstas que caem depois do dia do crédito (1 dia útil); a do próprio dia já chega
  nele. O desconto é calculado parcela por parcela (§7.4) e arredondado ao centavo em cada uma.
- No código: `regras.data_de_credito_da_antecipacao`, `regras.desconto_da_antecipacao_centavos`,
  `dados_sinteticos.simulacao_de_antecipacao`.

### A12. Contestações de um lojista são dado de disputa
- Decisão: a base analítica de contestações por lojista sai por uma função própria
  (`contestacoes_do_lojista_por_mes`), cuja ficha pede `disputa` e passa pelas portas do lojista;
  `indicador_agregado` só vê o total da Stone.
- Motivo: revisão de dev do bloco A (um MEI está muito perto de pessoa natural). Levar ao Brenno.

### A13. Comentários de satisfação por categoria
- Decisão: cada comentário sorteado combina com a categoria do chamado e a faixa da nota; os gerais só entram quando
  a categoria não tem. A concentração no varejo vem dos chamados da fase 1 e não muda.
- No código: `gerar.COMENTARIOS_POR_CATEGORIA`, `gerar._opcoes_de_comentario`.

### A14. Quarta recusa da antecipação e quem aprova o acordo da analista
- Decisão: a M00019 tem a conta de recebimento em verificação (trocada ontem), para a recusa por conta em
  verificação existir no mundo. O AC0004 tem a mesma analista como solicitante e aprovadora: dentro da alçada dela,
  a analista fecha sozinha (§7.9); "quem pediu nunca aprova" vale para a dupla aprovação.
- No código: `gerar.CONTA_EM_VERIFICACAO`, `gerar.ACORDOS`.

## Decisões do bloco E1: Jira, Slack, Telegram e leitura de e-mail (23/11, E1 a E5)

Tomadas pelo orquestrador; sem fonte, para o Pedro e o Brenno validarem.

### E1. Quem usa as integrações internas
- Decisão: categorias novas `chamado_interno` (Jira) e `comunicacao_interna` (Slack e Telegram), liberadas para
  todo cargo com área (`regras.CATEGORIAS_DE_TRABALHO_INTERNO`). Admin, auditor e gestor de acessos não usam
  ferramentas de dado e continuam de fora.
- Motivo: abrir chamado para outro time e avisar colegas é trabalho de qualquer funcionário; o risco está no
  destino e no conteúdo, que já ficam presos à lista do `.env` e à máscara.

### E2. Destino só por lista do `.env`
- Decisão: projeto e tipo do Jira (`JIRA_PROJETOS`, `JIRA_TIPOS`), canais do Slack (`SLACK_CANAIS`) e chats do
  Telegram (`TELEGRAM_CHATS`) vêm do `.env`. O modelo e a pessoa só usam a chave do projeto ou o apelido; o ID do
  canal ou do chat nunca chega ao modelo. Inclusive para ler: chave de projeto fora da lista é recusada.
- Motivo: o modelo não pode mandar dado para fora (LGPD, E58 da KAN-69) nem ler projeto que não é da plataforma.

### E3. Assinatura nas mensagens
- Decisão: Slack e Telegram saem assinados com o primeiro nome de quem confirmou ("— Ana, pela Plataforma
  Agêntica"), e a assinatura já aparece na prévia. O Jira não leva assinatura no texto: o chamado é aberto pela
  conta de serviço e o registro da plataforma guarda quem confirmou.
- Motivo: o bot é da plataforma; quem lê o canal precisa saber quem pediu.

### E4. Credencial e modo
- Decisão: as quatro integrações usam a credencial da plataforma (conta de serviço ou bot). Preencher o token liga
  a integração; sem ele, fica desligada e as ferramentas somem do índice do modelo. `<SISTEMA>_MODO=simulado` liga
  uma versão em memória para demo e testes, sempre identificada em `fonte`.

### E6. Leitura de e-mail separada do envio, com o relógio de verdade
- Decisão: `buscar_emails` lê a caixa da plataforma por IMAP numa integração própria (`email_leitura`), não na do
  envio (`email`): outro servidor e outra credencial, e uma queda de um não pausa o outro. Só procura remetentes
  do cadastro do lojista (mais o `EMAIL_DESTINO_TESTE` da demo), abre a pasta só para leitura e devolve assunto e
  trecho juntos no campo `texto` (texto livre mascarado), porque a lista de campos classificados é fechada e
  leitura não libera campo. Numa caixa real, o período padrão conta do dia de verdade (`agora_real`, como a
  cotação na H17); a suíte congela esse relógio no `HOJE_DO_MOCK`.

### E5. Escrita sem redirecionamento
- Decisão: o cliente HTTP não segue redirecionamento em escrita, e um 2xx de escrita com corpo ilegível vira "pode
  ter saído" (`EfeitoIncerto`): o servidor já recebeu o pedido, e repetir poderia duplicar a ação.

## Decisões do bloco C: leitura e cálculo sobre o mock (23/11, C1 a C6)

Tomadas pelo orquestrador ao implementar as ferramentas de leitura e cálculo, sem fonte que as decida. Ficam para o
Pedro confirmar.

### C1. `consultar_saldo_conta` sai do catálogo
- Decisão: a ficha planejada foi removida. A Conta Stone não existe no mock, e o saldo que o DOC-MOCK cita é o da
  agenda de recebíveis, que `consultar_agenda_recebiveis` mostra.
- No código: a pasta `ferramentas/financeiro/consultar_saldo_conta/` deixou de existir.

### C2. Nomes `*_ticket` viram `*_chamado`
- Decisão: `consultar_ticket` virou `consultar_chamado` e `resumir_volume_tickets` virou `resumir_volume_chamados`,
  o vocabulário do mock e de `listar_chamados_cliente`. As três de escrita são renomeadas pelo bloco D.
- Efeito fora da pasta: o front do professor cita `consultar_ticket` e `listar_tickets_cliente` no seed
  (`frontend/CONTRATO_API.md`); vale avisar pelo Jira.

### C3. Quem alcança os indicadores
- Decisão: `resumir_receita_periodo` é do financeiro (N1 em diante); `consultar_taxa_contestacao_mensal` só do
  coordenador financeiro (N2 do financeiro); `resumir_volume_chamados` do N2 do atendimento (supervisor e
  especialista N2). O DOC-MOCK §8.2 diz que o supervisor "vê os indicadores do time"; o especialista N2 entra porque
  a ficha decide por nível, não por cargo.
- No código: as fichas e `gabaritos.FERRAMENTAS_DO_CARGO`.

### C4. Responsável por um conjunto de dados
- Decisão: o responsável é o sistema dono da tabela (`cadastro`, `core`, `cobranca`, `disputas`, `crm`,
  `diretorio`, `analitica`). O mock não tem um time nomeado por sistema, e a ferramenta nunca devolve nome de pessoa.
- No código: `consultar_responsavel_conjunto`, `ferramentas/dicionario.py`.

### C5. Fórmula do ROI
- Decisão: ROI simples no horizonte pedido (12 meses se faltar): (ganho total menos custo total) dividido pelo custo
  total, com o custo de implantação somado ao custo. O payback são os meses inteiros, arredondados para cima, para o
  ganho líquido mensal pagar a implantação. Sem desconto do dinheiro no tempo. Fonte da necessidade: "Gerir: controlar
  custos, retorno de investimento" da proposta da Stone e a KAN-16; a fórmula é nossa.
- No código: `ferramentas/dados_e_indicadores/calcular_roi/func.py`.

### C6. Períodos padrão das ferramentas de indicadores
- Decisão: sem datas, o relatório vale os últimos 7 dias até ontem; o volume de chamados, de segunda-feira da semana
  do hoje do mock até ontem; a taxa de chargeback, os últimos 6 meses até o mês atual. Teto de 92 dias e de 24 meses.
- No código: `ferramentas/indicadores.py` e as três fichas.

## Correções do bloco C depois da revisão (24/11, C7 a C14)

Aplicadas depois da revisão do bloco C. Ficam para o Pedro confirmar.

### C7. Antecipação recusada também com a conta de recebimento inválida
- Decisão: `simular_antecipacao` recusa (`pode_antecipar` falso, com motivo) quando a conta de recebimento é
  `invalida`. O §7.4 lista quatro recusas e não cita esta; o §7.3 diz que com a conta inválida a liquidação falha e o
  dinheiro fica retido, então não faz sentido simular um dinheiro que não sai.
- Conferido contra o cenário 1 (M00001, a única com conta inválida): o DOC-MOCK §9 espera cruzar cadastro, liquidação e
  chamado e passar para o N2. Nenhum cenário espera simular antecipação para a M00001, e os cenários de antecipação
  (M00004 e M00003) não mudam.
- No código: `regras.ROTULOS_DOS_MOTIVOS_DE_RECUSA_DA_ANTECIPACAO`, `consultas.motivos_de_recusa_da_antecipacao`.

### C8. Verificação de identidade: tudo o que for informado precisa conferir
- Decisão: telefone e e-mail informados juntos precisam ser do MESMO contato cadastrado (cenário 6, §6.6: número fora
  do cadastro com o e-mail do sócio não passa). O telefone é comparado como DDD + número, sem `+55`, `0` de discagem
  ou pontuação, dos dois lados.
- No código: `consultas.normalizar_telefone`, `consultas.contato_confere`.

### C9. O limite de 1% de chargeback é por lojista
- Decisão: `consultar_taxa_contestacao_mensal` (agregado da Stone) mostra só a taxa e a tendência. Quem compara com o
  limite do §7.6 é a nova `consultar_taxa_contestacao_cliente` (categoria `disputa`, escopo de carteira), pelas
  quantidades (`chargebacks * 100 > vendas`), sem o arredondamento da taxa.
- No código: `financeiro/consultar_taxa_contestacao_cliente`, `dados_sinteticos.contestacoes_do_lojista_por_mes`.

### C10. Respostas grandes: teto do nosso lado e aviso para a frente de agentes
- Decisão: o agente corta cada resultado e cada leitura em 6000 caracteres (`MAX_CHARS_MD`, em `agentes/`), e um JSON
  cortado no meio engana o modelo. Do nosso lado: (a) `ferramentas/tamanho.py` limita o que `Ferramenta.executar`
  devolve a 5000 caracteres, tirando itens do fim da maior lista e marcando `truncado`, `cortados_por_tamanho` e
  `aviso_de_tamanho` (os totais da ferramenta continuam contando tudo); (b) teto de itens por ferramenta quando cada
  item é grande: `buscar_conjuntos_dados` 20, `consultar_agenda_recebiveis` 30 e `consultar_base_conhecimento` 10
  (com 50 as duas primeiras passavam de 6000). A mensagem de limite sempre diz o teto da ferramenta.
- Achado que mudou um teste: `consultar_transacoes_cliente` com `limite=50` já passava de 6000 caracteres; agora vem
  com menos linhas, `truncado` verdadeiro e o total real (`test_a08_...`).
- Aviso para Christopher e Isack (frente 3, não mexemos em `agentes/`): o ÍNDICE que o agente lê também é cortado em
  6000. Medido em 24/11 com o agente geral: supervisor de atendimento 5832, especialista N2 5706, coordenador financeiro
  5564 caracteres. Cada ferramenta nova acrescenta cerca de 170 e, com mais duas ou três, o fim do índice some sem
  aviso. Sugestão: o índice mostrar só as áreas e a pessoa (ou o modelo) abrir a área com `LER`, que já existe
  (`catalogo.ler("<area>")`), ou subir o teto do índice. Decisão deles.
- No código: `ferramentas/tamanho.py`, `lojista.limite_pedido` (parâmetro `maximo`), as três fichas.

### C11. A cobrança vê só o saldo da agenda
- Decisão: o §8.2 diz que a cobrança vê "só faturas, pagamentos, acordos e o saldo da agenda". Nasce a categoria
  `saldo_agenda` e a ferramenta `consultar_saldo_agenda` (só o resumo por situação, sem parcelas). A cobrança troca
  `agenda_recebiveis` por `saldo_agenda` e perde `consultar_agenda_recebiveis` e `simular_antecipacao` (o §8.2 dá a
  simulação ao atendimento, ao analista de recebíveis e ao coordenador). Quem tem `agenda_recebiveis` tem também
  `saldo_agenda`.
- Efeito: `analista_cobranca` não alcança mais a agenda parcela a parcela nem a simulação. Se a cobrança precisar da
  simulação na negociação de acordo, é pergunta para o Pedro (SEM FONTE: o §8.2 não a dá).
- No código: `mock/regras.py` (`CATEGORIAS_DADO`, `CARGOS`), `ferramentas/financeiro/consultar_saldo_agenda`.

### C12. Padrão dos formatos de saída
- Decisão: código do lojista sempre `id_cliente` nas ferramentas do bloco C (antes, `codigo` aparecia ao lado do
  `codigo` do chamado ou do chargeback); percentual sempre número com duas casas em campo `*_percentual` (antes havia
  texto `"2,99%"`, número `20.0` e `328.6`); `alcada` no lugar de `quem_aprova` (o nome de `listar_acordos` e de
  `regras.alcada_do_acordo`); `total_encontrado` quando a resposta tem uma lista só e `total_de_<lista>` quando tem duas.
  A média da satisfação virou número (`3.52`). O padrão está em `ferramentas/CLAUDE.md`.
- Não mexe no contrato com o front: `frontend/CONTRATO_API.md` não descreve o `dados` de nenhuma ferramenta de dado.
  O agente de atendimento não lê esses campos por nome (conferido em `agentes/`, só testes de `backend/tests/` os liam).

### C13. Pergunta: migrar `codigo` das ferramentas dos blocos A e B para `id_cliente`?
- Hoje `consultar_liquidacoes_cliente`, `consultar_transacoes_cliente`, `listar_faturas_em_atraso`,
  `listar_chamados_cliente` e `consultar_contatos_lojista` devolvem o lojista em `codigo`, e
  `test_agente_varias_ferramentas.py` lê `"codigo": "M..."` de uma observação do `consultar_cliente` (aí o `codigo` é
  da própria entidade, que fica). Migrar as cinco é pequeno, mas muda saída que a frente de agentes já viu em
  avaliações. Fica para o Pedro decidir.

### C14. Campos genéricos saem da lista global da máscara
- Decisão: `aviso`, `orientacao`, `explicacao`, `agenda`, `pago`, `diferenca`, `desconto`, `valor_antecipado`, `mdr`,
  `data_inicio`, `data_fim`, `mes_inicio`, `mes_fim`, `nome_do_sistema`, `derivados` e outros saíram de
  `CAMPOS_NAO_RESTRITOS` (valiam para toda ferramenta, e um texto de lojista guardado num campo com esse nome passaria
  sem virar `***`). Cada um foi para `campos_liberados` da ficha das ferramentas que o devolvem, e a lista fechada
  de `test_ferramentas_campos_liberados.py` agora cobre também essas fichas (só texto da plataforma).
- No código: `mock/regras.py` e as 11 fichas.

### C15. Alçadas num lugar só e contagem de ferramentas
- Decisão: `calcular_parcelas` já usava `regras.alcada_do_acordo` (inclui `dupla_aprovacao` e o perdão de encargos). Os
  textos antigos (V1, A6, pergunta 7, o comentário em `mock/regras.py` e a primeira frase do `agents.md` da
  ferramenta) diziam o contrário e foram corrigidos. Contagem na época: 51 ferramentas, 33 ativas e 18 esqueletos
  (hoje, depois da junção dos blocos C, D e E1: 56, 47 e 9, em `ferramentas/CLAUDE.md` e `ferramentas/agents.md`). O `CLAUDE.md` da raiz (do Marcelo) ainda diz "43 ferramentas, 11
  ativas": não é nosso, vale avisar no Jira.

## Decisões do bloco D: escrita com confirmação no mock (23/11, W1 a W6)

Escolhas sem fonte no DOC-MOCK para as 8 escritas do bloco D (plano `plano-ferramentas-final.md`).

### W1. Quem executa a antecipação
- Decisão: `executar_antecipacao` é de nível N2 com a categoria `agenda_recebiveis`: especialista N2, supervisor de
  atendimento e coordenador financeiro. O N1 só registra o pedido (`registrar_pedido_antecipacao`).
- Motivo: DOC-MOCK §7.4 ("o N1 simula; a execução fica com o N2, com o pedido do lojista registrado"). O §8.2 dá
  "antecipações" à analista de recebíveis, que é N1; a lista exata é SEM FONTE.
- No código: ficha de `ferramentas/financeiro/executar_antecipacao/func.py`.

### W2. Pedido de antecipação recusado não vira chamado
- Decisão: se a simulação tem motivo de recusa (§7.4), `registrar_pedido_antecipacao` recusa já na prévia, com o
  motivo, em vez de abrir um chamado que o N2 teria de recusar.
- No código: `registrar_pedido_antecipacao.montar`.

### W3. A ouvidoria abre e escreve em chamados
- Decisão: a analista de ouvidoria abre, escreve e muda a situação de chamados (o caso da ouvidoria só ela resolve).
  Não registra pedido de antecipação, porque não vê a agenda (A1).
- Motivo: `regras.NIVEL_DE_ATENDIMENTO_DO_CARGO` já põe a ouvidoria entre quem atende; o DOC-MOCK §6.5 não restringe.
- No código: `gabaritos.FERRAMENTAS_DO_CARGO`.

### W4. A prévia ensaia a gravação
- Decisão: a prévia de toda escrita no mock roda a gravação de verdade numa transação desfeita no fim
  (`mock/escritas.ensaiar`), para recusar com a mesma frase o que a confirmação recusaria (conta inválida no
  reprocessamento, passagem fora do ciclo, caso da ouvidoria, alçada).
- Motivo: a regra que o Enrico cobrou no `enviar_email` (prévia aceita e confirmação recusada faz a pessoa pedir tudo
  de novo).
- No código: `ferramentas/escritas_sinteticas.ensaiar`; `montar` de cada escrita.

### W5. Booleanos como "sim" ou "não"
- Decisão: `impede_vender`, `suspeita_fraude` e `perdoar_encargos` são texto `sim`/`não` (ausente é não), porque a
  ficha só tem os tipos texto, inteiro, decimal e data.
- No código: `escritas_sinteticas.sim_ou_nao`.

### W6. Teto do índice do modelo
- Decisão: o teste do tamanho do índice deixou de ter um teto fixo para o pior caso (era 3500, subiu para 4000 com as
  8 escritas). Depois da junção com os blocos C e E1 vale o controle por ferramenta de
  `test_catalogo_indice.py`: frase curta (até 160 caracteres) e um custo fixo por linha. O problema de fundo continua
  em aberto: o agente geral lista o catálogo inteiro e o índice passa de 6000 caracteres (ver C10). Falta decidir
  (Pedro, com agentes) se o índice mostra só a lista do agente, se é dividido por área ou se o teto sobe.
- No código: `backend/tests/test_catalogo_indice.py`.

## Divergências abertas com a KAN-69 (V1 a V14, mais V15 a V18)

A KAN-69 é o catálogo de casos de teste do Pedro no Jira. As divergências estão em `pesquisa/kan69_testes.md` §5, que
lista 18 (V1 a V18); as quatro últimas entram aqui porque também afetam a demo. Cada linha diz o que o Jira pede, o que
o código faz hoje e o que falta decidir.

- V1. Alçadas e escrita (E15 a E20). A KAN-69 quer alçada testável. Sem escrita na Sprint 2, os casos N3, N6 e N7 valem
  "por construção" (a ferramenta não existe). A proposta P-1 (calcular quem aprova) foi atendida: `calcular_parcelas`
  devolve `alcada` (`analista`, `coordenador`, `dupla_aprovacao` ou `proibido`). As alçadas moram em
  `mock/regras.py::alcada_do_acordo` (a ferramenta só explica a decisão em `motivo`; C15). O Pedro não registrou
  aprovação da P-1 (SEM FONTE).
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
3. Quem aprova entrada abaixo de 20%? O código manda para o coordenador (`alcada`). O DOC-MOCK só diz que o analista
   exige 20% no mínimo. SEM FONTE sobre o aprovador da exceção.
4. E-mail e telefone digitados em texto livre são mascarados? Hoje não. A máscara de texto livre só cobre sequências de
   11 dígitos (CPF) e de 13 a 19 dígitos (cartão); 12 dígitos ou mais de 19 viram `***`. O DOC-MOCK §8.3 só pede
   "detectados e mascarados" para CPF e cartão.
5. `id_cliente` ou `codigo_lojista`? Decidido em H6: continua `id_cliente` para o modelo.
6. Formato da máscara do nome do sócio. Hoje: inicial de cada parte e `***` (`J*** S***`). O DOC-MOCK §8.3 não define
   (SEM FONTE).
7. Alçadas em `mock/regras.py`. Resolvida no bloco C (C15): `calcular_parcelas` usa `regras.alcada_do_acordo` pela
   fachada, com `dupla_aprovacao` e o perdão de encargos, e as regras ficam num lugar só.
8. Escopo por chamados atribuídos. O DOC-MOCK §3.2 fala em carteira, fila e chamados atribuídos; o código só usa as
   carteiras do time (L11 da pesquisa).
9. Reativar um agente pausado. `Plataforma.deprecar` existe; não existe método que reative. Nenhuma fonte diz se pode.
10. Lista de ferramentas do agente de atendimento (KAN-55). Está fixa em 5, sem as 6 novas. O comentário no código diz que
    a lista virá da configuração do agente (KAN-55); falta isso ser feito.
11. Retenção do registro de chamadas e da auditoria. O valor está em branco no código (`[preencher: prazo de retenção]`
    em `governanca.py`) e nos cards (KAN-34, trava 8). SEM FONTE.
12. Preço simulado por token e limite mensal por pessoa (Sprint 3). A regra vem da KAN-16; os números não.
13. O prazo de 120 s por turno do agente vale? Foi escolhido para a demo e ainda não foi medido com o modelo real.
14. Fatura com exatamente 15 dias de atraso bloqueia a antecipação? O §7.4 diz "fatura vencida há mais de 15 dias" (o
    código usa isso: com 15 dias ainda antecipa, com 16 recusa) e a régua do §7.5 diz "15 dias: antecipação
    bloqueada". As duas frases discordam no dia 15. Não mudamos: `test_fatura_com_15_dias_exatos_...` fixa o
    comportamento atual. Se o Pedro escolher o §7.5, é trocar `<` por `<=` em `mock/consultas.py::
    motivos_de_recusa_da_antecipacao` e o teste.
15. Risco de oráculo em `verificar_identidade_contato`. A ferramenta responde só "confere" ou "não confere", mas quem
    tem acesso ao agente pode chutar números de telefone ou e-mails de um lojista e ver qual confere, até achar um
    contato cadastrado (e a resposta `confere` libera o resto do atendimento). Mitigações que não fizemos: limite de
    tentativas por pessoa e por lojista (o registro já guarda quem chamou, sem o contato), alerta ao Monitoramento
    depois de N falhas seguidas e confirmação do CNPJ junto (§6.6 já pede o CNPJ e o código no contato). O registro
    nunca guarda o telefone nem o e-mail informados. Decisão e dono: Pedro com o Brenno (segurança) e o Enrico (alertas).
