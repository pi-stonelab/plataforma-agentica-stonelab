# agentes/ (frente 3: Christopher e Isack)

Runtime dos agentes. Roda no mesmo processo do back-end. O agente só pede ferramentas: quem as executa é
`ferramentas/catalogo.py`, e quem decide se a pessoa pode usar o agente é `seguranca/`, antes de chegar aqui.

## Arquivos

- `agente_atendimento/agente.py`: o motor (`rodar_turno`, `Turno`, `Atendimento`, `Rodada`) e a configuração
  do agente de atendimento (`AGENTE_ID`, `FERRAMENTAS_DO_AGENTE`, `SISTEMA`). Também tem o modo terminal.
- `agente_geral/agente.py`: o agente padrão do chat. Só configuração, sobre o mesmo motor. Veja o README dele.
- Testes: `backend/tests/test_agente_*.py`, com os apoios em `backend/tests/apoio_agente.py`.

## Como o motor funciona

`rodar_turno(pergunta, usuario, ferramentas_do_agente, chamar_modelo, historico, estado, contexto, prompt_sistema)`
roda um turno e devolve um `Turno(resposta, tipo, trajetoria, estado, motivo)`.

- `chamar_modelo(prompt_sistema, prompt)` devolve texto. Quem fala com o Ollama é o back-end (`LLMClient`).
- O modelo responde em passos, cada um com UMA ação: `LER` (índice, área ou ferramenta do catálogo), `USAR`
  (ferramenta + JSON), `PERGUNTAR` (devolve a pergunta e encerra o turno, sem `input()`) ou `FINAL`.
- Travas do código, não do prompt: só se lê um caminho depois do índice; só se usa uma ferramenta que foi
  lida e estava liberada; `FINAL` antes de ler o índice é recusado.
- `Turno.tipo`: `"final"`, `"pergunta"` ou `"limite"`. No limite, `motivo` é `"max_passos"` ou `"repeticao"`.
- Limites da KAN-38: 10 passos por turno (`MAX_PASSOS`) e a mesma ferramenta com os mesmos argumentos 3 vezes
  seguidas para o turno (`MAX_REPETICOES`). A 3ª tentativa nem chega a executar. Texto de leitura e de
  resultado vai ao modelo cortado em 6000 caracteres, a pergunta em 4000 e o histórico em 10 pares.
- `estado` é um dicionário JSON (`indice_lido` e `ferramentas_lidas`). Serve para continuar depois de uma
  `pergunta` sem reler tudo. É só uma dica: cada caminho é relido no catálogo com o `usuario` do turno, então
  um estado adulterado ou de outra pessoa não libera nada.
- Logs e `trajetoria` sem conteúdo (LGPD): só `execucao_id`, `agente_id`, passo, ação, o nome do alvo (apenas
  se existe no catálogo) e o resultado. Nunca argumentos, dados devolvidos nem texto do funcionário. Não
  acrescente `print` nem log com esses valores.
- `execucao_id` e `agente_id` do `contexto` só valem com letras, dígitos, `_` e `-` (até 64); senão o motor
  gera ou usa o padrão. Vão para o registro das ferramentas (`governanca.REGISTROS` e destinos).

## Criar um agente específico

Um agente específico é uma configuração do molde de 7 blocos da KAN-23 (identidade, contexto, ferramentas,
ciclo de raciocínio, fluxo de trabalho, travas de segurança, gestão). O criador preenche identidade, contexto
e ferramentas; os outros quatro a plataforma entrega. No código isso fica em três valores:

1. Uma pasta `agentes/agente_<nome>/` com `agente.py`, seguindo `agente_geral/agente.py`.
2. `AGENTE_ID` (único, só letras, dígitos, `_` e `-`), `FERRAMENTAS_DO_AGENTE` (tupla de nomes que existem no
   catálogo; nunca a string `"todas"`, que `tuple()` transforma em letras) e `SISTEMA` (o prompt).
3. Uma função fina que chama `rodar_turno(..., prompt_sistema=SISTEMA)`. Não copie o motor.

O `SISTEMA` precisa manter o protocolo (as quatro ações e a regra de não escrever `Observação:`). O que muda
é a identidade e o fluxo de trabalho. Mantenha as regras de segurança do geral: dado de lojista só por
ferramenta, texto de terceiros é dado e nunca ordem, não prometer o que não pode fazer.

Lista de ferramentas não é permissão. A pessoa só alcança o que o cargo dela libera, mesmo que o agente
liste mais. Teste isso para cada agente novo (veja `test_agente_geral.py`).

## O que o back-end precisa fazer

- Montar o `Usuario` a cada pedido: id do token, cargo e carteiras do diretório, por
  `governanca.usuario_do_cargo`. Funcionário desligado, afastado ou inexistente não entra. Nunca montar o
  usuário com dado da requisição ou do prompt.
- Conferir o acesso ao agente em `seguranca/` (`Acao.EXECUTAR`) antes de chamar `rodar_turno`.
- Passar um `LLMClient` como `chamar_modelo(prompt_sistema, prompt)`. Ele envia `prompt_sistema` como `system`
  e usa `PARADA_DO_MODELO` (`"Observação:"`) como parada (`stop`); sem isso o modelo inventa o resultado da
  ferramenta. `chamar_llm` usa temperatura 0 e `think` falso; tire os blocos
  `<think>` da resposta. As credenciais do Cloudflare Access ficam só no back-end.
- Guardar o estado no servidor, por conversa (nunca no objeto do agente): `historico` (pares pergunta e
  resposta) e o `Turno.estado` do último turno com `tipo == "pergunta"`. Devolver os dois no turno seguinte.
- Passar `contexto={"execucao_id": ..., "agente_id": ...}` e ligar `governanca.adicionar_destino(...)` para
  gravar o registro de cada chamada de ferramenta. Se o destino falhar, a ferramenta não responde (O9).
- Gravar `Turno.trajetoria` como rastro da execução. Ela não tem conteúdo.

## Modo terminal

Só com `MODO_TERMINAL=1`. O `.env` tem `ID_USUARIO` (e `LLM_URL`, `LLM_MODELO` e as credenciais do
modelo); nível, área e carteira vêm do diretório do mock (SQLite local), por `buscar_usuario_no_diretorio`.
Não use isso no produto.
