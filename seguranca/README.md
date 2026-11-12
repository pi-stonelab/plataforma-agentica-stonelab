# seguranca

Perfis de acesso e checagem de permissão. Responsável: Brenno (alterações da integração feitas com a liberação dele).

## Arquivos

- `permissoes.py`: perfis (AdminGlobal, Supervisor, Colaborador, Auditor, GestorDeAcessos), Agente, Visibilidade, Acao, Area e Plataforma com auditoria.
- `envelope.py`: decorator `exige_permissao` e a instância `PLATAFORMA`, que serve só para a demo e testes simples.

## Regras de acesso ao agente

Cada perfil é uma subclasse de `Usuario` e decide em `pode(acao, agente)`. O dono escolhe a visibilidade do agente:
`PRIVADO` (padrão), `CONVIDADOS` ou `PUBLICO`. Publicar não exige aprovação.

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

Agente INATIVO (`ativo=False`):

- Ninguém executa, nem o dono. Vale em `pode` e de novo em `Plataforma.autorizar`.
- Quem só usa (convidado, outro Colaborador, Supervisor fora da área) também deixa de ver.
- Quem gerencia continua vendo e gerenciando, menos executar: o dono, o Supervisor da área (não privado) e o Admin (ver não privado e deprecar).

Outras regras:

- AdminGlobal opera sem ver conteúdo: pode deprecar (pausar/desativar) qualquer agente, ver só os não privados, e nunca executa (não vê dado de lojista), edita nem convida. Não cria agentes. Não lê auditoria. Área é opcional.
- Auditor só tem `pode_ler_auditoria = True` (D9): lê a auditoria por `Plataforma.ler_auditoria(usuario)`. Não cria, não vê e não executa agente. Área é opcional.
- GestorDeAcessos atribui e remove perfis, nunca sobre si mesmo. Não vê nem cria agentes.
- Quem foi rebaixado ou removido perde o acesso no mesmo instante: a `Plataforma` usa o perfil do cadastro (`_atual`), nunca o objeto que a pessoa guardou.
- `Usuario.usa_ferramentas` é `False` por padrão (perfil novo nasce sem ferramentas). Só Colaborador e Supervisor têm `True`. `cria_agentes` segue a mesma ideia.
- Pessoas são guardadas por id: `Agente.dono_id` e `Agente.convidados_ids`. `Evento` guarda `id_usuario`, nunca o objeto. Mensagens de `AcessoNegado` levam ação e id, nunca nome (o `repr` do usuário também não mostra nome).
- `Area.slug` (`atendimento`, `financeiro`) liga a área ao texto usado no banco e nas ferramentas; `area_do_slug` converte de volta e recusa slug desconhecido.
- Falha fechada na auditoria (O9): `Plataforma(ao_registrar=gancho)` chama o gancho a cada evento. Se o gancho levantar erro, a ação é negada (`AcessoNegado`) e o evento fica registrado em memória como não permitido. As mudanças (criar agente, mudar ou remover perfil) só acontecem depois que o evento foi gravado.

### Decisões a confirmar com o grupo

1. Níveis separados. A decisão registrada diz "agente privado: só o criador, os convidados..." num texto e "privado / convidados" como níveis diferentes em outro. Implementamos três níveis: privado = só o dono (convidar um privado é permitido, mas só passa a valer se virar `CONVIDADOS`), convidados = dono e convidados, público = todos os Colaboradores e Supervisores das duas áreas.
2. Agente inativo some para quem só usa (ver acima). O texto original só diz "ninguém executa; o dono ainda vê".
3. Supervisor executa e gerencia qualquer agente não privado das suas áreas, mesmo sem convite (era o que o código original fazia). Se o grupo quiser que ele só gerencie, é mudar `_gerencia` para não incluir EXECUTAR no caso dele.
4. Admin e Auditor não criam agentes. O Admin não é dono de nada nem pode ser convidado para usar.
5. REPLICAR ainda não existe como ação (fica para a Sprint 3).

## Como usar nos agentes e ferramentas

Coloque o decorator em toda função que age sobre um agente. Ela precisa ter parâmetros chamados `usuario` e `agente`.

```python
from seguranca.envelope import exige_permissao
from seguranca.permissoes import Acao

@exige_permissao(Acao.EXECUTAR)
def rodar_agente(usuario, agente, pergunta):
    ...
```

No back-end, use uma Plataforma por pedido. Se a função declara o parâmetro `plataforma`, o decorator usa a que chegou na chamada e nega se não for uma `Plataforma`:

```python
@exige_permissao(Acao.EXECUTAR)
def executar_agente(plataforma, usuario, agente, pergunta):
    ...

plataforma = Plataforma(ao_registrar=gravar_evento_no_banco)  # nova a cada pedido
plataforma.cadastrar(usuario_lido_do_banco)
executar_agente(plataforma, usuario_lido_do_banco, agente_lido_do_banco, "...")
```

Sem o parâmetro `plataforma`, vale a fixada em `exige_permissao(acao, plataforma=...)` e, por último, a global `PLATAFORMA`.

Qual ação usar:

| Ação | Quando |
| --- | --- |
| `Acao.VER` | mostrar ou listar o agente |
| `Acao.EXECUTAR` | rodar o agente ou chamar uma ferramenta dentro dele |
| `Acao.EDITAR` | mudar configuração, prompt ou ferramentas do agente |
| `Acao.CONVIDAR` | convidar outra pessoa para o agente |
| `Acao.DEPRECAR` | pausar ou desativar o agente |

O que acontece:

- Permitido: a função roda e a tentativa vai para a auditoria.
- Negado: levanta `AcessoNegado`, a função não roda e a tentativa vai para a auditoria.
- Erro inesperado na checagem: também vira `AcessoNegado` (falha fechada).
- A função decorada ganha `acao_exigida`, para os testes conferirem a ação.

Trate o `AcessoNegado` onde fizer sentido (por exemplo, responder "você não tem acesso a esse agente"). Não engula o erro para seguir em frente.

## Limites atuais

- Cadastro e auditoria ficam em memória: somem quando o programa fecha. O cadastro em memória e a global `PLATAFORMA` são só para a demo (`python seguranca/permissoes.py`).
- No back-end o perfil de cada pessoa vem do banco a cada pedido: monte a Plataforma, cadastre a pessoa com o perfil atual e descarte. Nunca monte o usuário a partir do que vem na requisição ou no prompt, e não reaproveite uma Plataforma entre pedidos.
- Este decorator confere o acesso ao agente. A checagem por ferramenta (nível e área de cada ferramenta) continua em `ferramentas/governanca.py`.
- Nenhum método muda `Agente.ativo` ou `visibilidade`: quem decide e grava é o back-end, depois de `autorizar(..., Acao.DEPRECAR/EDITAR, agente)`.
