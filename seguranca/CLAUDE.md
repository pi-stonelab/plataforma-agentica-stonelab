# seguranca/ (frente 6: Brenno)

Quem pode fazer o quê com um agente. Perfis, visibilidade, decorator de permissão e auditoria de acesso.
O Brenno liberou a alteração desta pasta para a integração. As regras de acesso estão no `README.md` desta pasta e
este arquivo não as muda. Aqui está a explicação de como o código funciona, o que o back-end chama a cada pedido e
o que ainda não existe.

Fontes: `KAN-xx`, `Dx`/`Ox` (decisões, em `docs/decisoes.md`) e o `README.md` desta pasta. Sem fonte, o texto
diz "SEM FONTE".

## As quatro portas

Todo pedido de uma pessoa passa por quatro perguntas, uma depois da outra. Cada pasta responde a sua.

1. Quem é você? Login, token e perfil lidos do banco. É do back-end (`backend/app/auth.py`, ainda não existe).
2. Você pode usar este agente? É esta pasta: `Plataforma.autorizar` e o decorator `exige_permissao`.
3. Você pode usar esta ferramenta? É de `ferramentas/` (`catalogo.executar`, por cargo, área e categoria de dado).
4. Este lojista é seu? Também de `ferramentas/` (`lojista.exigir_acesso`, carteira e janela de dias).

`seguranca/` não importa `ferramentas/`, `agentes/`, `mock/` nem `backend/`. Quem liga as pastas é o back-end
(`backend/app/permissoes.py`, que ainda não existe). Decisão O3.

## Perfis

Cada perfil é uma subclasse de `Usuario` e decide em `pode(acao, agente)`. Os cinco estão em `ROLES`.

- `Colaborador`: usa e gerencia o que é seu, usa o que foi aberto para ele. Exige área. Usa ferramentas e cria
  agentes.
- `Supervisor`: o mesmo, mais os agentes não privados das suas áreas (`area` e `areas_extras`). Exige área.
- `AdminGlobal`: opera a plataforma sem ver conteúdo. Pausa qualquer agente, vê só os não privados, nunca executa,
  edita ou convida. Não cria agentes. Não lê auditoria. Área opcional.
- `Auditor`: só lê a auditoria (D9). Não cria, não vê e não executa agente. Área opcional.
- `GestorDeAcessos`: atribui e remove perfis, nunca o próprio. Não vê nem cria agentes.

Três atributos de classe, todos falsos por padrão, para um perfil novo nascer sem poder: `usa_ferramentas`,
`cria_agentes` e `pode_ler_auditoria`. Só `Colaborador` e `Supervisor` têm `usa_ferramentas` e `cria_agentes`.
Só `Auditor` tem `pode_ler_auditoria`.

O atributo `nivel` (inteiro, 1 é `AdminGlobal`) nada lê hoje. Ele tem ordem invertida em relação ao `nivel` N1/N2
de `ferramentas/governanca.py` (onde N2 é o maior). Não compare os dois. O nível de ferramenta vem do cargo
(`mock/regras.py`), não do perfil (O1, D8).

Ligação com os cargos do mock: cada cargo tem um `perfil_padrao` em `mock/regras.py` (`Colaborador`, `Supervisor`,
`AdminGlobal` ou `Auditor`). Um teste confere que esses nomes existem em `ROLES`. A conversão do texto do banco para a
classe é do back-end: `{classe.__name__: classe for classe in ROLES}`. Perfil desconhecido é pessoa sem acesso.

## Visibilidade

O dono escolhe, e publicar não exige aprovação (D3):

- `PRIVADO` (padrão): só o dono.
- `CONVIDADOS`: o dono e quem ele convidou.
- `PUBLICO`: todos os Colaboradores e Supervisores das duas áreas.

No banco, a visibilidade é o texto (`privado`, `convidados`, `publico`). `Agente(...)` aceita esse texto e recusa
qualquer outro valor.

## Regras (as do README)

Tabela para agente ATIVO. "tudo" = ver, executar, editar, convidar e deprecar. "usar" = ver e executar.

