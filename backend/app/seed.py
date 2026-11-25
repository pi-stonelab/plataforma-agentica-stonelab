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


def senha_padrao() -> str | None:
    """`SEED_SENHA_DEMO`, lida pelo `Configuracao` (do ambiente ou do .env da raiz), ou None."""
    from app.config import configuracao

    segredo = configuracao.seed_senha_demo
    return segredo.get_secret_value() if segredo is not None else None


def main(argv: list[str] | None = None) -> None:
    from app.db import SessaoLocal, criar_tabelas

    parser = argparse.ArgumentParser(description="Cria as contas da demo.")
    parser.add_argument(
        "--senha",
        default=senha_padrao(),
        help="Senha de todas as contas da demo (padrão: SEED_SENHA_DEMO do .env).",
    )
    argumentos = parser.parse_args(argv)
    if not argumentos.senha:
        parser.error("informe --senha ou preencha SEED_SENHA_DEMO no .env.")

    criar_tabelas()
    with SessaoLocal() as sessao:
        criadas = semear(sessao, argumentos.senha)
        total = sessao.query(models.Usuario).count()
    print(f"Contas criadas: {len(criadas)} (total no banco: {total}).")


if __name__ == "__main__":
    main()
