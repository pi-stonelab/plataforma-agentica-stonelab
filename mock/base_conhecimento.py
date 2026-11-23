"""Base de conhecimento do atendimento: artigos públicos que a equipe escreveu a partir das regras do
DOC-MOCK (§2.2, §6.2 a §6.6 e §7.2 a §7.9). Texto próprio, sem dado de lojista nem de pessoa.

Os artigos falam com o lojista ("você"), como uma central de ajuda: o atendimento pode repassar o texto
como está. Procedimento interno (quem aprova, quem executa) entra só no que o lojista precisa saber.

Os números aqui são os de `regras.py`. Se uma regra mudar lá, o artigo dela muda aqui junto (um teste
confere os principais valores). Os sinônimos são as palavras que o lojista usa e que não aparecem no
texto ("caiu", "depósito", "defeito"...): a busca (`consultas.buscar_artigos`) procura neles também.
"""

from datetime import date

DATA_DOS_ARTIGOS = date(2026, 10, 1)

# (código, título, categoria, texto, sinônimos)
ARTIGOS = (
    (
        "KB001", "Quando cai o dinheiro de cada venda", "Recebimento",
        (
            "Venda no débito cai em 1 dia útil. Crédito à vista cai em 30 dias corridos. No parcelado, cada "
            "parcela cai 30 dias corridos depois da anterior: a primeira em 30 dias, a segunda em 60, e assim "
            "por diante. Pix cai na hora na sua Conta Stone e não entra na agenda. Se a data cair em sábado ou "
            "domingo, o dinheiro chega no próximo dia útil."
        ),
        "caiu cair recebo receber deposito depositado prazo agenda dinheiro credito debito pix parcela",
    ),
    (
        "KB002", "O que é a liquidação e por que ela pode falhar", "Recebimento",
        (
            "Todo dia útil a Stone soma o que você tem para receber naquele dia, desconta o que você deve "
            "(faturas, parcelas de acordo e chargebacks perdidos) e deposita o resto na sua conta de "
            "recebimento. Se a conta de recebimento estiver inválida, o depósito falha e o dinheiro fica "
            "retido, sem se perder: a Stone abre um chamado para resolver e tenta de novo a cada dia útil "
            "depois que a conta for corrigida. Se o desconto passar do que havia para receber, a diferença "
            "vira uma fatura de saldo negativo."
        ),
        "deposito caiu cair falhou falha retido conta invalida banco recebimento dinheiro",
    ),
    (
        "KB003", "Como funciona a antecipação de recebíveis", "Antecipação",
        (
            "Antecipar é receber antes o que está na sua agenda. O desconto é calculado parcela por parcela: "
            "valor da parcela vezes a taxa mensal do seu plano vezes os dias antecipados divididos por 30. "
            "Exemplo: R$ 1.000,00 antecipados 30 dias no plano Essencial custam R$ 29,90. A taxa é de 2,99% ao "
            "mês no plano Essencial e de 2,49% no plano Volume; no plano Negociado, ela é a combinada no seu "
            "contrato. O dinheiro antecipado cai em 1 dia útil, então a parcela que já cairia nesse dia não "
            "entra. Você pode pedir uma simulação a qualquer momento; a antecipação só é feita com o seu "
            "pedido registrado num chamado."
        ),
        "antecipar adiantar adiantamento receber antes taxa simulacao simular agenda",
    ),
    (
        "KB004", "Quando a antecipação é recusada", "Antecipação",
        (
            "A antecipação não é feita quando: a parcela está retida ou bloqueada (por exemplo, por um "
            "chargeback em aberto); a sua conta está bloqueada; a sua conta de recebimento está em "
            "verificação, como nas 24 horas depois de uma troca de conta; ou você tem fatura vencida há mais "
            "de 15 dias. Resolvido o motivo, dá para pedir de novo."
        ),
        "antecipar recusada recusa negada consigo bloqueada bloqueio",
    ),
    (
        "KB005", "Aluguel da maquininha e faturas", "Fatura e aluguel",
        (
            "O aluguel é cobrado todo dia 1, com vencimento no dia 10: R$ 39,90 no plano Essencial e R$ 29,90 "
            "no plano Volume. Ele não é cobrado se as suas vendas do mês anterior passaram do mínimo de "
            "isenção do plano (R$ 5.000 no Essencial e R$ 15.000 no Volume). No vencimento, a fatura pode ser "
            "descontada da sua agenda; se não for, ela fica em aberto como boleto, com 5 dias para pagar."
        ),
        "aluguel mensalidade cobranca cobrado taxa maquininha fatura boleto isencao",
    ),
    (
        "KB006", "Multa e juros de fatura em atraso", "Fatura e aluguel",
        (
            "Se você paga uma fatura com atraso, ela tem multa única de 2% e juros de 1% ao mês, "
            "proporcionais aos dias de atraso (o mês conta como 30 dias). Exemplo: uma fatura de R$ 320,00 paga "
            "com 40 dias de atraso fica em R$ 330,67, sendo R$ 6,40 de multa e R$ 4,27 de juros."
        ),
        "multa juros atraso atrasada encargos vencida divida",
    ),
    (
        "KB007", "O que acontece quando a fatura atrasa", "Fatura e aluguel",
        (
            "Três dias antes do vencimento você recebe um lembrete. Com 1 dia de atraso, recebe o aviso de "
            "fatura vencida. Com 5 dias, um segundo aviso e a ligação da Cobrança. Com 15 dias, a antecipação "
            "fica bloqueada. Com 30 dias, você não contrata produtos novos e a fatura passa a ter um analista "
            "responsável. Com 60 dias, a fatura vai para cobrança externa."
        ),
        "atraso atrasada vencida cobranca aviso lembrete ligacao divida",
    ),
    (
        "KB008", "Acordos de parcelamento de dívidas", "Fatura e aluguel",
        (
            "Você pode parcelar uma dívida com a Stone num acordo. Até 6 parcelas, com entrada de pelo menos "
            "20% e sem desconto no valor principal, o acordo sai na hora com a Cobrança, que também pode "
            "perdoar a multa e os juros de dívidas de até R$ 2.000. Entrada menor que 20%, de 7 a 12 parcelas, "
            "perdão de encargos em dívida maior ou desconto de até 10% no valor principal passam pela "
            "aprovação da coordenação. Acima de 12 parcelas ou de 10% de desconto no principal, o acordo não "
            "é possível. Acordos acima de R$ 10.000 passam por duas aprovações. Se duas parcelas do acordo "
            "vencerem sem pagamento, o acordo é desfeito e os encargos voltam."
        ),
        "acordo parcelar parcelamento negociar negociacao divida desconto entrada aprovacao",
    ),
    (
        "KB009", "Chargeback: prazos e documentos", "Contestação",
        (
            "Chargeback é quando quem comprou contesta a compra no banco do cartão. Enquanto o caso corre, o "
            "que você receberia pela venda (o valor já sem a taxa) fica retido na sua agenda. Você é avisado "
            "em até 1 dia útil e tem 7 dias corridos, a partir do aviso, para mandar a defesa; sem defesa, o "
            "chargeback é aceito. A decisão final sai em até 120 dias. Os documentos dependem do motivo: "
            "compra não reconhecida pede o comprovante da venda e a nota fiscal; mercadoria não recebida, a "
            "nota fiscal e o comprovante de entrega; produto diferente do anunciado, a nota fiscal, fotos ou "
            "descrição do produto e a conversa com o cliente; cobrança duplicada, os comprovantes das duas "
            "vendas; valor diferente do combinado, a nota fiscal e o comprovante da venda; cancelamento não "
            "processado, a política de cancelamento aceita pelo cliente e o comprovante de estorno."
        ),
        "chargeback contestacao contestar contestada estorno disputa defesa documentos retido",
    ),
    (
        "KB010", "Devolução de Pix pelo MED", "Pix e devolução",
        (
            "O MED, mecanismo do Banco Central, devolve Pix em casos de fraude ou golpe. Ele não vale para "
            "arrependimento, erro de chave ou desacordo comercial. Quando chega um pedido de MED, o valor "
            "fica bloqueado na sua Conta Stone. Desde 1º de setembro de 2026, você tem até 80 dias para "
            "contestar uma devolução que considere indevida, por exemplo mostrando o comprovante de entrega."
        ),
        "med pix devolucao devolver bloqueado golpe fraude contestar",
    ),
    (
        "KB011", "Cancelamento de venda", "Recebimento",
        (
            "Se você cancela a venda antes do depósito, as parcelas dela saem da agenda. Depois do depósito, o "
            "cancelamento vira um estorno, descontado dos próximos depósitos."
        ),
        "cancelar cancelamento estorno estornar devolver venda",
    ),
    (
        "KB012", "Planos e taxas de cada venda", "Taxas e planos",
        (
            "A taxa de cada venda, o MDR, depende do seu plano. Essencial, para lojistas pequenos: débito "
            "1,99%, crédito à vista 3,49%, parcelado de 2 a 6 vezes 4,29% e de 7 a 12 vezes 4,99%. Volume: "
            "débito 1,49%, crédito à vista 2,99%, parcelado de 2 a 6 vezes 3,79% e de 7 a 12 vezes 4,49%. "
            "Negociado, para contas grandes: as taxas são as do seu contrato e ficam abaixo das do Volume. O "
            "Pix não tem taxa. O atendimento confirma qual é o seu plano."
        ),
        "taxa taxas mdr plano tarifa porcentagem cobrado quanto",
    ),
    (
        "KB013", "Troca da conta de recebimento", "Alteração cadastral",
        (
            "Por segurança, a troca da conta de recebimento só é feita com um código enviado ao telefone ou "
            "e-mail que já está no seu cadastro, e nunca por pedido vindo de um número que não está "
            "cadastrado. Depois da troca, a conta nova fica 24 horas em verificação, e os depósitos desse "
            "período vão para a conta antiga. A Stone nunca pede senha nem código por mensagem."
        ),
        "trocar troca mudar conta banco recebimento cadastro alterar seguranca golpe codigo",
    ),
    (
        "KB014", "Prazos de atendimento", "Atendimento",
        (
            "Todo contato gera um protocolo, que vai na primeira resposta. O prazo para resolver depende da "
            "prioridade: quando você não consegue vender ou está com a conta bloqueada, até 4 horas corridas; "
            "quando o seu dinheiro está em jogo, 1 dia útil; nos outros casos, de 3 a 5 dias úteis. A "
            "ouvidoria responde em até 10 dias úteis, prorrogáveis por mais 15 com aviso, e recebe casos que "
            "já passaram pelo atendimento sem solução."
        ),
        "prazo protocolo demora tempo ouvidoria reclamacao atendimento resposta",
    ),
    (
        "KB015", "A maquininha não liga, trava ou não lê o cartão", "Maquininha",
        (
            "Desligue e ligue a maquininha de novo, confira a bateria e se ela está conectada ao Wi-Fi ou ao "
            "chip. Se continuar, fale com o atendimento: abrimos um chamado de maquininha e, se for preciso, "
            "mandamos outra. Quando você não consegue vender, o prazo é de 4 horas corridas. Enquanto isso, "
            "dá para vender por Pix ou por link de pagamento."
        ),
        "maquininha maquina defeito quebrada liga ligar travou trava tela chip cartao erro comunicacao",
    ),
    (
        "KB016", "O depósito veio menor do que eu esperava", "Recebimento",
        (
            "O depósito do dia soma as parcelas que caem naquele dia e desconta o que você deve: aluguel, "
            "parcela de acordo, chargeback perdido ou estorno de venda cancelada. Se o valor veio menor, a "
            "diferença precisa aparecer em um desses descontos. Se não aparecer, o atendimento confere a sua "
            "agenda e o depósito do dia e abre um chamado para corrigir."
        ),
        "deposito menor faltando diferenca veio menos desconto descontado liquidacao valor errado",
    ),
    (
        "KB017", "Segunda via do boleto", "Fatura e aluguel",
        (
            "O atendimento pode enviar de novo o boleto de uma fatura sua em aberto, com o mesmo valor e "
            "vencimento. Se a fatura já venceu, o boleto novo inclui a multa e os juros do atraso."
        ),
        "boleto segunda via pagar fatura aluguel codigo barras",
    ),
    (
        "KB018", "Comprovante de venda e de depósito", "Recebimento",
        (
            "O comprovante de cada venda sai na via do lojista, impressa ou na tela da sua maquininha. Os "
            "depósitos e as vendas do dia ficam no seu extrato, e o atendimento pode confirmar a data e o valor "
            "de uma venda ou de um depósito pelo código dela."
        ),
        "comprovante extrato recibo via encontro venda deposito",
    ),
)
