"""Avaliação do uso de ferramentas pelo agente: quantas vezes ele escolheu as ferramentas certas.

Roda cenários fixos (pergunta, quem pergunta, ferramentas esperadas) e mede, por pedido: se as
ferramentas certas foram executadas, se a resposta traz o dado esperado, quantos passos e chamadas ao
modelo foram gastos e quanto tempo levou. O que foi executado vem do registro da governança
(`ferramentas.governanca.REGISTROS`), não do que o modelo diz ter feito.

Com o modelo real (precisa de `LLM_URL` e das credenciais no .env):
    python -m agentes.avaliacao
    python -m agentes.avaliacao --cenario multa --cenario cadastro_e_transacoes
    python -m agentes.avaliacao --salvar avaliacao.json

O arquivo salvo guarda só números e nomes de cenário e de ferramenta: nunca a pergunta, a resposta
nem dado de lojista. Tokens por chamada ainda não entram: dependem do `LLMClient` do back-end.
"""

import argparse
import inspect
import json
import re
import statistics
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from agentes.agente_atendimento import agente as motor
from ferramentas import governanca

ANA = "F0001"        # atendente N1, carteira varejo: M00001 é dela, M00002 não
RENATA = "F0011"     # coordenadora financeira N2: todos os lojistas


@dataclass(frozen=True)
class Cenario:
    """Um pedido de teste. `esperadas` são as ferramentas que devem rodar com sucesso (sem ordem);
    `negadas` as que devem ser tentadas e recusadas pela governança. `padroes` são expressões
    regulares que a resposta final precisa casar (todas)."""

    nome: str
    pergunta: str
    funcionario: str
    esperadas: tuple[str, ...]
    negadas: tuple[str, ...] = ()
    padroes: tuple[str, ...] = ()


CENARIOS = (
    Cenario(
        "multa",
        "Uma fatura de R$ 1000 está 30 dias atrasada. Qual o valor total com multa e juros?",
        RENATA,
        ("calcular_multa_atraso",),
        padroes=(r"1\.?030",),
    ),
    Cenario(
        "cadastro",
        "Quem é o lojista M00001?",
        RENATA,
        ("consultar_cliente",),
        padroes=(r"Padaria P[ãa]o da Vila",),
    ),
    Cenario(
        "transacoes",
        "Quais foram as últimas transações do lojista M00001?",
        RENATA,
        ("consultar_transacoes_cliente",),
        padroes=(r"T0000625",),
    ),
    Cenario(
        "cep",
        "Qual é o endereço do CEP 01310-100?",
        RENATA,
        ("consultar_endereco_cep",),
        padroes=(r"Avenida Paulista",),
    ),
    Cenario(
        "cadastro_e_transacoes",
        "Me diga o nome do lojista M00001 e a transação mais recente dele.",
        RENATA,
        ("consultar_cliente", "consultar_transacoes_cliente"),
        padroes=(r"Padaria P[ãa]o da Vila", r"T0000625"),
    ),
    Cenario(
        "cadastro_transacoes_e_multa",
        "Do lojista M00001, quero o nome, a transação mais recente e o total de uma fatura de "
        "R$ 1000 com 30 dias de atraso.",
        RENATA,
        ("consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso"),
        padroes=(r"Padaria P[ãa]o da Vila", r"T0000625", r"1\.?030"),
    ),
    Cenario(
        "lojista_de_outra_carteira",
        "Quem é o lojista M00002?",
        ANA,
        (),
        negadas=("consultar_cliente",),
    ),
)


@dataclass
class Resultado:
    cenario: str
    tipo: str                   # final, pergunta ou limite
    motivo: str | None
    passos: int                 # linhas da trajetória do turno
    chamadas_ao_modelo: int
    segundos_no_modelo: float
    segundos_total: float
    executadas: tuple[str, ...]  # ferramentas que rodaram com sucesso, na ordem
    negadas: tuple[str, ...]     # ferramentas recusadas pela governança
    recusas_do_agente: int       # USAR sem ler a ficha antes (o motor barra e registra)
    ferramentas_certas: bool
    resposta_certa: bool

    @property
    def aprovado(self):
        return self.tipo == "final" and self.ferramentas_certas and self.resposta_certa


class Medidor:
    """Embrulha o `chamar_modelo` para contar chamadas e somar o tempo gasto no modelo.

    Repassa `tempo_limite` só se o modelo de dentro declara esse parâmetro, como o motor faz."""

    def __init__(self, chamar_modelo):
        self._chamar_modelo = chamar_modelo
        self._repassa_tempo = "tempo_limite" in inspect.signature(chamar_modelo).parameters
        self.chamadas = 0
        self.segundos = 0.0

    def __call__(self, prompt_sistema, prompt, tempo_limite=None):
        inicio = time.monotonic()
        try:
            opcoes = {"tempo_limite": tempo_limite} if self._repassa_tempo else {}
            return self._chamar_modelo(prompt_sistema, prompt, **opcoes)
        finally:
            self.chamadas += 1
            self.segundos += time.monotonic() - inicio


def _registros_do_pedido(execucao_id):
    with governanca.TRAVA_DOS_REGISTROS:
        return [r for r in governanca.REGISTROS if r["execucao_id"] == execucao_id]


