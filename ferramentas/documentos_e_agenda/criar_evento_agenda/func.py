"""Prepara um evento na agenda da conta (Google ou Outlook) de quem pede; cria só quando ele confirma."""

import re
import uuid
from datetime import datetime, time, timedelta

from ferramentas import email_smtp
from ferramentas.base import ErroFerramenta
from ferramentas.escritorio import (
    PARAMETRO_SERVICO,
    EscritaDeEscritorio,
    conector_da_pessoa,
    exigir_uma_linha,
)
from ferramentas.integracoes import conector
from ferramentas.integracoes.conector import DestinoNaoPermitido
from ferramentas.mensagens_internas import assinado, texto_mascarado

PADRAO_HORA = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")
SEPARADOR_DE_CONVIDADOS = re.compile(r"[,;]")
DURACAO_PADRAO = 30
DURACAO_MINIMA = 5
DURACAO_MAXIMA = 480
CONVIDADOS_NO_MAXIMO = 5
DIAS_A_FRENTE_NO_MAXIMO = 365
TAMANHO_DO_TITULO = 120
TAMANHO_DA_DESCRICAO = 500
TAMANHO_DO_LOCAL = 100


def _inicio(argumentos, hoje):
    """Data e hora de começo (horário de Brasília, sem fuso). No passado ou longe demais: `parametro_invalido`."""
    achado = PADRAO_HORA.fullmatch(argumentos["hora_inicio"])
    if achado is None:
        raise ErroFerramenta("parametro_invalido", "O parâmetro hora_inicio deve ter o formato HH:MM, como 14:30.")
    data = argumentos["data"]
    if data < hoje or data > hoje + timedelta(days=DIAS_A_FRENTE_NO_MAXIMO):
        raise ErroFerramenta("parametro_invalido", "A data deve ser de hoje até um ano à frente.")
    return datetime.combine(data, time(int(achado.group(1)), int(achado.group(2))))


def _convidados(conta, texto):
    """Os e-mails em minúsculas, sem repetição, todos de domínio permitido. Senão, `parametro_invalido`."""
    enderecos = [item.strip().lower() for item in SEPARADOR_DE_CONVIDADOS.split(texto or "") if item.strip()]
    enderecos = list(dict.fromkeys(enderecos))
    if len(enderecos) > CONVIDADOS_NO_MAXIMO:
        raise ErroFerramenta("parametro_invalido", f"Convide até {CONVIDADOS_NO_MAXIMO} pessoas.")
    for endereco in enderecos:
        if not email_smtp.endereco_valido(endereco):
            raise ErroFerramenta("parametro_invalido", "Um dos convidados não é um e-mail válido.")
        try:
            conta.exigir_convidado(endereco)
        except DestinoNaoPermitido:
            dominios = ", ".join(conta.dominios_permitidos()) or "nenhum"
            raise ErroFerramenta(
                "parametro_invalido", f"Só é possível convidar e-mails dos domínios liberados: {dominios}."
            ) from None
    return enderecos


class CriarEventoAgenda(EscritaDeEscritorio):
    nome = "criar_evento_agenda"
    area = "documentos_e_agenda"
    categorias_dados = ("agenda_pessoal",)
    campos_liberados = (*EscritaDeEscritorio.campos_liberados, "quando", "convidados", "titulo", "inicio", "fim", "local")
    status = "ativa"
    onde_conferir = "na agenda"
    titulo = "Criar evento na agenda"
    descricao_para_pessoa = "Prepara um evento na sua agenda (Google ou Microsoft); ele só é criado depois que você confirma."
    rotulos_da_previa = {
        "servico": "Conta", "titulo": "Evento", "quando": "Quando", "local": "Local", "convidados": "Convidados",
        "texto": "Descrição",
    }
    parametros = {
        "titulo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_DO_TITULO},
        "data": {"tipo": "data", "obrigatorio": True},
        "hora_inicio": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 5},
        "duracao_minutos": {"tipo": "inteiro", "obrigatorio": False},
        "convidados": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 400},
        "local": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": TAMANHO_DO_LOCAL},
        "descricao": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": TAMANHO_DA_DESCRICAO},
        "servico": PARAMETRO_SERVICO,
    }

    def montar(self, argumentos, usuario):
        conta = conector_da_pessoa(usuario, argumentos.get("servico"))
        titulo = exigir_uma_linha(argumentos["titulo"], "O título")
        inicio = _inicio(argumentos, conta.hoje())
        duracao = argumentos.get("duracao_minutos", DURACAO_PADRAO)
        if not DURACAO_MINIMA <= duracao <= DURACAO_MAXIMA:
            raise ErroFerramenta(
                "parametro_invalido", f"A duração deve ficar entre {DURACAO_MINIMA} e {DURACAO_MAXIMA} minutos."
            )
        fim = inicio + timedelta(minutes=duracao)
        local = exigir_uma_linha(argumentos["local"], "O local") if argumentos.get("local") else ""
        descricao = texto_mascarado(argumentos["descricao"], "A descrição") if argumentos.get("descricao") else ""
        convidados = _convidados(conta, argumentos.get("convidados"))
        # O convite chega a colegas: a descrição leva a assinatura de quem pediu, como as mensagens do Slack (E3).
        texto = assinado(descricao, usuario).strip()
        conteudo = {
            "servico": conta.nome, "titulo": titulo, "inicio": inicio, "fim": fim, "local": local,
            "descricao": texto, "convidados": convidados, "id_unico": uuid.uuid4().hex,
        }
        previa = {
            "servico": conta.rotulo,
            "titulo": titulo,
            "quando": f"{inicio:%d/%m/%Y} das {inicio:%H:%M} às {fim:%H:%M}",
            "local": local,
            "convidados": convidados,
            "texto": texto,
        }
        return conteudo, {campo: valor for campo, valor in previa.items() if valor not in ("", [])}

    def efetivar(self, conteudo, usuario):
        conta = conector(conteudo["servico"])
        try:
            evento = conta.criar_evento(usuario.id_usuario, conteudo)
        except DestinoNaoPermitido:  # o domínio saiu da lista do .env depois da prévia
            raise ErroFerramenta("parametro_invalido", "Um convidado não está mais liberado. Nada foi criado.") from None
        return {"titulo": evento["titulo"], "inicio": evento["inicio"], "fim": evento["fim"], "fonte": conta.fonte()}

    def mensagem_ao_confirmar(self, dados):
        frase = "Evento criado na agenda."
        return f"{frase} Modo de demonstração: nada saiu de verdade." if "simulado" in dados["fonte"] else frase


FERRAMENTA = CriarEventoAgenda()