| Quem é a pessoa | PRIVADO | CONVIDADOS | PUBLICO |
| --- | --- | --- | --- |
| Dono (Colaborador ou Supervisor) | tudo | tudo | tudo |
| Colaborador convidado pelo dono | nada | usar | usar |
| Colaborador que não é dono nem convidado | nada | nada | usar |
| Supervisor, agente de uma das suas áreas (não é dono) | nada | tudo | tudo |
| Supervisor, agente de outra área, convidado | nada | usar | usar |
| Supervisor, agente de outra área, não convidado | nada | nada | usar |
| AdminGlobal | só deprecar | ver e deprecar | ver e deprecar |
| Auditor | nada | nada | nada |
| GestorDeAcessos | nada | nada | nada |

Como ler a tabela com o código (`_gerencia`, `_usa` e `pode` de cada perfil):

- "tudo" tem uma exceção: convidar só vale quando o agente está em `CONVIDADOS`. Em `PRIVADO` e `PUBLICO` o
  convite é negado para todos. Para convidar alguém, o dono primeiro muda o agente para `CONVIDADOS`.
- Agente inativo (`ativo=False`): ninguém executa, nem o dono. Quem só usa deixa de ver. Quem gerencia continua
  vendo e gerenciando.
- O Supervisor não vê agente privado de outra pessoa. Nos abertos da sua área ele gerencia e executa sem precisar de
  convite. Se o grupo quiser que ele só gerencie, a mudança é em `_gerencia` (README, decisão 3 a confirmar).
- O `AdminGlobal` pode deprecar até um agente privado, mas precisa do id: ele não aparece em `agentes_visiveis`.
- `Plataforma.autorizar` ainda nega `EXECUTAR` quando o agente está inativo, mesmo que um perfil novo esqueça disso.

## Plataforma: cadastro e auditoria de um pedido

`Plataforma` guarda em memória os usuários cadastrados, os agentes carregados e a lista de eventos. No back-end, ela
vale para UM pedido (ver abaixo).

- `cadastrar(usuario)`, `usuario(id)`: cadastro de pessoas.
- `registrar(agente, criador)`: cria um agente NOVO. Só em nome de quem tem perfil que cria, na área dele (o
  Supervisor também nas extras), com id ainda não usado. Grava o evento `CRIAR`.
- `carregar_agente(agente)`: põe um agente que já existe no banco, sem evento `CRIAR` e sem criador. Só o back-end
  usa, com o que leu do banco. Id repetido com outro agente é erro. Serve também para o agente geral.
- `autorizar(usuario, acao, agente, execucao_id=None)`: decide e grava UM evento. Decide sempre sobre o agente
  REGISTRADO. Agente não registrado, ou igual no id mas diferente no dono ou na visibilidade, é negado. O objeto
  que você passa só serve de chave.
- `alterar_visibilidade(quem, agente, nova)`: exige `EDITAR`. `desativar(quem, agente)`: exige `DEPRECAR`.
  `convidar(quem, convidado, agente)`: exige `CONVIDAR` e que o convidado esteja cadastrado. Em todos, o evento é
  gravado antes da mudança.
- `agentes_visiveis(usuario)`: só dos agentes carregados.
- `atribuir_role` e `remover_role` (pelo `GestorDeAcessos`): o gestor não mexe no próprio perfil, e a pessoa
  continua com o mesmo id.
- `autorizar_leitura_auditoria(usuario)`: só o Auditor passa. Registra a tentativa e não devolve eventos.

O perfil vigente vem sempre do cadastro (`_atual`), nunca do objeto que a pessoa guardou. Quem foi rebaixado ou
removido perde o acesso na hora.

## Eventos de auditoria

`Evento` é imutável (`dataclass(frozen=True)`) e tem seis campos: `quando`, `id_usuario`, `acao`, `alvo`,
`permitido` e `execucao_id` (opcional).

- Só o id da pessoa. Nunca o objeto, nunca o nome. O `repr` de `Usuario` e as mensagens de `AcessoNegado` também
  não levam nome. A mensagem leva a ação e o id do agente.