def avaliar_cenario(
    cenario: Cenario,
    chamar_modelo: Callable[..., str],
    buscar_usuario: Callable[[str], object],
    ferramentas_do_agente: Sequence[str] = motor.FERRAMENTAS_DO_AGENTE,
) -> Resultado:
    usuario = buscar_usuario(cenario.funcionario)
    if usuario is None:
        raise ValueError(f"Funcionário {cenario.funcionario} não encontrado no diretório.")
    execucao_id = uuid.uuid4().hex
    medidor = Medidor(chamar_modelo)
    inicio = time.monotonic()
    turno = motor.rodar_turno(
        cenario.pergunta, usuario, ferramentas_do_agente, medidor,
        contexto={"execucao_id": execucao_id},
    )
    segundos_total = time.monotonic() - inicio

    registros = _registros_do_pedido(execucao_id)
    do_agente = [r for r in registros if r["camada_bloqueio"] == "agente"]
    do_catalogo = [r for r in registros if r["camada_bloqueio"] != "agente"]
    executadas = tuple(r["ferramenta"] for r in do_catalogo if r["status"] == "ok")
    negadas = tuple(r["ferramenta"] for r in do_catalogo if r["tipo_erro"] == "permissao_negada")
    return Resultado(
        cenario=cenario.nome,
        tipo=turno.tipo,
        motivo=turno.motivo,
        passos=len(turno.trajetoria),
        chamadas_ao_modelo=medidor.chamadas,
        segundos_no_modelo=round(medidor.segundos, 3),
        segundos_total=round(segundos_total, 3),
        executadas=executadas,
        negadas=negadas,
        recusas_do_agente=len(do_agente),
        ferramentas_certas=(
            set(executadas) == set(cenario.esperadas) and set(negadas) == set(cenario.negadas)
        ),
        resposta_certa=turno.tipo == "final"
        and all(re.search(p, turno.resposta) for p in cenario.padroes),
    )


def avaliar(
    chamar_modelo, buscar_usuario, cenarios: Sequence[Cenario] = CENARIOS,
    ferramentas_do_agente: Sequence[str] = motor.FERRAMENTAS_DO_AGENTE,
) -> list[Resultado]:
    return [
        avaliar_cenario(c, chamar_modelo, buscar_usuario, ferramentas_do_agente) for c in cenarios
    ]


def resumir(resultados: Sequence[Resultado]) -> str:
    """Texto para o terminal: uma linha por cenário e os totais."""
    linhas = [
        f"{'cenário':<30} {'ok':<4} {'ferram.':<8} {'resp.':<6} {'passos':>6} {'modelo':>6} {'s':>7}"
    ]
    for r in resultados:
        linhas.append(
            f"{r.cenario:<30} {'sim' if r.aprovado else 'NÃO':<4} "
            f"{'sim' if r.ferramentas_certas else 'NÃO':<8} {'sim' if r.resposta_certa else 'NÃO':<6} "
            f"{r.passos:>6} {r.chamadas_ao_modelo:>6} {r.segundos_total:>7.1f}"
        )
        if r.tipo != "final":
            linhas.append(f"    terminou em {r.tipo} ({r.motivo})")
    if resultados:
        aprovados = sum(r.aprovado for r in resultados)
        por_chamada = [r.segundos_no_modelo / r.chamadas_ao_modelo for r in resultados if r.chamadas_ao_modelo]
        linhas.append(f"aprovados: {aprovados} de {len(resultados)}")
        if por_chamada:
            linhas.append(
                f"tempo por chamada ao modelo: média {statistics.mean(por_chamada):.1f} s, "
                f"máxima {max(por_chamada):.1f} s"
            )
    return "\n".join(linhas)


def para_json(resultados: Sequence[Resultado]) -> str:
    """Só números e nomes (sem pergunta, resposta ou dado de lojista)."""
    return json.dumps([asdict(r) for r in resultados], ensure_ascii=False, indent=2)


def principal(argumentos=None):
    """`python -m agentes.avaliacao`: roda os cenários com o modelo direto, como no terminal."""
    analisador = argparse.ArgumentParser(description="Mede o uso de ferramentas pelo agente.")
    analisador.add_argument("--cenario", action="append", choices=[c.nome for c in CENARIOS])
    analisador.add_argument("--salvar", help="grava os números em um arquivo JSON")
    escolhas = analisador.parse_args(argumentos)

    from agentes import (
        terminal,  # lazy: carrega o .env e exige o modelo só quando se roda de verdade
    )

    if not terminal.LLM_URL:
        raise SystemExit("Defina LLM_URL no .env para avaliar com o modelo real.")
    cenarios = [c for c in CENARIOS if not escolhas.cenario or c.nome in escolhas.cenario]
    resultados = avaliar(
        terminal.chamar_llm, terminal.buscar_usuario_no_diretorio, cenarios
    )
    print(resumir(resultados))
    if escolhas.salvar:
        with open(escolhas.salvar, "w", encoding="utf-8") as arquivo:
            arquivo.write(para_json(resultados))


if __name__ == "__main__":
    principal()
