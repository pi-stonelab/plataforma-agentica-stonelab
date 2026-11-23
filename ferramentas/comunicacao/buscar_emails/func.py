"""Mensagens que um lojista mandou para a caixa de e-mail da plataforma (IMAP), num período."""

import os
from datetime import timedelta

from ferramentas import dados_sinteticos, lojista
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.email_smtp import endereco_valido
from ferramentas.integracoes.email_leitura.conector import CONECTOR as EMAIL_LEITURA

LIMITE_PADRAO = 5
LIMITE_MAXIMO = 10
DIAS_PADRAO = 30
DIAS_NO_MAXIMO = 180  # o período de uma busca (a caixa é lida pela rede, mensagem por mensagem)


def _enderecos_do_lojista(codigo):
    """Os e-mails dos contatos do cadastro. Na demo (`EMAIL_DESTINO_TESTE`), o envio foi todo para o endereço de
    teste, então a resposta do "lojista" chega de lá: ele entra na busca."""
    contatos, _ = dados_sinteticos.buscar_contatos(codigo)
    enderecos = [c["email"] for c in contatos if c.get("email") and endereco_valido(c["email"])]
    teste = os.environ.get("EMAIL_DESTINO_TESTE", "").strip()
    if teste and endereco_valido(teste):
        enderecos.append(teste)
    return list(dict.fromkeys(enderecos))


def _periodo(argumentos):
    hoje = EMAIL_LEITURA.hoje()
    data_fim = argumentos.get("data_fim") or hoje
    data_inicio = argumentos.get("data_inicio") or data_fim - timedelta(days=DIAS_PADRAO)
    lojista.conferir_ordem_das_datas(data_inicio, data_fim)
    if (data_fim - data_inicio).days > DIAS_NO_MAXIMO:
        raise ErroFerramenta("parametro_invalido", f"O período pode ter até {DIAS_NO_MAXIMO} dias.")
    return data_inicio, data_fim


def _para_o_agente(mensagem):
    """Assunto e trecho viram um campo `texto` só: é texto do lojista, e a máscara o trata como texto livre."""
    return {
        "email": mensagem["email"],
        "data_hora": mensagem["data_hora"],
        "texto": f"Assunto: {mensagem['assunto']}\n{mensagem['trecho']}",
    }


class BuscarEmails(Ferramenta):
    nome = "buscar_emails"
    area = "comunicacao"
    acesso = "leitura"
    integracoes = ("email_leitura",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("contato", "interacao")
    sensibilidade = "pessoal"
    conteudo_terceiros = True
    status = "ativa"
    descricao_para_pessoa = "Mostra os e-mails que um lojista mandou para a caixa da plataforma num período."
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "assunto": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 120},
        "data_inicio": {"tipo": "data", "obrigatorio": False},
        "data_fim": {"tipo": "data", "obrigatorio": False},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        codigo = argumentos["id_cliente"]
        limite = argumentos.get("limite", LIMITE_PADRAO)
        if not 1 <= limite <= LIMITE_MAXIMO:
            raise ErroFerramenta("parametro_invalido", f"O limite deve ficar entre 1 e {LIMITE_MAXIMO}.")
        data_inicio, data_fim = _periodo(argumentos)
        lojista.exigir_acesso(usuario, codigo)
        enderecos = _enderecos_do_lojista(codigo)
        if not enderecos and EMAIL_LEITURA.modo() != "simulado":
            raise ErroFerramenta("nao_encontrado", "O lojista não tem e-mail cadastrado.")
        mensagens, total, fonte = EMAIL_LEITURA.mensagens(
            codigo, enderecos, data_inicio, data_fim, argumentos.get("assunto"), limite
        )
        return {
            "id_cliente": codigo,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": data_fim.isoformat(),
            "mensagens": [_para_o_agente(mensagem) for mensagem in mensagens],
            "total": total,
            "fonte": fonte,
        }


FERRAMENTA = BuscarEmails()