- `acao` é `VER`, `EXECUTAR`, `EDITAR`, `CONVIDAR`, `DEPRECAR`, e também `CRIAR`, `ALTERAR_VISIBILIDADE:<valor>`,
  `DESATIVAR`, `CONVIDAR_PESSOA_DESCONHECIDA`, `ATRIBUIR_ROLE:<perfil>`, `REMOVER_ROLE` e `LER_AUDITORIA`.
- `execucao_id` só aceita letras, números, `_` e `-`, até 64 caracteres. Valor fora disso nega a ação e o evento sai
  sem ele. É o fio que liga o evento ao registro de chamadas de ferramenta (`governanca.CAMPOS_REGISTRO` tem o mesmo
  campo). O orquestrador precisa passar o MESMO valor nos dois lugares (`pesquisa/critica_B.md`, §6).
- Gancho (O9): `Plataforma(ao_registrar=funcao)` chama a função a cada evento. Se ela levantar erro, a ação é
  negada com `AcessoNegado` e o evento fica na lista em memória como não permitido. Sem rastro, sem ação. Criar
  agente, mudar visibilidade, desativar e mudar perfil só acontecem depois que o evento foi gravado.
- A lista `plataforma.auditoria` vale só para um pedido. A auditoria da empresa é a tabela do back-end.

## Decorator `exige_permissao`

    from seguranca.envelope import exige_permissao
    from seguranca.permissoes import Acao

    @exige_permissao(Acao.EXECUTAR)
    def executar_agente(plataforma, usuario, agente, execucao_id, pergunta):
        ...

- A função decorada precisa ter os parâmetros `usuario` e `agente`. Sem eles, o erro aparece ao importar.
- Se declarar `plataforma`, vale a que chegou na chamada; se o valor não for uma `Plataforma`, nega. Sem esse
  parâmetro, vale a fixada em `exige_permissao(acao, plataforma=...)` e, por último, a global `PLATAFORMA`, que só
  serve para a demo e testes simples.
- Se declarar `execucao_id`, ele vai para o evento.
- Negado ou erro inesperado na checagem: `AcessoNegado`, e a função nem começa (falha fechada).
- A função decorada ganha `acao_exigida`, para os testes conferirem.
- Não ponha o decorator em rota do FastAPI (os parâmetros viram query e dá 422). A rota chama uma função de serviço
  decorada. Também não vai em `ferramentas/`: a ferramenta não recebe `agente`.

## Agente geral (da plataforma)

`Agente.da_plataforma(nome, id=None)`: `area=None`, `dono_id=DONO_PLATAFORMA` (`"plataforma"`), `PUBLICO`.
Nenhuma pessoa pode ter o id `plataforma`, então ninguém é dono. O construtor só aceita agente sem área quando o
dono é a plataforma.

- Colaborador e Supervisor das duas áreas veem e executam, enquanto ele está ativo.
- Ninguém edita nem convida, nem o Supervisor da área (por isso a área é `None`: com área, o Supervisor passaria a
  gerenciar).
- O Admin o pausa por `desativar` (DEPRECAR). Inativo, ninguém executa.
- Auditor, Gestor e Admin não executam.
- Entra na Plataforma só por `carregar_agente`. `registrar` por pessoa é negado.
- O lado dos dados está em `agentes/agente_geral/` e `docs/agente-geral-e-especificos.md`.

## O que o back-end precisa chamar a cada pedido

Nada aqui existe ainda em `backend/`. É o contrato que a etapa do back-end cumpre.

1. Ler o token (só `sub` e validade) e buscar a pessoa no banco em TODO pedido. Perfil, área e carteiras nunca
   vêm do token, do corpo da requisição nem do prompt. Pessoa ausente, inativa ou com perfil fora de `ROLES`: 401
   sem detalhe.
2. Conferir no diretório do mock se o funcionário está `ativo` (desligado e afastado não entram, mesmo com token
   válido).
3. Criar uma `Plataforma(ao_registrar=gravar_evento)` NOVA e `cadastrar` a pessoa com o perfil lido agora. Nunca
   reaproveitar a `Plataforma` entre pedidos nem usar a global `PLATAFORMA` em pedido real.
