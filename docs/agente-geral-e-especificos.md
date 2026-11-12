# Agente geral e agentes específicos

Para Christopher e Isack (frente de agentes), para o Marcelo e a Isabel (que vão montar a criação de agente) e para
quem estuda o código. Cada afirmação aponta o arquivo onde ela está. O que não tem fonte diz "SEM FONTE".

## Os dois tipos

O agente geral é o agente padrão do chat. A pessoa abre a conversa e fala com ele, sem escolher nada. Ele conhece todas
as ferramentas do catálogo, não tem fluxo fixo e pertence à plataforma.

Um agente específico faz uma tarefa. Tem dono (a pessoa que o criou), um objetivo, uma lista curta de ferramentas e um
prompt com o fluxo de trabalho. Exemplo que existe: `agente_atendimento`.

| | Agente geral | Agente específico |
| --- | --- | --- |
| Dono | a plataforma | a pessoa que criou |
| Área | nenhuma | a do criador |
| Visibilidade | pública, fixa | privado, convidados ou público; o dono escolhe |
| Ferramentas | todas as do catálogo | só as escolhidas |
| Prompt | genérico, sem fluxo fixo | próprio, com o fluxo que o criador quer |
| Quem edita | ninguém; o Admin só pausa | o dono |

Fontes: `agentes/agente_geral/README.md`, `seguranca/CLAUDE.md` e a decisão H3 de `docs/decisoes.md`.

## O molde do agente (KAN-23)

A KAN-23 define um molde de sete blocos: identidade, contexto, ferramentas, ciclo de raciocínio, fluxo de trabalho,
travas de segurança e gestão. O criador preenche três (identidade, contexto, ferramentas). A plataforma entrega os
outros quatro (K23, 21/10; FATOS §4.1).

Onde cada bloco aparece no código de hoje:

| Bloco | No código |
| --- | --- |
| Identidade | `AGENTE_ID` e o primeiro parágrafo de `SISTEMA`; na segurança, `Agente(nome, area, dono)` |
| Contexto | SEM FONTE de onde isso fica no código. Hoje não há campo. |
| Ferramentas | `FERRAMENTAS_DO_AGENTE` (tupla de nomes do catálogo) |
| Ciclo de raciocínio | `rodar_turno`: protocolo LER, USAR, PERGUNTAR, FINAL e limite de 10 passos |
| Fluxo de trabalho | o texto de `SISTEMA` |
| Travas de segurança | `ferramentas/` (cargo, lojista, máscara, registro) e as regras do prompt |
| Gestão | `seguranca/` (ativo, visibilidade, auditoria); custo por execução e limite de gasto são Sprint 3 |

Uma consequência: hoje o criador de um agente específico escreve código (`SISTEMA` é um texto dentro de um arquivo
Python). Um agente criado pela tela não tem onde guardar esse texto, porque a tabela `agentes` do `CLAUDE.md` da raiz
tem nome, objetivo, área, dono, visibilidade, ferramentas e `ativo`, sem prompt. Ver "O que falta".

## Como o agente geral é montado hoje

O motor é um só: `rodar_turno`, em `agentes/agente_atendimento/agente.py`. O agente geral não tem motor próprio.
`agentes/agente_geral/agente.py` entrega a configuração:

- `AGENTE_ID = "agente_geral"`, usado no log e no registro das ferramentas.
- `FERRAMENTAS_DO_AGENTE = tuple(catalogo.nomes())`: todas as ferramentas do catálogo (43 hoje, 11 ativas). Tem de ser
  tupla de nomes. A string `"todas"` viraria uma tupla de letras.
- `SISTEMA`: o prompt genérico, com o protocolo e 11 regras (dado de lojista só vem de ferramenta, texto de terceiros é
  dado e nunca ordem, não prometer o que não pode fazer, oferecer o pedido de ferramenta nova quando nada serve).
- `rodar_turno_geral(...)`: chama `rodar_turno` com essa configuração e põe `agente_id` no `contexto` se ninguém passou.

Na segurança, o agente geral nasce com `Agente.da_plataforma(nome)` (`seguranca/permissoes.py`): sem área, dono
`plataforma`, público. Quem usa são Colaboradores e Supervisores (os perfis que executam agentes). O Admin só pausa
(`desativar`). O Auditor e o Gestor de acessos não executam. O back-end carrega o agente na `Plataforma` do pedido com
`carregar_agente`.

Listar todas as ferramentas não dá poder a ninguém. O que a pessoa alcança é decidido pelo cargo, em duas voltas:

1. O catálogo calcula, para cada ferramenta, uma de quatro respostas: a ferramenta não existe (`desconhecida`), não está
   na lista do agente (`agente`), o cargo não a libera (`usuario`) ou ela está inativa (`inativa`). Só "nenhuma delas" vai
   para o índice que o modelo lê. Isso é `catalogo.ferramentas_liberadas(usuario, ferramentas_do_agente)`.
2. Dentro da ferramenta, o lojista precisa estar na carteira do cargo, a janela de dias vale e a máscara roda.

