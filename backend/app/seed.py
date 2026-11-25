"""Cria as contas da demo a partir dos funcionários do diretório do mock (decisão de 25/11, opção 1).

Cada conta aponta para um funcionário (`id_funcionario`); o perfil sai do cargo
(`PERFIL_DO_CARGO`). Nome e e-mail são os do mock (sintéticos, domínio `.example`). Cargo, carteira e
situação continuam só no mock. O GestorDeAcessos não tem cargo no mock (SEM FONTE) e entra como
conta à parte, sem funcionário e sem ferramentas.

Rodar (de dentro de backend/, com o banco do mock já criado por `python -m mock.gerar`):

    python -m app.seed --senha <senha da demo>

Roda de novo sem duplicar: conta que já existe não é alterada.
"""

import argparse
import os

from ferramentas import dados_sinteticos
from sqlalchemy.orm import Session

from app import models
from app.auth import gerar_hash, normalizar_email
from app.permissoes import PERFIL_DO_CARGO

# Todos os funcionários do mock (mock/gerar.py, FUNCIONARIOS): um por cargo, mais os casos
# negativos F0014 (desligado) e F0015 (afastada), que existem para a demo mostrar o login negado.
FUNCIONARIOS_DA_DEMO = tuple(f"F{numero:04d}" for numero in range(1, 16))

GESTOR_DE_ACESSOS = {
    "id": "G0001",
    "nome": "Gestão de Acessos",
    "email": "gestao.acessos@stonesim.example",
    "perfil": "GestorDeAcessos",
    "area": "atendimento",
}


def contas_da_demo() -> list[dict]:
    """As contas a criar, lidas do diretório do mock (sem senha)."""
    contas = []
    for id_funcionario in FUNCIONARIOS_DA_DEMO:
        funcionario = dados_sinteticos.buscar_funcionario(id_funcionario)
        contato = dados_sinteticos.contato_do_funcionario(id_funcionario)
        if funcionario is None or contato is None:
            raise RuntimeError(f"{id_funcionario} não está no diretório do mock. Rode python -m mock.gerar.")
        contas.append(
            {
                "id": id_funcionario,
                "id_funcionario": id_funcionario,
                "nome": contato["nome"],
                "email": contato["email"],
                "perfil": PERFIL_DO_CARGO[funcionario["cargo"]].__name__,
                "area": None,  # vem do cargo, a cada pedido
            }
        )
    contas.append({**GESTOR_DE_ACESSOS, "id_funcionario": None})
    return contas


def semear(sessao: Session, senha: str) -> list[str]:
    """Cria as contas que faltam e devolve os ids criados."""
    senha_hash = gerar_hash(senha)
    criadas = []
    for conta in contas_da_demo():
        if sessao.get(models.Usuario, conta["id"]) is not None:
            continue
        sessao.add(
            models.Usuario(
                **{**conta, "email": normalizar_email(conta["email"])},
                senha_hash=senha_hash,
                areas_extras=[],
            )
        )
        criadas.append(conta["id"])
    sessao.commit()
    return criadas


# Agentes da demo, com os nomes atuais do catálogo (PR 25). As escritas (abrir_chamado, adicionar_nota_chamado)
# são em duas fases: o agente monta a prévia e a pessoa confirma no cartão do chat. O enviar_email fica de fora
# porque depende de SMTP configurado no .env.
AGENTES_DA_DEMO = (
    {
        "id": "ag-geral",
        "nome": "Assistente Geral",
        "objetivo": "Responde dúvidas usando as ferramentas que o seu cargo libera.",
        "area": None,
        "dono_id": "plataforma",  # seguranca.DONO_PLATAFORMA: ferramentas = catálogo inteiro
        "visibilidade": "publico",
        "ferramentas": [],
        "ativo": True,
        "convidados": [],
    },
    {
        "id": "ag-atendimento",
        "nome": "Assistente de Atendimento",
        "objetivo": "Tira dúvidas sobre lojistas, transações, liquidações, chamados, multas e endereços.",
        "area": "atendimento",
        "dono_id": "F0006",
        "visibilidade": "publico",
        "ferramentas": [
            "consultar_cliente",
            "consultar_transacoes_cliente",
            "calcular_multa_atraso",
            "consultar_endereco_cep",
            "consultar_liquidacoes_cliente",
            "listar_chamados_cliente",
            "consultar_historico_contato",
            "consultar_contatos_lojista",
            "abrir_chamado",
            "adicionar_nota_chamado",
            "solicitar_ferramenta_ausente",
        ],
        "ativo": True,
        "convidados": [],
    },
    {
        "id": "ag-cobranca",
        "nome": "Cobrança e Multas",
        "objetivo": "Calcula multa, juros e parcelamento de faturas em atraso e consulta o histórico do lojista.",
        "area": "financeiro",
        "dono_id": "F0008",
        "visibilidade": "convidados",
        "ferramentas": [
            "consultar_cliente",
            "consultar_transacoes_cliente",
            "listar_faturas_em_atraso",
            "calcular_multa_atraso",
            "calcular_parcelas",
            "solicitar_ferramenta_ausente",
        ],
        "ativo": True,
        "convidados": ["F0009"],
    },
    {
        "id": "ag-chamados",
        "nome": "Resumo de Chamados",
        "objetivo": "Resume os chamados abertos e o histórico de contato de um lojista antes do atendimento.",
        "area": "atendimento",
        "dono_id": "F0001",
        "visibilidade": "privado",
        "ferramentas": [
            "consultar_cliente",
            "listar_chamados_cliente",
            "consultar_historico_contato",
            "solicitar_ferramenta_ausente",
        ],
        "ativo": True,
        "convidados": [],
    },
    {
        "id": "ag-conciliacao",
        "nome": "Conciliação de Liquidações (v1)",
        "objetivo": "Versão antiga da conferência de liquidações. Desativada.",
        "area": "financeiro",
        "dono_id": "F0011",
        "visibilidade": "publico",
        "ferramentas": ["consultar_liquidacoes_cliente"],
        "ativo": False,
        "convidados": [],
    },
)


def semear_agentes(sessao: Session) -> list[str]:
    """Cria os agentes da demo que faltam (depois das contas: dono e convidados são contas)."""
    criados = []
    for dados in AGENTES_DA_DEMO:
        if sessao.get(models.Agente, dados["id"]) is not None:
            continue
        convidados = dados["convidados"]
        sessao.add(models.Agente(**{k: v for k, v in dados.items() if k != "convidados"}))
        sessao.flush()
        for usuario_id in convidados:
            sessao.add(models.AgenteConvidado(agente_id=dados["id"], usuario_id=usuario_id))
        criados.append(dados["id"])
    sessao.commit()
    return criados


def main() -> None:
    from app.db import SessaoLocal, criar_tabelas

    parser = argparse.ArgumentParser(description="Cria as contas da demo.")
    parser.add_argument(
        "--senha",
        default=os.environ.get("SEED_SENHA_DEMO"),
        help="Senha de todas as contas da demo (ou SEED_SENHA_DEMO no ambiente).",
    )
    argumentos = parser.parse_args()
    if not argumentos.senha:
        parser.error("informe --senha (ou SEED_SENHA_DEMO).")

    criar_tabelas()
    with SessaoLocal() as sessao:
        criadas = semear(sessao, argumentos.senha)
        agentes = semear_agentes(sessao)
        total = sessao.query(models.Usuario).count()
    print(f"Contas criadas: {len(criadas)} (total no banco: {total}). Agentes criados: {len(agentes)}.")


if __name__ == "__main__":
    main()
