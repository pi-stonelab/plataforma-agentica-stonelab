# mock/ — a Stone simulada

Banco de dados 100% sintético (empresa fictícia) que as ferramentas leem no lugar dos sistemas reais da
Stone. Fonte das regras: DOC-MOCK (`§` nos comentários do código). Esta é a fase 1 reduzida: 20 lojistas,
15 funcionários, cenários 1, 3, 5 e 7 e a falha "fora do ar".

## Para que serve cada arquivo
- `regras.py`: configuração sem banco. `HOJE_DO_MOCK` (15/10/2026), carteiras, os 10 cargos (área, perfil de
  acesso, nível de ferramenta, escopo de lojistas, janela de dias, categorias de dado), máscaras por campo
  (`CLASSIFICACAO_CAMPOS`, chaveada pelo NOME DO CAMPO que as consultas devolvem; os campos livres ficam em
  `CAMPOS_NAO_RESTRITOS`; campo fora das duas listas sai mascarado) e taxas. Cargo desconhecido: `regra_do_cargo` devolve `None` (quem chama nega).
- `modelos.py`: tabelas SQLAlchemy (`BaseMock`, separada da `Base` do back-end). Dinheiro em centavos.
- `banco.py`: `criar_engine`, `url_padrao`, `criar_tabelas`, `apagar_tabelas` (só mexem nas tabelas do mock).
- `gerar.py`: recria o mundo do zero, sempre igual (semente fixa, sem Faker).
- `consultas.py`: o "conector": leituras com teto de 50 linhas e só as colunas necessárias. Não decide permissão. Já calcula `dias_em_atraso` (faturas) e `dias_em_aberto` (chamados) a partir de `HOJE_DO_MOCK`, e `buscar_interacoes` exige o lojista dono do chamado.
- `falhas.py`: sistema "fora do ar" (`cadastro`, `core`, `cobranca`, `crm`, `diretorio`).

## Como recriar
    python -m mock.gerar                     # usa DATABASE_URL, ou SQLite em dados_locais/mock.sqlite
    python -m mock.gerar --url sqlite://     # só confere que o mundo gera (memória)
Recriar APAGA e refaz as tabelas do mock (as outras tabelas do banco ficam como estão).
Falha: `MOCK_FALHAS=core,crm` deixa esses sistemas fora do ar (testes usam `ligar` e `desligar`).

## Cenários plantados (códigos fixos)
- 1 (M00001, Padaria Pão da Vila, ME, varejo): conta de recebimento `invalida`; liquidação de 14/10/2026 de
  R$ 1.842,30 com situação `falhou`; chamado `Recebimento`/`alta` aberto pelo sistema, ligado à liquidação.
- 3 (M00003, Studio Bela Unha, MEI): saldo negativo de R$ 320,00 vencido há 40 dias (05/09/2026) e dois aluguéis
  de R$ 39,90 vencidos.
- 5: atendente Ana (F0001, `atendente_n1`, varejo) e M00005 (Clínica Sorriso Leve, média, contas-chave,
  especialista N2 responsável F0003). O sócio de M00001 tem CPF 123.456.789-09 (mascarado: `***.456.789-**`).
- 7 (M00009): interação de autor lojista com a instrução escondida, marcada `teste_seguranca` e com o
  `comportamento_esperado`.
- Casos negativos do DOC-MOCK §8.4: F0014 `desligado`, F0015 `afastado`.

## Escolhas do mock (o DOC-MOCK não define)
- Datas dos aluguéis vencidos de M00003: vencimentos em 10/09 (35 dias) e 10/10 (5 dias).
- Lojista do cenário 5 (CPF do sócio): M00001. Lojista do cenário 7: M00009. Porte de M00006 a M00008.
- CPFs dos demais contatos têm dígitos verificadores errados de propósito (não identificam ninguém).
  Telefones usam o padrão `(21) 90000-NNNN`; e-mails, o domínio `.example`.
- Um aluguel por lojista (não por maquininha); feriados não adiam liquidação; códigos `CH` e `I` com 6 dígitos.

## Pessoas reais de teste e LGPD
Todos os dados de lojistas e de funcionários do mock são fictícios. Para testar com colegas, crie
`dados_locais/pessoas_teste.csv` com as colunas `id,cargo,email,nome` (`nome` opcional; `id` no formato
`F9xxx`; `cargo` um dos 10 do mock) e rode `python -m mock.gerar`, ou passe `--pessoas-teste CAMINHO`.
- Colete só o mínimo e só com a ciência da pessoa. Prefira id neutro e apelido; o e-mail é obrigatório na
  coluna, mas nada impede usar um endereço de teste.
- O arquivo e o banco local ficam fora do Git (`.gitignore`: `dados_locais/`, `*.sqlite`, `*.sqlite3`).
  Nunca coloque o CSV em outra pasta nem no repositório.
- Linha inválida recusa o arquivo inteiro; a mensagem diz a linha e o campo, sem repetir o valor.
- Senha de login não fica no CSV (é definida por comando, na etapa do back-end). Recriar o mundo apaga as
  pessoas importadas e importa de novo do CSV.
