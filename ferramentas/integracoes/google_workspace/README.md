# Google Workspace

A conta Google de cada funcionário: agenda (Calendar), planilhas (Sheets), documentos (Docs) e arquivos (Drive). A
plataforma usa para o agente listar e criar eventos, buscar arquivos pelo nome, ler planilha e documento, adicionar uma
linha e criar uma planilha. Tudo roda com a conta e as permissões de quem pede: o app nunca vê o que a pessoa não vê.

## Ferramentas que usam

- `documentos_e_agenda/listar_eventos_agenda` (leitura)
- `documentos_e_agenda/criar_evento_agenda` (escrita, com confirmação)
- `documentos_e_agenda/ler_planilha` (leitura)
- `documentos_e_agenda/adicionar_linha_planilha` (escrita, com confirmação)
- `documentos_e_agenda/criar_planilha` (escrita, com confirmação)
- `documentos_e_agenda/ler_documento` (leitura)
- `documentos_e_agenda/buscar_arquivos` (leitura)

O Google e o Microsoft 365 são alternativas: a ferramenta fica visível se qualquer um dos dois estiver ligado, e a
pessoa usa a conta que ligou (decisão G2).

## Conector

`google_workspace/conector.py` (`ConectorGoogleWorkspace`), sobre a base `Conector`: modos `real`, `simulado` e
`desligado` (`GOOGLE_MODO`), disjuntor (3 falhas de rede seguidas pausam 60 s), `testar`, saúde por serviço
(`autorizacao`, `agenda`, `planilhas`, `documentos`, `arquivos`) e `credencial="pessoa"`.

- Chamadas reais à Calendar v3, Sheets v4, Docs v1 e Drive v3, com o token da pessoa, por `cliente_http`.
- Escopos mínimos: leitura (`calendar.events.readonly`, `spreadsheets.readonly`, `documents.readonly`,
  `drive.metadata.readonly`); escrita (`calendar.events`, `spreadsheets`) só é pedida quando a pessoa usa uma
  ferramenta de escrita. A busca é pelo nome do arquivo, nunca pelo conteúdo.
- Linha nova entra como `RAW` (texto nunca vira fórmula). O evento tem `id` nosso: repetir o pedido não duplica.
- Convidado de evento só de domínio listado em `ESCRITORIO_DOMINIOS` (o `exigir_destino` da base); vazio, ninguém.
- 403 do Google é separado em limite de pedidos, falta de permissão e item sem acesso.
- O conteúdo que volta (título de evento, planilha, documento) é de terceiros: vai em `conteudo_de_terceiros`, é
  mascarado antes do modelo e é tratado como dado, nunca como instrução.
- Erro e log levam só a etapa e o tipo da falha: nunca token, endereço, id de arquivo ou texto.

## Ligação

OAuth2 com código de autorização e PKCE (S256), um token por pessoa, em `ferramentas/integracoes/oauth.py`
(`FluxoOAuth`: `iniciar`, `concluir`, `renovar`, `desligar`). O `state` vale uma vez, só para a pessoa que o pediu, por
10 minutos. A renovação é uma só por conta, mesmo com pedidos simultâneos. O consentimento é granular: pedir escrita
não exige reconceder a leitura. Sem conta ligada, a ferramenta responde `integracao_indisponivel` ("conta não ligada").

1. No Console do Google Cloud do domínio: crie o app OAuth do tipo "aplicativo da Web", ligue as APIs Calendar, Sheets,
   Docs e Drive e cadastre o `GOOGLE_REDIRECT_URI`.
2. No `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` e `ESCRITORIO_DOMINIOS`
   (`.env.example` mostra os nomes, sem valores). Preencher o `GOOGLE_CLIENT_ID` liga a integração.
3. Cada pessoa liga a própria conta pela interface (abaixo).

[A FAZER (Marcelo e Isabel, back-end, Sprint 3): rotas `GET /integracoes/google_workspace/autorizar` (chama
`iniciar` com o `id_usuario` do token e responde o endereço de consentimento) e `GET .../callback` (recebe `state` e
`code`, chama `concluir` com o `id_usuario` do token), e um `ProvedorNoBanco` com os tokens cifrados
(`credenciais.usar(provedor)` no `lifespan`). Hoje o provedor é `ProvedorEmMemoria`.]
[A FAZER (Larissa, interface): botão "Conectar conta" e "Desconectar" na tela de conectores.]

## Hoje

Conector real escrito e testado contra um servidor local falso que imita Calendar, Sheets, Docs, Drive e o login do
Google (`backend/tests/apoio_escritorio.py`, em loopback). **Não foi possível testar contra o Google de verdade**: não
há conta nem app registrado, e o projeto só usa dado sintético. Quem tiver o app roda, com `MODO_TERMINAL=1`:

`python -m ferramentas.integracoes testar google_workspace`

O comando manda um código inventado ao endereço de token: `invalid_grant` quer dizer que o `client_id` e o segredo
foram aceitos; `invalid_client` quer dizer que o app está errado. Depois, com uma conta de teste ligada pela interface,
conferir a mão: listar eventos de hoje, ler uma planilha, adicionar linha e criar planilha (e apagar o que sobrar).

Com `GOOGLE_MODO=simulado` (ou sem credencial na demo), `escritorio_simulado.py` devolve, no mesmo formato do real, a
agenda e as planilhas inventadas do mundo do `mock/` (hoje fixo em 15/10/2026, documentos da base de conhecimento
pública, planilhas só com indicadores agregados) e diz `fonte` simulada. O que a pessoa cria fica na memória, só para ela.
