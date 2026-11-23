"""Base de conhecimento do atendimento: artigos públicos que a equipe escreveu a partir das regras do
DOC-MOCK (§2.2, §6.2 a §6.6 e §7.2 a §7.8). Texto próprio, sem dado de lojista nem de pessoa.

Os números aqui são os de `regras.py`. Se uma regra mudar lá, o artigo dela muda aqui junto (um teste
confere os principais valores).
"""

from datetime import date

DATA_DOS_ARTIGOS = date(2026, 10, 1)

# (código, título, categoria, texto)
ARTIGOS = (
    (
        "KB001", "Quando cai o dinheiro de cada venda", "Recebimento",
        (
            "Venda no débito cai em 1 dia útil. Crédito à vista cai em 30 dias. No parcelado, cada parcela "
            "cai 30 dias depois da anterior: a primeira em 30 dias, a segunda em 60, e assim por diante. Pix "
            "cai na hora na Conta Stone e não entra na agenda. Data que cai em sábado ou domingo passa para o "
            "próximo dia útil."
        ),
    ),
    (
        "KB002", "O que é a liquidação e por que ela pode falhar", "Recebimento",
        (
            "Todo dia útil a Stone soma o que o lojista tem para receber naquele dia, desconta o que ele deve "
            "(faturas com desconto na agenda, parcelas de acordo e chargebacks perdidos) e deposita o resto "
            "na conta de recebimento. Se a conta de recebimento estiver inválida, a liquidação falha, o "
            "dinheiro fica retido e um chamado de Recebimento com prioridade alta é aberto sozinho. A Stone "
            "tenta de novo a cada dia útil. Se o desconto passar do que havia para receber, a diferença vira "
            "uma fatura de saldo negativo."
        ),
    ),
    (
        "KB003", "Como funciona a antecipação de recebíveis", "Antecipação",
        (
            "Antecipar é receber antes o que está na agenda. O desconto é calculado parcela por parcela: "
            "valor da parcela vezes a taxa mensal do plano vezes os dias antecipados divididos por 30. A taxa "
            "é de 2,99% ao mês no plano Essencial e de 2,49% no plano Volume; no plano Negociado ela é "
            "combinada com o lojista. O dinheiro antecipado cai em 1 dia útil. O atendimento pode simular a "
            "qualquer momento, mas só o especialista N2 executa, e só com o pedido do lojista registrado num "
            "chamado."
        ),
    ),
    (
        "KB004", "Quando a antecipação é recusada", "Antecipação",
        (
            "A antecipação é recusada em quatro casos: a parcela está retida ou bloqueada (por exemplo, por "
            "um chargeback em aberto), o lojista está bloqueado, a conta de recebimento está em verificação, "
            "ou o lojista tem fatura vencida há mais de 15 dias."
        ),
    ),
    (
        "KB005", "Aluguel da maquininha e faturas", "Fatura e aluguel",
        (
            "O aluguel é cobrado todo dia 1, com vencimento no dia 10: R$ 39,90 no plano Essencial e R$ 29,90 "
            "no plano Volume. Ele não é cobrado se as vendas do mês anterior passaram do mínimo de isenção do "
            "plano (R$ 5.000 no Essencial e R$ 15.000 no Volume). No vencimento, a Stone tenta descontar da "
            "agenda; se não houver saldo, o que faltar vira boleto com 5 dias para pagar."
        ),
    ),
    (
        "KB006", "Multa e juros de fatura em atraso", "Fatura e aluguel",
        (
            "Fatura paga com atraso tem multa única de 2% e juros de 1% ao mês, proporcionais aos dias de "
            "atraso (o mês conta como 30 dias). Exemplo: uma fatura de R$ 320,00 paga com 40 dias de atraso "
            "fica em R$ 330,67, sendo R$ 6,40 de multa e R$ 4,27 de juros."
        ),
    ),
    (
        "KB007", "O que acontece quando a fatura atrasa", "Fatura e aluguel",
        (
            "Três dias antes do vencimento o lojista recebe um lembrete. Com 1 dia de atraso, recebe o aviso "
            "de fatura vencida. Com 5 dias, um segundo aviso e a ligação da Cobrança. Com 15 dias, a "
            "antecipação fica bloqueada. Com 30 dias, o lojista não contrata produtos novos e a fatura ganha "
            "um analista responsável. Com 60 dias, a fatura vai para cobrança externa."
        ),
    ),
    (
        "KB008", "Acordos de parcelamento de dívidas", "Fatura e aluguel",
        (
            "A analista de cobrança fecha sozinha acordos de até 6 parcelas, com entrada de pelo menos 20% e "
            "sem desconto no valor principal. Até 12 parcelas, ou com desconto no principal de até 10%, quem "
            "aprova é o coordenador financeiro. Acima de R$ 10.000, o acordo precisa de duas aprovações, e "
            "quem pediu nunca aprova. Com 2 parcelas vencidas, o acordo quebra e os encargos voltam."
        ),
    ),
    (
        "KB009", "Chargeback: prazos e documentos", "Contestação",
        (
            "Chargeback é quando quem comprou contesta a compra no banco do cartão. O valor da venda fica "
            "retido na agenda enquanto o caso corre. O lojista é avisado em até 1 dia útil e tem 7 dias "
            "corridos, a partir do aviso, para mandar a defesa; sem defesa, o chargeback é aceito. A decisão "
            "final sai em até 120 dias. Os documentos dependem do motivo: para mercadoria não recebida, nota "
            "fiscal e comprovante de entrega; para compra não reconhecida, comprovante da venda e nota "
            "fiscal; para produto diferente do anunciado, nota fiscal, descrição ou fotos do produto e a "
            "conversa com o cliente."
        ),
    ),
    (
        "KB010", "Devolução de Pix pelo MED", "Pix e devolução",
        (
            "O MED, mecanismo do Banco Central, devolve Pix em casos de fraude ou golpe. Ele não vale para "
            "arrependimento, erro de chave ou desacordo comercial. Quando chega um pedido de MED, o valor "
            "fica bloqueado na Conta Stone do lojista. Desde 1º de setembro de 2026, o lojista tem até 80 "
            "dias para contestar uma devolução que considere indevida, por exemplo mostrando o comprovante de "
            "entrega."
        ),
    ),
    (
        "KB011", "Cancelamento de venda", "Recebimento",
        (
            "Se o lojista cancela a venda antes da liquidação, as parcelas dela saem da agenda. Depois da "
            "liquidação, o cancelamento vira um estorno, descontado das próximas liquidações."
        ),
    ),
    (
        "KB012", "Planos e taxas de cada venda", "Taxas e planos",
        (
            "A taxa de cada venda, o MDR, depende do plano. Essencial, para lojistas pequenos: débito 1,99%, "
            "crédito à vista 3,49%, parcelado de 2 a 6 vezes 4,29% e de 7 a 12 vezes 4,99%. Volume, para "
            "médio porte: débito 1,49%, crédito à vista 2,99%, parcelado de 2 a 6 vezes 3,79% e de 7 a 12 "
            "vezes 4,49%. No Negociado, para contas grandes, as taxas são combinadas e ficam abaixo do "
            "Volume. O Pix não tem taxa."
        ),
    ),
    (
        "KB013", "Troca da conta de recebimento e verificação de identidade", "Alteração cadastral",
        (
            "Antes de mostrar dado confidencial ou mudar qualquer coisa, o atendimento confirma que fala com "
            "um contato do cadastro: o telefone ou o e-mail precisa estar cadastrado, a pessoa informa o CNPJ "
            "e recebe um código no contato cadastrado. A troca da conta de recebimento é mais rígida, porque "
            "é o golpe que mais rende: só o especialista N2 faz, o código vai para o contato antigo, e a "
            "conta nova fica 24 horas em verificação, com as liquidações indo para a conta antiga nesse "
            "período. Pedido de troca vindo de número fora do cadastro é tratado como suspeita e vai para o "
            "N2."
        ),
    ),
    (
        "KB014", "Prazos de atendimento", "Atendimento",
        (
            "Todo contato gera um protocolo no formato data mais sequência do dia, que vai na primeira "
            "resposta. O prazo para resolver depende da prioridade: crítica (lojista sem conseguir vender ou "
            "com a conta bloqueada) em 4 horas corridas, alta (dinheiro do lojista em jogo) em 1 dia útil, "
            "média em 3 dias úteis e baixa em 5 dias úteis. A ouvidoria tem prazo de 10 dias úteis, "
            "prorrogável por mais 15 dias com aviso ao lojista, e só recebe casos que já passaram pelos "
            "canais normais."
        ),
    ),
)
