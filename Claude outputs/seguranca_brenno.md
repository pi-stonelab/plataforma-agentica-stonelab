# Regras provisórias de segurança das ferramentas

Para: Brenno (segurança, KAN-62, KAN-63, KAN-69). De: Pedro (frente 4).
Tudo está em `ferramentas/governanca.py`. Quando as entregas oficiais chegarem, só esse arquivo muda.

## Premissas

- O usuário da plataforma é sempre um funcionário da Stone. O lojista aparece só como dado
  (`id_cliente`), nunca opera a plataforma.
- A credencial que chega à ferramenta é a do funcionário, montada pelo sistema autenticado, nunca pelo modelo.
- O código decide o acesso, nunca o modelo. Na dúvida, bloqueia (falha fechado).

## Regras provisórias (nível e área)

- Níveis: N1 e N2 (N2 é o mais alto). Áreas de funcionário: atendimento, financeiro, dados, tecnologia.
- Cada ferramenta tem uma ficha com nível mínimo, áreas permitidas, sensibilidade e categorias de dados.
  `motivo_bloqueio(ferramenta, usuario)` devolve `None` (liberado) ou uma frase curta sem dados.
- Bloqueia se: usuário ausente, sem `id_usuario` ou com nível ou área fora das listas; ficha com valor fora das listas;
  nível abaixo do mínimo; área fora das permitidas (exceto `"todas"`).
- A ficha nova nasce fechada: o padrão é nível N2, nenhuma área, sensibilidade sigilosa.
- Escopo de carteira: N2 vê qualquer cliente, N1 só os da própria `carteira`.
  `cliente_no_escopo(usuario, id_cliente)` é checado antes de buscar o dado.

## Matriz da ficha e a razão de cada linha

Nível mínimo é N1 em quase todas, porque nesta fase o nível controla sobretudo o escopo de carteira.
As exceções são `consultar_saldo_conta` (saldo de conta de lojista) e `consultar_taxa_contestacao_mensal`
(indicador sensível do negócio): só N2.

- Atendimento: áreas atendimento e financeiro, sensibilidade pessoal. Mostra cadastro de lojista, então
  não é para a área de dados nem de tecnologia.
- Financeiro: áreas atendimento e financeiro, sensibilidade sigilosa. Transações de cliente são o dado
  mais sensível. O atendimento entra porque precisa explicar cobrança ao lojista.
- `calcular_parcelas`, `calcular_roi` e `calcular_multa_atraso`: todas as áreas, pública. É conta pura
  sobre números que a pessoa informa, sem dado de cliente.
- Dados e indicadores: áreas dados e financeiro, interna. Indicadores agregados e descrição de conjuntos de
  dados não identificam lojista, mas são internos.
- Comunicação: todas as áreas, pessoal. Mensagens têm texto de pessoas; a proteção vem do escopo e do registro.
- Documentos e agenda, chamados internos: todas as áreas, interna. São rotina de qualquer funcionário.
- Consultas públicas (CEP, câmbio): todas as áreas, pública. Dado aberto.
- Plataforma (`solicitar_ferramenta_ausente`): todas as áreas, interna. Só registra um pedido.

[aqui conectamos com Brenno: níveis e áreas oficiais, KAN-62]

## O que trocar quando as suas entregas chegarem

- KAN-62 (nível e área): trocar `NIVEIS`, `AREAS_USUARIO` e a classe `Usuario` pelas oficiais.
  Se a ordem dos níveis mudar, `motivo_bloqueio` continua usando a posição na tupla `NIVEIS`.
- KAN-69 (escopo de carteira): trocar o corpo de `cliente_no_escopo`. A assinatura fica.
- KAN-63 (mascaramento): entra como passo novo antes de `Ferramenta.executar` devolver `dados`.
  [aqui conectamos com Brenno: função de mascaramento, KAN-63]

## Por que não há mascaramento hoje

As ferramentas ativas não devolvem CPF, CNPJ, e-mail nem telefone. Só devolvem o que o dicionário de
dados da ferramenta lista (por exemplo, nome fantasia, segmento, cidade, UF, situação, data de início).
Os dados são sintéticos. Quando uma ferramenta passar a devolver documento ou contato, o mascaramento
da KAN-63 precisa estar ligado antes de ela ficar ativa.

## Credenciais por funcionário

Credencial de sistema externo (CRM, banco, Jira) fica com o conector, em variável de ambiente ou em um
cofre por funcionário. Nunca passa pelo modelo, pelos argumentos nem pelo registro. Nesta rodada nenhuma
ferramenta ativa chama sistema externo.
[aqui conectamos com Brenno: cofre de credenciais por funcionário]

## LGPD

- Finalidade: cada ferramenta tem uma finalidade no `agents.md` e as categorias de dados na ficha.
- Necessidade: só as colunas listadas na saída de cada ferramenta; nada de `SELECT *`.
- Teto de linhas: 50 por consulta (`LIMITE_LINHAS`); acima disso a resposta vem truncada e avisa.
- Registro sem conteúdo: cada chamada guarda ferramenta, funcionário (identificador interno, nunca
  nome ou e-mail), status, tipo de erro, duração e categorias de dados. Nunca argumentos, dados,
  mensagem ou texto de exceção.
- Dados sintéticos: nenhum dado pessoal real em código, testes ou documentos.
- [preencher: prazo de retenção de `REGISTROS` e quem pode consultá-los, definir com Brenno e o monitoramento]
- [preencher: base legal e encarregado (DPO), definir com a Stone]
