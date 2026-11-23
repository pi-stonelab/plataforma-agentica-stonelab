# CRM

[preencher: o que é este sistema e para que a plataforma o usa]

## Ferramentas que usam

- `atendimento/consultar_cliente` (leitura)
- `atendimento/buscar_clientes` (leitura)
- `atendimento/listar_chamados_cliente` (leitura)
- `atendimento/consultar_ticket` (leitura)
- `atendimento/consultar_historico_contato` (leitura)
- `atendimento/consultar_contatos_lojista` (leitura)
- `atendimento/abrir_chamado` (escrita com confirmação)
- `atendimento/atualizar_situacao_chamado` (escrita com confirmação)
- `atendimento/adicionar_nota_chamado` (escrita com confirmação)
- `atendimento/registrar_pedido_antecipacao` (escrita com confirmação)

## Conector

`integracoes/sistemas_internos.py` (`ConectorInterno`), modo sempre `simulado`: o CRM é o mock. A saúde vem dos sistemas `cadastro` e `crm` de `mock.falhas`.

## Ligação

[aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]

## Hoje

Dados simulados em `ferramentas/dados_sinteticos.py` (`buscar_cliente`, `buscar_chamados`, `buscar_interacoes`, `buscar_contatos`): lê o banco do mock (`mock/consultas.py`). `buscar_cliente` não devolve contato nem conta; `buscar_chamados` não devolve o resumo; `buscar_contatos` devolve em claro e a máscara é de `Ferramenta.executar`. Trocar pelo real é trocar o corpo dessa função.