4. Montar o `Agente` com o que veio do banco (`dono_id`, `convidados_ids`, `visibilidade`, `ativo`, `area_do_slug`) e
   chamar `carregar_agente`. Para listar agentes (`agentes_visiveis`), carregue os candidatos antes.
5. Chamar uma função de serviço decorada com `@exige_permissao(Acao.EXECUTAR)` que recebe `plataforma`, `usuario`,
   `agente` e `execucao_id`. O mesmo `execucao_id` vai para `contexto` das ferramentas.
6. Tratar `AcessoNegado` num `exception_handler` e responder genérico ("Acesso negado."), sem nome de agente nem de
   pessoa. SEM FONTE no código para 404 em vez de 403 quando a pessoa nem pode ver o agente; é proposta de
   `pesquisa/arquitetura.md` §5.5.
7. Para mudar estado, chamar os métodos que autorizam (`alterar_visibilidade`, `desativar`, `convidar`) e só então
   gravar o novo valor no banco.
8. Para ler a auditoria, chamar `autorizar_leitura_auditoria` e só depois consultar a tabela.
9. Ligar `ao_registrar` a uma função que grava na tabela `auditoria` com sessão própria. Se a gravação falhar, levante
   erro: a ação será negada.

Para montar o `governanca.Usuario` (o das ferramentas) da mesma pessoa, use `governanca.usuario_do_cargo` com o
cargo e as carteiras do diretório. Perfil sem `usa_ferramentas` (Admin, Auditor, Gestor) não recebe `governanca.Usuario`.

## Como acrescentar

- Perfil novo: uma subclasse de `Usuario` com `pode`, a entrada em `ROLES` e a linha na matriz de
  `backend/tests/test_seguranca_permissoes.py` (`ESPERADO_ATIVO`, `ESPERADO_INATIVO` e a `fabrica`).
  `test_perfil_novo_nasce_sem_poder` cobre o padrão fechado.
- Área nova: uma subclasse de `Area` com `nome` e `slug`, e a entrada em `AREAS`. Também mexe em `mock/regras.py`
  (veja `mock/CLAUDE.md`). `test_areas_batem_entre_mock_governanca_e_seguranca` pega listas que divergem.

## Limites conhecidos

- Cadastro e auditoria ficam em memória e somem quando o programa fecha. A demo é `python seguranca/permissoes.py`.
- REPLICAR ainda não existe como ação (Sprint 3). A cópia revalidaria cada ferramenta contra o cargo e a área de
  quem copiou (`governanca.motivo_bloqueio`), sem código novo de segurança. Fonte: KAN-28, KAN-69 E26.
- Reativar um agente pausado hoje só pelo banco.
- Não existe listagem de metadados (id, área, dono) para o Admin achar um agente privado. Fica para a Sprint 3.
- Convites antigos voltam: mudar `CONVIDADOS` para `PRIVADO` e de volta mantém `convidados_ids` (BAIXO-6 da
  auditoria B). Limpar a lista ao sair de `CONVIDADOS` é decisão aberta.
- `alterar_visibilidade` valida o valor antes de checar a permissão: quem não pode editar e manda valor inválido
  recebe `ValueError`, não `AcessoNegado` (BAIXO-7). Sem vazamento.
- Não existe rota para o Auditor ler a auditoria (a lista de rotas da KAN-60 não tem). A regra de perfil existe;
  a leitura em si, não (V9 da KAN-69).
- Alerta de acesso indevido ao Monitoramento (KAN-69 E3) é Sprint 3: hoje só há o evento de auditoria (V6).
- Admin e Auditor sem área: o `Usuario` aceita (área opcional), mas qualquer ferramenta de dado os trata como
  usuário inválido.
- A mensagem de `AcessoNegado` leva o id do agente. Para o cliente HTTP, responda uma mensagem fixa.
- Decisões ainda abertas com o Brenno e o grupo estão em "Decisões a confirmar com o grupo" do `README.md`.
