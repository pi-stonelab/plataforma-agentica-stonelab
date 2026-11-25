# Microsoft 365

A conta Microsoft de cada funcionário: agenda (Outlook), arquivos e planilhas (OneDrive e Excel) e documentos (Word),
pelo Microsoft Graph. A plataforma usa para o agente listar e criar eventos, buscar arquivos, ler planilha e documento,
adicionar uma linha e criar uma planilha, sempre com a conta e as permissões de quem pede.

## Ferramentas que usam

- `documentos_e_agenda/listar_eventos_agenda` (leitura)
- `documentos_e_agenda/criar_evento_agenda` (escrita, com confirmação)
- `documentos_e_agenda/ler_planilha` (leitura)
- `documentos_e_agenda/adicionar_linha_planilha` (escrita, com confirmação)
- `documentos_e_agenda/criar_planilha` (escrita, com confirmação)
- `documentos_e_agenda/ler_documento` (leitura)
- `documentos_e_agenda/buscar_arquivos` (leitura)

Alternativa ao Google Workspace: as ferramentas ficam visíveis se qualquer um dos dois estiver ligado (decisão G2).

## Conector

`microsoft_365/conector.py` (`ConectorMicrosoft365`), sobre a base `Conector`: modos `real`, `simulado` e `desligado`
(`MICROSOFT_MODO`), disjuntor, `testar`, saúde por serviço e `credencial="pessoa"`.

- Permissões delegadas mínimas: leitura (`Calendars.Read`, `Files.Read`); escrita (`Calendars.ReadWrite`,
  `Files.ReadWrite`) só quando a pessoa usa uma ferramenta de escrita; `offline_access` sempre (sem ele não há token
  de renovação). Nenhuma permissão `.All`.
- Evento com `transactionId` nosso: repetir o pedido não duplica. Convidado só de domínio em `ESCRITORIO_DOMINIOS`.
- Linha nova no Excel: primeiro o formato da célula (`@` para texto), depois os valores; texto que parece fórmula ou
  data não vira fórmula nem data. Planilha nova é um `.xlsx` enviado sem sobrescrever outro de mesmo nome.
- O `.docx` é baixado por redirecionamento para `sharepoint.com`, `1drv.com` ou `onedrive.live.com`, sem o token, e
  lido por `formatos.ler_docx` (sem macro, sem entidade externa, com teto de tamanho).
- A busca do Graph também encontra pelo conteúdo do arquivo; o que volta é só nome, tipo e data (decisão G7).
- Conteúdo de terceiros, máscara e erros como no Google Workspace: tudo vai em `conteudo_de_terceiros`, é dado.

## Ligação

OAuth2 com código de autorização e PKCE (S256), um token por pessoa (`FluxoOAuth`, `ferramentas/integracoes/oauth.py`).
O token de renovação da Microsoft muda a cada uso; a renovação é única por conta, e o novo par é guardado. A Microsoft
não tem endereço para revogar o token: "desligar" só apaga a conta daqui, e a pessoa tira o consentimento em
myaccount.microsoft.com.

1. No Microsoft Entra ID do diretório da Stone: registre um app do tipo "Web", cadastre o `MICROSOFT_REDIRECT_URI`,
   as permissões delegadas acima e crie um segredo.
2. No `.env`: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` (vazio só para cliente público), `MICROSOFT_TENANT`
   (vazio: `organizations`), `MICROSOFT_REDIRECT_URI` e `ESCRITORIO_DOMINIOS`. Preencher o `MICROSOFT_CLIENT_ID` liga.
3. Cada pessoa liga a própria conta pela interface.

[A FAZER (Marcelo e Isabel, back-end, Sprint 3): rotas `GET /integracoes/microsoft_365/autorizar` e `GET .../callback`
(mesmo desenho do Google Workspace) e o `ProvedorNoBanco` com tokens cifrados. Hoje o provedor é `ProvedorEmMemoria`.]
[A FAZER (Larissa, interface): botão "Conectar conta" e "Desconectar" na tela de conectores.]

## Hoje

Conector real escrito e testado contra um servidor local falso que imita o login da Microsoft, o Graph e o endereço
de download (`backend/tests/apoio_escritorio.py`, em loopback). **Não foi possível testar contra a Microsoft de
verdade**: não há app registrado nem conta, e o projeto só usa dado sintético. Quem tiver o app roda, com
`MODO_TERMINAL=1`:

`python -m ferramentas.integracoes testar microsoft_365`

O comando manda um código inventado ao endereço de token: `invalid_grant` quer dizer que o `client_id` (e o segredo)
foram aceitos; `invalid_client` ou `unauthorized_client`, que o app está errado. Depois, com uma conta de teste ligada,
conferir à mão: eventos de hoje, leitura de uma planilha e de um `.docx`, adicionar linha (inclusive texto como
`=1+1` e `10/12`) e criar planilha, e apagar o que sobrar.

Com `MICROSOFT_MODO=simulado`, o mesmo mundo simulado do Google Workspace responde no formato do real (`fonte`
simulada), em memória e só para a pessoa.
