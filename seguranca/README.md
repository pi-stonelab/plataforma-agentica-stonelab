# seguranca

Perfis de acesso e checagem de permissão. Responsável: Brenno.

## Arquivos

- `permissoes.py`: perfis (AdminGlobal, Supervisor, Colaborador, GestorDeAcessos), Agente, Acao e Plataforma com auditoria.
- `envelope.py`: decorator `exige_permissao` e a instância compartilhada `PLATAFORMA`.

## Como usar nos agentes e ferramentas

Coloque o decorator em toda função que age sobre um agente. Ela precisa ter parâmetros chamados `usuario` e `agente`.

```python
from seguranca.envelope import exige_permissao
from seguranca.permissoes import Acao

@exige_permissao(Acao.EXECUTAR)
def rodar_agente(usuario, agente, pergunta):
    ...

@exige_permissao(Acao.EXECUTAR)
def chamar_ferramenta(usuario, agente, nome_ferramenta, argumentos):
    ...

@exige_permissao(Acao.EDITAR)
def editar_agente(usuario, agente, novas_configuracoes):
    ...
```

Qual ação usar:

| Ação | Quando |
| --- | --- |
| `Acao.VER` | mostrar ou listar o agente |
| `Acao.EXECUTAR` | rodar o agente ou chamar uma ferramenta dentro dele |
| `Acao.EDITAR` | mudar configuração, prompt ou ferramentas do agente |
| `Acao.CONVIDAR` | convidar outra pessoa para o agente |
| `Acao.DEPRECAR` | desativar o agente |

O que acontece:

- Permitido: a função roda e a tentativa vai para a auditoria.
- Negado: levanta `AcessoNegado`, a função não roda e a tentativa vai para a auditoria.
- Erro inesperado na checagem: também vira `AcessoNegado` (falha fechado).

Trate o `AcessoNegado` onde fizer sentido (por exemplo, responder "você não tem acesso a esse agente"). Não engula o erro para seguir em frente.

## Usuários e agentes

Use sempre a `PLATAFORMA` de `seguranca.envelope`, para que todos enxerguem o mesmo cadastro:

```python
from seguranca.envelope import PLATAFORMA
from seguranca.permissoes import Colaborador, Financeiro

joao = PLATAFORMA.cadastrar(Colaborador("João", Financeiro()))
agente = joao.criar_agente("Relatório de carteira", PLATAFORMA)
```

Nunca monte o usuário a partir do que vem na requisição ou no prompt. O perfil vem do login (back-end).

## Limites atuais

- Cadastro e auditoria ficam em memória: somem quando o programa fecha. No produto, vão para o banco.
- Este decorator confere o acesso ao agente. A checagem por ferramenta (nível e área de cada ferramenta) continua em `ferramentas/governanca.py`.