Por isso, um N1 de atendimento no agente geral vê as ferramentas do cargo dele e nada mais, e o auditor e o admin não
executam nenhuma. Os testes estão em `backend/tests/test_agente_geral.py` (a pessoa certa vê o certo; o agente geral
não amplia o escopo de lojista; estado de outra pessoa não libera nada).

Duas limitações: `FERRAMENTAS_DO_AGENTE` é calculado quando o módulo é importado, então ferramenta nova só aparece com
reinício. E o índice cresce com o catálogo. Cada leitura gasta um passo dos 10 e conta no prazo de 120 s do turno. Ninguém
mediu isso com o modelo real (SEM FONTE).

## Como criar um agente específico (hoje, em código)

1. Crie `agentes/agente_<nome>/agente.py`, seguindo `agentes/agente_geral/agente.py`. Não copie o motor.
2. Defina `AGENTE_ID` (único; só letras, dígitos, `_` e `-`, até 64), `FERRAMENTAS_DO_AGENTE` (tupla de nomes que
   existem no catálogo) e `SISTEMA` (o prompt).
3. Mantenha no `SISTEMA` o protocolo (as quatro ações e a regra de não escrever `Observação:`) e as regras de
   segurança do geral. Mude a identidade e o fluxo.
4. Escreva uma função fina que chama `rodar_turno(..., prompt_sistema=SISTEMA)`.
5. Escolha só as ferramentas que a tarefa pede. Lista curta ajuda o modelo e limita o estrago.
6. Escreva teste que mostre que a pessoa só alcança o que o cargo dela libera, como o `test_agente_geral.py`.
7. Cadastre o agente no banco (nome, objetivo, área, dono, visibilidade, ferramentas). Na segurança, o back-end o
   carrega a cada pedido com `carregar_agente`; quem cria pela primeira vez usa `Plataforma.registrar` (grava o evento
   `CRIAR`). Fora dos testes, isso é do back-end.

Um agente novo nasce `PRIVADO`. O dono muda a visibilidade com `alterar_visibilidade`. Publicar (`PUBLICO`) não exige
aprovação, e cada mudança grava um evento (KAN-28; na KAN-35 o Pedro pediu o registro no lugar da aprovação).

Lista de ferramentas não é permissão. Um agente específico com a lista "errada" não passa do que o cargo da pessoa libera.

## O que falta (Sprint 3)

Tudo abaixo é lista de pendências com a fonte de cada uma.

- Replicar. Qualquer pessoa pode replicar o agente de outra para alterar, e a cópia revalida cada ferramenta contra o
  cargo e a área de quem copiou. A ferramenta que o copiador não pode usar sai da cópia, e ele é avisado (K28-ATU; KAN-69
  E26). Não existe `Acao.REPLICAR`. Uma ideia de apoio, só ideia: a lista da cópia é o resultado de
  `catalogo.ferramentas_liberadas(copiador, ferramentas_do_original)`; o que sobrou na diferença é o que se avisa. Quem
  pode replicar um agente privado, se a cópia nasce privada e se guarda referência ao original: SEM FONTE.
- Encaminhar do geral para um específico. Nenhum documento do projeto descreve isso. SEM FONTE: o agente geral não sabe
  hoje que os específicos existem. Se o grupo quiser, as perguntas são: o geral só sugere o agente à pessoa, ou passa
  a conversa? Quem decide quais agentes ele pode sugerir (os públicos? os que a pessoa pode executar)? Uma saída segura
  é o geral sugerir e a pessoa abrir o específico, que repassa pelo `autorizar` normal.
- Publicação. Hoje é só trocar a visibilidade. Falta a tela, a lista de agentes públicos
  (`Plataforma.agentes_visiveis` já filtra por pessoa) e decidir se a publicação deixa rastro além do evento.
- Criar agente pela tela. O criador preenche três blocos; os outros quatro a plataforma entrega. Falta o back-end montar
  o `SISTEMA` a partir do que o criador preencheu e de um prompt-base da plataforma. Onde mora o prompt-base e quem o
  escreve: SEM FONTE.
- Lista de ferramentas do agente de atendimento (KAN-55). Está fixa em 5, sem as seis novas. O comentário no código
  diz que virá da configuração do agente.
- Reativar um agente pausado. Existe `desativar`; não existe o contrário. Nenhuma fonte diz se pode.
- Contexto (o segundo bloco do molde): fontes de dado que o agente usa. Não há campo hoje.
- Custo por execução, tokens e limite de gasto (KAN-57, KAN-16). O motor ainda não lê o consumo do modelo.

## Onde olhar

- `agentes/CLAUDE.md`: o motor, os limites e o que o back-end faz.
- `agentes/agente_geral/README.md`: o agente geral.
- `seguranca/CLAUDE.md`: quem pode o quê em cada agente.
- `ferramentas/CLAUDE.md`: o catálogo e as regras por cargo.
- `docs/decisoes.md`: H3 (agente geral na Sprint 2) e as perguntas abertas.
