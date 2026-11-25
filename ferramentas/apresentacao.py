"""Como a prévia fala com quem confirma: datas no padrão brasileiro, vírgula decimal e nomes no lugar de códigos.

Só texto para a pessoa. Regra de negócio e valor gravado nunca passam por aqui.
"""

from datetime import date, datetime
from decimal import Decimal

ROTULOS_DA_PRIORIDADE = {"baixa": "Baixa", "média": "Média", "alta": "Alta", "crítica": "Crítica"}
ROTULOS_DO_NIVEL = {"N1": "Atendimento N1", "N2": "Atendimento N2", "supervisor": "Supervisor de atendimento"}
ROTULOS_DA_ALCADA = {
    "analista": "Analista de cobrança",
    "coordenador": "Coordenador financeiro",
    "dupla_aprovacao": "Dupla aprovação (duas pessoas)",
}
ROTULOS_DO_CARGO = {
    "atendente_n1": "atendente N1",
    "especialista_n2": "especialista N2",
    "supervisor_atendimento": "supervisor de atendimento",
    "analista_ouvidoria": "analista de ouvidoria",
    "analista_cobranca": "analista de cobrança",
    "analista_disputas": "analista de disputas",
    "analista_recebiveis": "analista de recebíveis",
    "coordenador_financeiro": "coordenador financeiro",
    "auditor_compliance": "auditor de compliance",
    "admin_plataforma": "administrador da plataforma",
}


def data_br(valor):
    """"2026-10-16" (ou data) vira "16/10/2026". Texto que não é data volta como veio."""
    try:
        return (valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])).strftime("%d/%m/%Y")
    except ValueError:
        return valor


def data_e_hora_br(valor):
    """"2026-10-16T01:00:00" vira "16/10/2026 às 01:00" (o "às" evita que a máscara de texto leia a data e a hora como
    um número só). Texto que não é data e hora volta como veio."""
    try:
        return (valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor))).strftime("%d/%m/%Y às %H:%M")
    except ValueError:
        return valor


def decimal_br(valor):
    """2.99 vira "2,99"."""
    return str(Decimal(str(valor)).normalize() if valor == int(valor) else valor).replace(".", ",")


def cargo_de(id_funcionario, buscar_funcionario):
    """O cargo por extenso de quem pediu ("analista de cobrança"), no lugar do id. `buscar_funcionario` é a leitura do
    diretório (`dados_sinteticos.buscar_funcionario`). Sem cadastro, "outra pessoa": o id nunca vai para o cartão."""
    funcionario = buscar_funcionario(id_funcionario) if id_funcionario else None
    return ROTULOS_DO_CARGO.get((funcionario or {}).get("cargo"), "outra pessoa")
