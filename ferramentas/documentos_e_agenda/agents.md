# documentos_e_agenda

Agenda, planilhas, documentos e arquivos do próprio funcionário (Google ou Microsoft) e os arquivos que ele anexa na conversa.

## Como escolher

- Ver ou conferir a agenda: `listar_eventos_agenda`. Marcar um evento: `criar_evento_agenda`.
- Achar um arquivo pelo nome: `buscar_arquivos`; depois, `ler_planilha` (planilha) ou `ler_documento` (texto).
- Registrar uma linha numa planilha que já existe: `adicionar_linha_planilha`. Planilha nova: `criar_planilha`.
- O funcionário anexou um arquivo na conversa: `ler_arquivo_anexado`. Quer receber um arquivo pronto: `entregar_arquivo`.
- Tudo aqui é da conta do próprio funcionário, nunca de outra pessoa. As que criam algo só montam a prévia: quem
  confirma é o funcionário, na tela.
- Se a mensagem disser que a conta não está ligada, avise o funcionário para conectá-la na tela de integrações.
- Use só as que aparecem na lista abaixo: as outras não estão liberadas para você.

## Ferramentas

[aqui conectamos com o catálogo: ferramentas desta área liberadas para o
usuário]

## Para quem mantém

- Integrações da área: `google_workspace`, `microsoft_365` (alternativas, conta OAuth de cada pessoa) e `anexos`.
- Ferramentas ativas (9):
  - `listar_eventos_agenda` (leitura)
  - `criar_evento_agenda` (escrita em duas fases)
  - `ler_planilha` (leitura)
  - `adicionar_linha_planilha` (escrita em duas fases)
  - `criar_planilha` (escrita em duas fases)
  - `ler_documento` (leitura)
  - `buscar_arquivos` (leitura)
  - `ler_arquivo_anexado` (leitura)
  - `entregar_arquivo` (escrita sem prévia: só grava na pasta de saída da própria plataforma)
- Integração desligada no `.env` tira a ferramenta do índice do modelo; com Google e Microsoft, a ferramenta só
  some se as duas estão desligadas.
