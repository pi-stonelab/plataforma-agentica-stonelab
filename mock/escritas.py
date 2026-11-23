"""Escrita nos sistemas simulados: o que as ferramentas de escrita gravam depois que a pessoa confirma.

Cada operação roda numa transação só (tudo ou nada) e confere de novo, dentro dela, as regras do DOC-MOCK:
ciclo do chamado (§6.5), liquidação (§7.3), antecipação (§7.4) e alçadas (§7.9). Quem chama já passou pela
governança das ferramentas (cargo, área, categoria e carteira); aqui ficam as regras do negócio, que valem
para qualquer um que escreva.

O relógio do mock está parado: toda escrita acontece em `regras.AGORA_DO_MOCK`.

Sistema fora do ar (`mock.falhas`) é conferido antes da transação: nada é gravado. Regra violada levanta
`EscritaRecusada` com o tipo de erro e uma frase para a pessoa; a transação é desfeita.

No Postgres, quem grava é o papel `mock_escrita` (`PRIVILEGIOS_DE_ESCRITA`, gerado em `03_papeis.sh` por
`mock/exportar.py`): lê tudo, insere só nas tabelas abaixo e altera só as colunas listadas.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from . import falhas, regras
from .banco import trava_de_acesso
from .consultas import (
    filtro_dos_recebiveis_antecipaveis,
    motivos_de_recusa_da_antecipacao,
)
from .modelos import (
    CANAIS,
    CANAL_INTERNO,
    CATEGORIAS_DE_CHAMADO,
    Acordo,
    Antecipacao,
    Chamado,
    ContaRecebimento,
    Fatura,
    Funcionario,
    Interacao,
    Liquidacao,
    Lojista,
    Recebivel,
)

TIPOS_DE_RECUSA = ("nao_encontrado", "parametro_invalido", "permissao_negada")
TIPOS_DE_NOTA = ("nota_interna", "resposta_ao_lojista")
ORDEM_DOS_NIVEIS = regras.NIVEIS_DE_ATENDIMENTO  # N1 < N2 < supervisor

# O que o papel de escrita do Postgres pode fazer, tabela por tabela. Uma fonte só: `mock/exportar.py` gera os
# GRANT daqui, e um teste confere que cada operação abaixo só mexe no que está listado.
PRIVILEGIOS_DE_ESCRITA = {
    "chamados": {
        "insert": True,
        "update": ("situacao", "id_responsavel", "resolvido_em", "nivel_atendimento", "suspeita_fraude"),
    },
    "interacoes": {"insert": True, "update": ()},
    "liquidacoes": {"insert": True, "update": ("situacao",)},
    "acordos": {"insert": True, "update": ("situacao", "id_aprovador")},
    "faturas": {"insert": False, "update": ("situacao", "id_acordo")},
    "antecipacoes": {"insert": True, "update": ()},
    "recebiveis": {"insert": False, "update": ("situacao", "id_antecipacao")},
}
# Tabela que o gerador deixa vazia: só a escrita da plataforma a preenche (antecipação só com pedido do lojista).
TABELAS_SO_DA_ESCRITA = ("antecipacoes",)
# Sequências dos ids inteiros das tabelas em que o papel insere (o Postgres numera com SERIAL).
SEQUENCIAS_DE_ESCRITA = ("interacoes_id_seq", "liquidacoes_id_seq")


class EscritaRecusada(Exception):
    """Uma regra do negócio não deixa gravar. `mensagem` é para a pessoa e não traz dado restrito."""

    def __init__(self, tipo_erro: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.tipo_erro = tipo_erro
        self.mensagem = mensagem


@contextmanager
def _transacao(engine: Engine, *sistemas: str) -> Iterator[Session]:
    """Confere os sistemas antes de abrir e grava tudo de uma vez no fim (ou nada, se algo levantar)."""
    for sistema in sistemas:
        falhas.verificar(sistema)
    with trava_de_acesso(engine), Session(engine) as sessao, sessao.begin():
        yield sessao


def _lojista(sessao: Session, codigo: str) -> Lojista:
    lojista = sessao.get(Lojista, codigo)
    if lojista is None:
        raise EscritaRecusada("nao_encontrado", "Lojista não encontrado.")
    return lojista


def _funcionario_ativo(sessao: Session, id_funcionario: str) -> Funcionario:
    funcionario = sessao.get(Funcionario, id_funcionario)
    if funcionario is None or funcionario.situacao != "ativo":
        raise EscritaRecusada("permissao_negada", "Funcionário sem acesso para gravar.")
    return funcionario


def _chamado_do_lojista(sessao: Session, codigo_lojista: str, codigo_chamado: str) -> Chamado:
    """O chamado, travado para esta transação (no Postgres, FOR UPDATE). Outro lojista: não encontrado."""
    chamado = sessao.scalar(
        select(Chamado)
        .where(Chamado.codigo == codigo_chamado, Chamado.id_lojista == codigo_lojista)
        .with_for_update()
    )
    if chamado is None:
        raise EscritaRecusada("nao_encontrado", "Chamado não encontrado para este lojista.")
    return chamado


def _proximo_codigo(sessao: Session, coluna, prefixo: str, digitos: int) -> str:
    maior = sessao.scalar(select(func.max(coluna)))
    numero = int(maior[len(prefixo):]) + 1 if maior else 1
    return f"{prefixo}{numero:0{digitos}d}"


def _proximo_protocolo(sessao: Session, momento: datetime) -> str:
    prefixo = f"{momento:%Y%m%d}-"
    maior = sessao.scalar(select(func.max(Chamado.protocolo)).where(Chamado.protocolo.like(prefixo + "%")))
    numero = int(maior[len(prefixo):]) + 1 if maior else 1
    return f"{prefixo}{numero:06d}"


def _proximo_dia_util() -> date:
    return regras.somar_dias_uteis(datetime.combine(regras.HOJE_DO_MOCK, time()), 1).date()


def _acima(nivel: str, outro: str) -> bool:
    return ORDEM_DOS_NIVEIS.index(nivel) > ORDEM_DOS_NIVEIS.index(outro)


def _nivel_de_atendimento(funcionario: Funcionario) -> str:
    """O nível de quem atende chamados, pelo cargo do diretório (nunca pelo que quem chama diz)."""
    nivel = regras.NIVEL_DE_ATENDIMENTO_DO_CARGO.get(funcionario.cargo)
    if nivel is None:
        raise EscritaRecusada("permissao_negada", "Seu cargo não atende chamados.")
    return nivel


def classificar_chamado(
    categoria: str,
    fila: str,
    impede_vender: bool = False,
    valor_envolvido_centavos: int | None = None,
    nivel_minimo: str | None = None,
) -> dict:
    """Prioridade (§6.3), nível (§6.3 e §6.5) e prazo (§6.4) de um chamado aberto agora, sem banco: a prévia e a
    abertura usam a mesma conta. O nível é o da categoria, N2 quando o valor envolvido passa de R$ 1.000, e nunca
    abaixo de `nivel_minimo`. Máquina que não deixa vender é crítica."""
    if categoria not in CATEGORIAS_DE_CHAMADO:
        raise EscritaRecusada("parametro_invalido", "Categoria de chamado desconhecida.")
    prioridade = regras.PRIORIDADE_POR_CATEGORIA[categoria]
    if impede_vender and categoria == regras.CATEGORIA_QUE_FICA_CRITICA_SE_NAO_VENDE:
        prioridade = "crítica"
    nivel = regras.NIVEL_DE_ATENDIMENTO_POR_CATEGORIA[categoria]
    if valor_envolvido_centavos and valor_envolvido_centavos > regras.VALOR_QUE_SOBE_O_CHAMADO_PARA_O_N2_CENTAVOS:
        nivel = max(nivel, "N2", key=ORDEM_DOS_NIVEIS.index)
    if nivel_minimo:
        nivel = max(nivel, nivel_minimo, key=ORDEM_DOS_NIVEIS.index)
    prazo = regras.prazo_do_chamado(regras.AGORA_DO_MOCK, prioridade, fila)
    return {"prioridade": prioridade, "nivel_atendimento": nivel, "prazo_em": prazo}


def _descrever_chamado(chamado: Chamado) -> dict:
    return {
        "codigo": chamado.codigo,
        "protocolo": chamado.protocolo,
        "categoria": chamado.categoria,
        "prioridade": chamado.prioridade,
        "fila": chamado.fila,
        "nivel_atendimento": chamado.nivel_atendimento,
        "situacao": chamado.situacao,
        "id_responsavel": chamado.id_responsavel,
        "prazo_em": chamado.prazo_em.isoformat(),
        "suspeita_fraude": chamado.suspeita_fraude,
    }


# ---------------------------------------------------------------------------------------------
# CRM: chamados e mensagens (DOC-MOCK §6.3 a §6.6)
# ---------------------------------------------------------------------------------------------


def abrir_chamado(
    engine: Engine,
    codigo_lojista: str,
    categoria: str,
    resumo: str,
    canal: str,
    id_funcionario: str,
    impede_vender: bool = False,
    valor_envolvido_centavos: int | None = None,
    nivel_minimo: str | None = None,
) -> dict:
    """Abre um chamado pelo funcionário. Fila, prioridade, nível e prazo saem das regras, nunca de quem pede.

    Quem abre fica responsável se o nível dele dá conta do chamado; senão o chamado fica "novo", na fila do nível
    certo. `nivel_minimo` sobe o nível (o pedido de antecipação vai para o N2).
    """
    if canal not in CANAIS:
        raise EscritaRecusada("parametro_invalido", "Canal desconhecido.")
    if not resumo.strip():
        raise EscritaRecusada("parametro_invalido", "O resumo não pode ficar vazio.")
    with _transacao(engine, "cadastro", "crm") as sessao:
        lojista = _lojista(sessao, codigo_lojista)
        nivel_de_quem_abre = _nivel_de_atendimento(_funcionario_ativo(sessao, id_funcionario))
        classe = classificar_chamado(categoria, lojista.carteira, impede_vender, valor_envolvido_centavos, nivel_minimo)
        fica_com_quem_abre = not _acima(classe["nivel_atendimento"], nivel_de_quem_abre)
        momento = regras.AGORA_DO_MOCK
        chamado = Chamado(
            codigo=_proximo_codigo(sessao, Chamado.codigo, "CH", 6),
            protocolo=_proximo_protocolo(sessao, momento),
            id_lojista=lojista.codigo,
            categoria=categoria,
            prioridade=classe["prioridade"],
            fila=lojista.carteira,
            id_responsavel=id_funcionario if fica_com_quem_abre else None,
            situacao="em_atendimento" if fica_com_quem_abre else "novo",
            aberto_por="funcionario",
            aberto_em=momento,
            prazo_em=classe["prazo_em"],
            resumo=resumo.strip(),
            nivel_atendimento=classe["nivel_atendimento"],
            suspeita_fraude=False,
        )
        sessao.add(chamado)
        sessao.flush()
        return _descrever_chamado(chamado)


def _canal_da_conversa(sessao: Session, chamado: Chamado) -> str:
    """O canal em que o lojista falou por último; sem mensagem dele, WhatsApp, o canal mais usado (§11.3)."""
    canal = sessao.scalar(
        select(Interacao.canal)
        .where(Interacao.id_chamado == chamado.codigo, Interacao.autor == "lojista")
        .order_by(Interacao.data_hora.desc(), Interacao.id.desc())
    )
    return canal or CANAIS[0]


def adicionar_nota(
    engine: Engine,
    codigo_lojista: str,
    codigo_chamado: str,
    texto: str,
    tipo: str,
    id_funcionario: str,
    *,
    escrita_pelo_agente: bool,
) -> dict:
    """Grava uma nota interna (só a equipe vê) ou uma resposta ao lojista, pelo canal em que ele falou.

    Texto escrito pelo agente de IA fica com autor "agente" (§6.8), sempre com `id_funcionario` = quem revisou e
    confirmou. Chamado fechado não recebe mais nada (§6.5: um novo contato abre outro chamado).
    """
    if tipo not in TIPOS_DE_NOTA:
        raise EscritaRecusada("parametro_invalido", "Tipo de nota desconhecido.")
    if not texto.strip():
        raise EscritaRecusada("parametro_invalido", "O texto não pode ficar vazio.")
    with _transacao(engine, "crm") as sessao:
        _funcionario_ativo(sessao, id_funcionario)
        chamado = _chamado_do_lojista(sessao, codigo_lojista, codigo_chamado)
        if chamado.situacao == "fechado":
            raise EscritaRecusada("parametro_invalido", "O chamado está fechado: um novo contato abre outro chamado.")
        canal = CANAL_INTERNO if tipo == "nota_interna" else _canal_da_conversa(sessao, chamado)
        interacao = Interacao(
            id_chamado=chamado.codigo,
            autor="agente" if escrita_pelo_agente else "funcionario",
            canal=canal,
            data_hora=regras.AGORA_DO_MOCK,
            texto=texto.strip(),
            teste_seguranca=False,
            id_funcionario=id_funcionario,
        )
        sessao.add(interacao)
        sessao.flush()
        return {"id_chamado": chamado.codigo, "tipo": tipo, "canal": canal, "data_hora": interacao.data_hora.isoformat()}


def atualizar_chamado(
    engine: Engine,
    codigo_lojista: str,
    codigo_chamado: str,
    id_funcionario: str,
    nova_situacao: str | None = None,
    encaminhar_para: str | None = None,
    suspeita_fraude: bool = False,
) -> dict:
    """Muda a situação, sobe o chamado de nível ou marca suspeita de fraude (§6.5 e §6.6).

    - Situação: só as passagens de `regras.TRANSICOES_DO_CHAMADO`, por alguém do nível do chamado ou acima.
      Pegar um chamado novo ("em_atendimento") põe quem pegou como responsável. Na fila da ouvidoria, só a
      ouvidoria muda a situação ou encaminha (marcar suspeita e escrever nota continuam valendo).
    - Encaminhar: só para cima (N1 para N2 ou supervisor). O chamado volta a "novo", sem responsável, na fila
      do novo nível.
    - Suspeita de fraude: marca e sobe para o N2, se estiver abaixo (o golpe da troca de conta, cenário 6).
    """
    if nova_situacao is None and encaminhar_para is None and not suspeita_fraude:
        raise EscritaRecusada("parametro_invalido", "Diga o que muda: situação, encaminhamento ou suspeita de fraude.")
    with _transacao(engine, "crm") as sessao:
        funcionario = _funcionario_ativo(sessao, id_funcionario)
        nivel_do_funcionario = _nivel_de_atendimento(funcionario)
        chamado = _chamado_do_lojista(sessao, codigo_lojista, codigo_chamado)
        if chamado.situacao == "fechado":
            raise EscritaRecusada("parametro_invalido", "O chamado está fechado: um novo contato abre outro chamado.")
        if nova_situacao is not None or encaminhar_para is not None:
            _conferir_quem_mexe(chamado, funcionario.cargo, nivel_do_funcionario)
        if nova_situacao is not None:
            _mudar_situacao(chamado, nova_situacao, id_funcionario)
        destino = encaminhar_para
        if suspeita_fraude:
            chamado.suspeita_fraude = True
            if destino is None and _acima(regras.NIVEL_DA_SUSPEITA_DE_FRAUDE, chamado.nivel_atendimento):
                destino = regras.NIVEL_DA_SUSPEITA_DE_FRAUDE
        if destino is not None:
            _encaminhar(chamado, destino)
        sessao.flush()
        return _descrever_chamado(chamado)


def _conferir_quem_mexe(chamado: Chamado, cargo: str, nivel_do_funcionario: str) -> None:
    """Na fila da ouvidoria, só a ouvidoria; nas outras, alguém do nível do chamado ou acima."""
    if chamado.fila == regras.FILA_OUVIDORIA:
        if cargo not in regras.CARGOS_DA_OUVIDORIA:
            raise EscritaRecusada("permissao_negada", "Caso da ouvidoria: só a ouvidoria muda a situação ou encaminha.")
    elif _acima(chamado.nivel_atendimento, nivel_do_funcionario):
        raise EscritaRecusada("permissao_negada", "Este chamado está com um nível acima do seu.")


def _mudar_situacao(chamado: Chamado, nova: str, id_funcionario: str) -> None:
    if nova not in regras.TRANSICOES_DO_CHAMADO.get(chamado.situacao, ()):
        raise EscritaRecusada(
            "parametro_invalido", f"O chamado está {chamado.situacao.replace('_', ' ')} e não pode ir para essa situação."
        )
    if chamado.situacao == "novo":
        chamado.id_responsavel = id_funcionario
    chamado.situacao = nova
    chamado.resolvido_em = regras.AGORA_DO_MOCK if nova == "resolvido" else None


def _encaminhar(chamado: Chamado, destino: str) -> None:
    if destino not in ORDEM_DOS_NIVEIS:
        raise EscritaRecusada("parametro_invalido", "Encaminhe para N2 ou supervisor.")
    if not _acima(destino, chamado.nivel_atendimento):
        raise EscritaRecusada("parametro_invalido", "O chamado já está nesse nível ou acima: encaminhe só para cima.")
    if chamado.situacao in regras.SITUACOES_DE_CHAMADO_SEM_ENCAMINHAMENTO:
        raise EscritaRecusada("parametro_invalido", "Chamado resolvido não é encaminhado: reabra antes.")
    chamado.nivel_atendimento = destino
    chamado.id_responsavel = None
    chamado.situacao = "novo"
    chamado.resolvido_em = None


# ---------------------------------------------------------------------------------------------
# Core: liquidação e antecipação (DOC-MOCK §7.3 e §7.4)
# ---------------------------------------------------------------------------------------------


def reprocessar_liquidacao(engine: Engine, codigo_lojista: str, id_liquidacao: int, id_funcionario: str) -> dict:
    """Agenda uma nova tentativa da liquidação que falhou, para o próximo dia útil, se a conta estiver ativa.

    A original passa a "reprocessada" (o motivo da falha fica). A nova nasce "agendada", ligada a ela. O recebível
    do dia continua retido até a nova tentativa ser paga (§7.3).
    """
    with _transacao(engine, "cadastro", "core") as sessao:
        _funcionario_ativo(sessao, id_funcionario)
        liquidacao = sessao.scalar(
            select(Liquidacao)
            .where(Liquidacao.id == id_liquidacao, Liquidacao.id_lojista == codigo_lojista)
            .with_for_update()
        )
        if liquidacao is None:
            raise EscritaRecusada("nao_encontrado", "Liquidação não encontrada para este lojista.")
        if liquidacao.situacao not in regras.SITUACOES_DE_LIQUIDACAO_QUE_REPROCESSAM:
            raise EscritaRecusada("parametro_invalido", "Só a liquidação que falhou é reprocessada.")
        conta = sessao.scalar(select(ContaRecebimento.situacao).where(ContaRecebimento.id_lojista == codigo_lojista))
        if conta != regras.SITUACAO_DA_CONTA_QUE_RECEBE:
            raise EscritaRecusada(
                "parametro_invalido",
                "A conta de recebimento não está ativa: o N2 corrige a conta antes, e só então a liquidação é "
                "reprocessada.",
            )
        nova = Liquidacao(
            id_lojista=codigo_lojista,
            data=_proximo_dia_util(),  # o core tenta de novo no próximo dia útil (§7.3)
            valor_total_centavos=liquidacao.valor_total_centavos,
            situacao="agendada",
            motivo_falha=None,
            id_liquidacao_original=liquidacao.id,
        )
        liquidacao.situacao = "reprocessada"
        sessao.add(nova)
        sessao.flush()
        return {
            "id_liquidacao": liquidacao.id,
            "id_nova_tentativa": nova.id,
            "data": nova.data.isoformat(),
            "valor_total_centavos": nova.valor_total_centavos,
        }


def executar_antecipacao(engine: Engine, codigo_lojista: str, codigo_chamado: str, id_funcionario: str) -> dict:
    """Antecipa hoje tudo o que dá, com o pedido do lojista registrado no chamado (§7.4).

    Confere de novo as recusas do §7.4 e o chamado (do lojista, categoria Antecipação, não fechado). As parcelas
    são as mesmas da simulação (`consultas.filtro_dos_recebiveis_antecipaveis`), e o desconto é calculado
    parcela por parcela, como nela. Grava a antecipação, marca as parcelas e deixa uma nota no chamado.
    """
    with _transacao(engine, "cadastro", "cobranca", "core", "crm") as sessao:
        _funcionario_ativo(sessao, id_funcionario)
        lojista = _lojista(sessao, codigo_lojista)
        chamado = _chamado_do_lojista(sessao, codigo_lojista, codigo_chamado)
        if chamado.categoria != regras.CATEGORIA_DO_PEDIDO_DE_ANTECIPACAO or chamado.situacao == "fechado":
            raise EscritaRecusada(
                "parametro_invalido", "O pedido do lojista precisa estar num chamado de Antecipação ainda aberto."
            )
        motivos = _motivos_de_recusa(sessao, lojista)
        if motivos:
            rotulos = ", ".join(regras.ROTULOS_DOS_MOTIVOS_DE_RECUSA_DA_ANTECIPACAO[m] for m in motivos)
            raise EscritaRecusada("parametro_invalido", f"Antecipação recusada: {rotulos}.")
        parcelas = sessao.scalars(
            select(Recebivel).where(*filtro_dos_recebiveis_antecipaveis(codigo_lojista)).with_for_update()
        ).all()
        if not parcelas:
            raise EscritaRecusada("parametro_invalido", "Não há parcelas para antecipar.")
        taxa = regras.TAXA_ANTECIPACAO_PONTOS_BASE[regras.PLANO_POR_PORTE[lojista.porte]]
        credito = regras.data_de_credito_da_antecipacao()
        bruto = sum(p.valor_parcela_centavos for p in parcelas)
        desconto = sum(
            regras.desconto_da_antecipacao_centavos(p.valor_parcela_centavos, (p.data_prevista - credito).days, taxa)
            for p in parcelas
        )
        antecipacao = Antecipacao(
            codigo=_proximo_codigo(sessao, Antecipacao.codigo, "AN", 4),
            id_lojista=codigo_lojista,
            id_chamado=chamado.codigo,
            pedida_por="lojista",
            id_executor=id_funcionario,
            executada_em=regras.AGORA_DO_MOCK,
            valor_antecipado_bruto_centavos=bruto,
            desconto_antecipacao_centavos=desconto,
            valor_antecipado_liquido_centavos=bruto - desconto,
            taxa_antecipacao_pontos_base=taxa,
            data_credito=credito,
            situacao="executada",
        )
        sessao.add(antecipacao)
        sessao.flush()
        for parcela in parcelas:
            parcela.situacao = "antecipado"
            parcela.id_antecipacao = antecipacao.codigo
        sessao.add(Interacao(
            id_chamado=chamado.codigo, autor="funcionario", canal=CANAL_INTERNO, data_hora=regras.AGORA_DO_MOCK,
            texto=f"Antecipação {antecipacao.codigo} executada a pedido do lojista.", teste_seguranca=False,
            id_funcionario=id_funcionario,
        ))
        sessao.flush()
        return {
            "codigo": antecipacao.codigo,
            "id_chamado": chamado.codigo,
            "quantidade_de_parcelas": len(parcelas),
            "valor_antecipado_bruto_centavos": bruto,
            "desconto_antecipacao_centavos": desconto,
            "valor_antecipado_liquido_centavos": bruto - desconto,
            "taxa_antecipacao_pontos_base": taxa,
            "data_credito": credito.isoformat(),
        }


def _motivos_de_recusa(sessao: Session, lojista: Lojista) -> list[str]:
    """As recusas do §7.4 que valem para o lojista inteiro, lidas dentro da transação da execução."""
    return motivos_de_recusa_da_antecipacao(sessao, lojista.codigo) or []


# ---------------------------------------------------------------------------------------------
# Cobrança: acordos (DOC-MOCK §7.5 e §7.9)
# ---------------------------------------------------------------------------------------------


def _faturas_para_o_acordo(sessao: Session, codigo_lojista: str, codigos: tuple[str, ...] | None) -> list[Fatura]:
    """Faturas vencidas e fora de acordo. Com `codigos`, exatamente essas (todas precisam valer)."""
    consulta = (
        select(Fatura)
        .where(Fatura.id_lojista == codigo_lojista, Fatura.situacao == "vencida", Fatura.id_acordo.is_(None))
        .order_by(Fatura.vencimento, Fatura.codigo)
        .with_for_update()
    )
    faturas = sessao.scalars(consulta).all()
    if codigos:
        por_codigo = {fatura.codigo: fatura for fatura in faturas}
        if any(codigo not in por_codigo for codigo in codigos):
            raise EscritaRecusada("parametro_invalido", "Só entram faturas vencidas deste lojista que não estão em acordo.")
        faturas = [por_codigo[codigo] for codigo in dict.fromkeys(codigos)]
    if not faturas:
        raise EscritaRecusada("nao_encontrado", "O lojista não tem fatura vencida fora de acordo.")
    return faturas


def _percentual_de(centavos: int, percentual: Decimal, arredondamento: str) -> int:
    return int((Decimal(centavos) * percentual / 100).to_integral_value(arredondamento))


def montar_acordo(
    faturas: list[dict],
    numero_de_parcelas: int,
    entrada_percentual: Decimal | int | None,
    perdoar_encargos: bool,
    desconto_principal_percentual: Decimal | int,
) -> dict:
    """Os números do acordo (§7.5 e §7.9), sem banco: a prévia e a gravação usam a mesma conta.

    `faturas`: [{"valor_centavos", "vencimento" (date)}]. Sem `entrada_percentual`, a entrada mínima da analista
    (20% do renegociado). A entrada arredonda para cima e o desconto para baixo, ao centavo: o arredondamento nunca
    tira o acordo da alçada que os percentuais pedidos dão.
    """
    if not 1 <= numero_de_parcelas <= regras.PARCELAS_MAXIMAS_COORDENADOR:
        raise EscritaRecusada(
            "parametro_invalido", f"O acordo vai de 1 a {regras.PARCELAS_MAXIMAS_COORDENADOR} parcelas (§7.9)."
        )
    if entrada_percentual is None:
        entrada_percentual = regras.ENTRADA_MINIMA_ANALISTA_PERCENTUAL
    entrada_percentual, desconto_principal_percentual = Decimal(entrada_percentual), Decimal(desconto_principal_percentual)
    if not (0 <= entrada_percentual < 100 and 0 <= desconto_principal_percentual < 100):
        raise EscritaRecusada("parametro_invalido", "A entrada e o desconto são percentuais de 0 a 99.")
    original = sum(f["valor_centavos"] for f in faturas)
    encargos = sum(
        sum(regras.encargos_de_atraso_centavos(f["valor_centavos"], (regras.HOJE_DO_MOCK - f["vencimento"]).days))
        for f in faturas
    )
    desconto = _percentual_de(original, desconto_principal_percentual, ROUND_FLOOR)
    perdao = encargos if perdoar_encargos else 0
    renegociado = original + encargos - perdao - desconto
    entrada = _percentual_de(renegociado, entrada_percentual, ROUND_CEILING)
    alcada = regras.alcada_do_acordo(original, renegociado, numero_de_parcelas, entrada, perdao, desconto)
    if alcada == "proibido":
        raise EscritaRecusada(
            "parametro_invalido",
            "Acordo fora das regras: até 12 parcelas e desconto no principal de até 10% (§7.9).",
        )
    return {
        "valor_original_centavos": original,
        "encargos_centavos": encargos,
        "perdao_encargos_centavos": perdao,
        "desconto_principal_centavos": desconto,
        "valor_renegociado_centavos": renegociado,
        "entrada_centavos": entrada,
        "numero_de_parcelas": numero_de_parcelas,
        "valor_da_parcela_centavos": -(-(renegociado - entrada) // numero_de_parcelas),
        "alcada": alcada,
    }


def faturas_do_acordo(engine: Engine, codigo_lojista: str, codigos: tuple[str, ...] | None) -> list[dict]:
    """As faturas que entrariam no acordo (para a prévia): [{"codigo", "valor_centavos", "vencimento"}]."""
    falhas.verificar("cobranca")
    with trava_de_acesso(engine), Session(engine) as sessao:
        _lojista(sessao, codigo_lojista)
        return [
            {"codigo": f.codigo, "valor_centavos": f.valor_centavos, "vencimento": f.vencimento}
            for f in _faturas_para_o_acordo(sessao, codigo_lojista, codigos)
        ]


def registrar_acordo(
    engine: Engine,
    codigo_lojista: str,
    codigos_das_faturas: tuple[str, ...],
    numero_de_parcelas: int,
    entrada_percentual: Decimal | int | None,
    perdoar_encargos: bool,
    desconto_principal_percentual: Decimal | int,
    id_solicitante: str,
) -> dict:
    """Grava o acordo com as faturas da prévia, recalculado agora.

    Na alçada de quem pede (`regras.ALCADAS_DE_ACORDO_DO_CARGO`), o acordo nasce ativo e quem pediu é o aprovador
    ("negocia dentro da alçada", §8.2). Acima, nasce "pendente_aprovacao" e as faturas continuam vencidas até a
    aprovação (a régua segue, §7.5). Dupla aprovação nunca nasce ativa.
    """
    with _transacao(engine, "cadastro", "cobranca") as sessao:
        _lojista(sessao, codigo_lojista)
        solicitante = _funcionario_ativo(sessao, id_solicitante)
        alcadas = regras.ALCADAS_DE_ACORDO_DO_CARGO.get(solicitante.cargo)
        if not alcadas:
            raise EscritaRecusada("permissao_negada", "Seu cargo não negocia acordos.")
        faturas = _faturas_para_o_acordo(sessao, codigo_lojista, codigos_das_faturas)
        numeros = montar_acordo(
            [{"valor_centavos": f.valor_centavos, "vencimento": f.vencimento} for f in faturas],
            numero_de_parcelas, entrada_percentual, perdoar_encargos, desconto_principal_percentual,
        )
        na_alcada_de_quem_pede = numeros["alcada"] in alcadas
        acordo = Acordo(
            codigo=_proximo_codigo(sessao, Acordo.codigo, "AC", 4),
            id_lojista=codigo_lojista,
            valor_original_centavos=numeros["valor_original_centavos"],
            valor_renegociado_centavos=numeros["valor_renegociado_centavos"],
            entrada_centavos=numeros["entrada_centavos"],
            numero_de_parcelas=numero_de_parcelas,
            perdao_encargos_centavos=numeros["perdao_encargos_centavos"],
            desconto_principal_centavos=numeros["desconto_principal_centavos"],
            alcada=numeros["alcada"],
            id_solicitante=id_solicitante,
            id_aprovador=id_solicitante if na_alcada_de_quem_pede else None,
            criado_em=regras.HOJE_DO_MOCK,
            situacao="ativo" if na_alcada_de_quem_pede else "pendente_aprovacao",
        )
        sessao.add(acordo)
        sessao.flush()
        for fatura in faturas:
            fatura.id_acordo = acordo.codigo
            fatura.situacao = "em_acordo" if na_alcada_de_quem_pede else "vencida"
        sessao.flush()
        return {"codigo": acordo.codigo, "situacao": acordo.situacao, "faturas": [f.codigo for f in faturas], **numeros}


def _decide_o_acordo(cargo: str, alcada: str) -> bool:
    if alcada == "dupla_aprovacao":
        return cargo in regras.CARGOS_DA_SEGUNDA_APROVACAO
    return alcada in regras.ALCADAS_DE_ACORDO_DO_CARGO.get(cargo, ())


def decidir_acordo(engine: Engine, codigo_acordo: str, aprovar: bool, id_aprovador: str) -> dict:
    """Aprova ou recusa um acordo pendente. Quem pediu nunca decide (§8.1, segregação; §7.9), e quem decide precisa
    ter a alçada do acordo; a dupla aprovação é dada pelo coordenador (§8.2)."""
    with _transacao(engine, "cobranca") as sessao:
        aprovador = _funcionario_ativo(sessao, id_aprovador)
        acordo = sessao.scalar(select(Acordo).where(Acordo.codigo == codigo_acordo).with_for_update())
        if acordo is None:
            raise EscritaRecusada("nao_encontrado", "Acordo não encontrado.")
        if acordo.situacao != "pendente_aprovacao":
            raise EscritaRecusada("parametro_invalido", "Só acordo pendente de aprovação é aprovado ou recusado.")
        if acordo.id_solicitante == id_aprovador:
            raise EscritaRecusada("permissao_negada", "Quem pediu o acordo não pode aprová-lo nem recusá-lo.")
        if not _decide_o_acordo(aprovador.cargo, acordo.alcada):
            raise EscritaRecusada("permissao_negada", "Este acordo passa da sua alçada.")
        faturas = sessao.scalars(select(Fatura).where(Fatura.id_acordo == acordo.codigo).with_for_update()).all()
        if aprovar:
            acordo.situacao, acordo.id_aprovador = "ativo", id_aprovador
            for fatura in faturas:
                fatura.situacao = "em_acordo"
        else:
            acordo.situacao = "recusado"  # o esquema não guarda quem recusou: fica no registro da plataforma
            for fatura in faturas:
                fatura.id_acordo = None
        sessao.flush()
        return {
            "codigo": acordo.codigo,
            "id_cliente": acordo.id_lojista,
            "situacao": acordo.situacao,
            "alcada": acordo.alcada,
            "valor_renegociado_centavos": acordo.valor_renegociado_centavos,
            "faturas": [f.codigo for f in faturas],
        }
