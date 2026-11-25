# DataHub

Dicionário de dados da Stone simulada: as tabelas de cada sistema, as colunas, quais são restritas e de onde cada tabela é calculada. Não guarda dado, só a descrição do esquema.

## Ferramentas que usam

- `dados_e_indicadores/buscar_conjuntos_dados` (leitura)
- `dados_e_indicadores/consultar_esquema_conjunto` (leitura)
- `dados_e_indicadores/consultar_responsavel_conjunto` (leitura)
- `dados_e_indicadores/consultar_linhagem_conjunto` (leitura)

## Conector

`integracoes/sistemas_internos.py` (`ConectorInterno`), modo sempre `simulado`, sem sistema de `mock.falhas`: o dicionário sai do esquema em código, não do banco.

## Ligação

`dados_sinteticos.dicionario_de_dados()` (gerado de `mock/modelos.py` e de `regras.CLASSIFICACAO_CAMPOS`), lido pelas ferramentas por `ferramentas/dicionario.py`, que calcula os derivados a partir da origem.

## Hoje

Dados simulados. Trocar pelo DataHub real é trocar `ferramentas/dicionario.py` pela API de busca de conjuntos, mantendo os mesmos campos de saída.
