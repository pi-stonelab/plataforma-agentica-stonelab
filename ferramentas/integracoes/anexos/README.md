# Anexos do chat

Os arquivos que a pessoa envia na conversa (entrada) e os que o agente entrega de volta (saída). Fica numa pasta da
própria plataforma, separada por pessoa. Não é um serviço externo: serve para o agente ler o que a pessoa anexou e
devolver uma planilha ou um texto pronto, sem caminho de disco nem link público.

## Ferramentas que usam

- `documentos_e_agenda/ler_arquivo_anexado` (leitura)
- `documentos_e_agenda/entregar_arquivo` (escrita sem confirmação: só grava na pasta da própria pessoa; decisão G4)

## Conector

`anexos/conector.py` (`ConectorAnexos`), sobre a base `Conector` (tipo `interno`): modos `real`, `simulado` e
`desligado` (`ANEXOS_MODO`), disjuntor, `testar` e saúde.

- Entrada: txt, csv, xlsx, docx e pdf, até 5 MB. Saída: csv, xlsx e txt. Id de entrada `ANX-` + 12 letras, de saída
  `ARQ-` + 12 letras: quem pede diz o id, nunca um caminho.
- Disco: `<ANEXOS_DIRETORIO>/<entrada|saida>/<id_usuario>/<id>__<nome seguro>`, permissão 0600, gravação atômica,
  abertura sem seguir link simbólico. Até 30 arquivos e 50 MB por pessoa; arquivo com mais de 7 dias é apagado no
  próximo envio da mesma pessoa. Uma pessoa nunca enxerga o arquivo de outra.
- Leitura (`formatos.py`, biblioteca padrão; o PDF usa `pypdf` se instalado): macro, zip com caminho suspeito,
  parte cifrada, `DOCTYPE`/entidade em XML e texto com byte nulo são recusados; fórmula nunca é calculada; o que passa
  do limite de linhas ou de caracteres volta cortado com `truncado` e `aviso_de_corte`.
- O conteúdo do anexo é de terceiros: vai em `conteudo_de_terceiros`, mascarado antes do modelo, e é dado, nunca
  instrução. Na saída, texto que parece fórmula ganha um apóstrofo para não executar ao abrir na planilha.
- Falha de disco vira `integracao_indisponivel` e alimenta o disjuntor.

## Ligação

No `.env`: `ANEXOS_DIRETORIO` (caminho absoluto fora do repositório; preencher liga) e, se quiser, `ANEXOS_MODO`.
`MODO_TERMINAL=1 python -m ferramentas.integracoes testar anexos` grava, lê e apaga um arquivo de prova na pasta.

[A FAZER (Marcelo, back-end): rota de envio do chat (sugestão: `POST /conversas/{id}/anexos`): confere o token, lê o
arquivo (multipart) até 5 MB e chama `anexos.guardar_entrada(id_usuario_do_token, nome, bytes)`, devolvendo o `anexo_id`;
na montagem do turno, listar os anexos da conversa (`listar_entradas`). Rota de download (sugestão:
`GET /arquivos/{arquivo_id}`): confere o token e chama `anexos.abrir_saida(id_usuario_do_token, arquivo_id)`, com
`Content-Disposition: attachment`, o tipo do arquivo e `X-Content-Type-Options: nosniff`.]
[A FAZER (Larissa, interface): botão de anexar no chat (txt, csv, xlsx, docx e pdf, até 5 MB) e o link de download
do arquivo que o agente entrega, com o `arquivo_id` da resposta da ferramenta.]

## Hoje

Conector real pronto, testado em pasta temporária (`backend/tests/test_integracoes_anexos.py`). Falta só ligar o
upload e o download do chat (acima). Com `ANEXOS_MODO=simulado`, os arquivos ficam na memória, com três de exemplo
por pessoa tirados do mundo do `mock/` (planilhas de indicadores agregados, sem dado de lojista), e o que a pessoa
entrega some quando a plataforma reinicia.
