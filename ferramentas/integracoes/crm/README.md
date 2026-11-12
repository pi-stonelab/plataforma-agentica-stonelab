# CRM

[preencher: o que é este sistema e para que a plataforma o usa]

## Ferramentas que usam

- `atendimento/consultar_cliente` (leitura)
- `atendimento/buscar_clientes` (leitura)
- `atendimento/listar_tickets_cliente` (leitura)
- `atendimento/consultar_ticket` (leitura)
- `atendimento/consultar_historico_contato` (leitura)
- `atendimento/abrir_ticket` (escrita)
- `atendimento/atualizar_status_ticket` (escrita)
- `atendimento/adicionar_nota_ticket` (escrita)

## Conector

[preencher: como a plataforma fala com ele e como checa se está de pé]

## Ligação

[aqui conectamos com o banco simulado do back-end (KAN-32, Marcelo e Isabel)]

## Hoje

Dados simulados em `ferramentas/dados_sinteticos.py` (`buscar_cliente`): lê o cadastro do lojista no banco do mock (`mock/consultas.py`); a fachada não devolve contato nem conta. Trocar pelo real é trocar o corpo dessa função.
