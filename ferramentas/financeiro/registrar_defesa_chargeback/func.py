"""Prepara o registro dos documentos de defesa de um chargeback; grava só quando quem pediu confirma.

O lojista manda os documentos, a pessoa de Disputas os confere e registra aqui. Com todos os documentos que o
motivo pede, o caso segue para a análise (DOC-MOCK §7.6); com menos, continua aguardando a defesa até o prazo.
"""

import re
import unicodedata

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.apresentacao import data_br
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

PADRAO_CHARGEBACK = re.compile(r"CB\d{5}")
LIMITE_DE_CHARGEBACKS = 50
DOCUMENTOS_NO_MAXIMO = 8


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower().strip()


def _documentos_pedidos(texto):
    """"nota fiscal, comprovante_entrega" -> ("nota_fiscal", "comprovante_entrega"): aceita o código ou o rótulo que a
    consulta de contestações mostra (inteiro ou sem o que vem entre parênteses). Nome que não é de documento nenhum: `parametro_invalido`."""
    por_nome = {}
    for codigo, rotulo in dados_sinteticos.ROTULOS_DOS_DOCUMENTOS.items():
        por_nome[_sem_acento(codigo)] = codigo
        por_nome[_sem_acento(rotulo)] = codigo
        por_nome[_sem_acento(rotulo.split("(")[0])] = codigo  # "comprovante de entrega (rastreio ...)" também por "comprovante de entrega"
    pedidos = [parte for parte in (p.strip() for p in texto.split(",")) if parte]
    if not pedidos or len(pedidos) > DOCUMENTOS_NO_MAXIMO:
        raise ErroFerramenta("parametro_invalido", f"Informe de 1 a {DOCUMENTOS_NO_MAXIMO} documentos, separados por vírgula.")
    achados = []
    for pedido in pedidos:
        codigo = por_nome.get(_sem_acento(pedido))
        if codigo is None:
            raise ErroFerramenta(
                "parametro_invalido", "Documento desconhecido. Use os documentos que a consulta de contestações lista."
            )
        achados.append(codigo)
    return tuple(dict.fromkeys(achados))


def _rotulos(codigos):
    return [dados_sinteticos.ROTULOS_DOS_DOCUMENTOS[c] for c in codigos]


class RegistrarDefesaChargeback(FerramentaComConfirmacao):
    nome = "registrar_defesa_chargeback"
    area = "financeiro"
    integracoes = ("sql",)
    nivel_minimo = "N1"
    areas_permitidas = ("financeiro",)
    categorias_dados = ("cadastral", "disputa")
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "documentos_a_registrar", "documentos_ja_registrados",
        "documentos_que_faltam", "o_que_acontece",
    )
    sensibilidade = "sigilosa"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "nos chargebacks do lojista"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Registrar defesa do chargeback"
    mensagem_feito = "Defesa registrada."
    descricao_para_pessoa = (
        "Prepara o registro dos documentos de defesa de um chargeback, antes do fim do prazo; nada é gravado antes da "
        "sua confirmação."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_chargeback": "Chargeback",
        "motivo": "Motivo",
        "prazo_defesa": "Prazo da defesa",
        "documentos_a_registrar": "Documentos a registrar",
        "documentos_ja_registrados": "Já registrados",
        "documentos_que_faltam": "Ainda faltam",
        "o_que_acontece": "O que acontece",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chargeback": {"tipo": "texto", "obrigatorio": True},
        "documentos": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": 400},
    }

    def montar(self, argumentos, usuario):
        codigo, id_chargeback = argumentos["id_cliente"], argumentos["id_chargeback"].upper()
        if not PADRAO_CHARGEBACK.fullmatch(id_chargeback):
            raise ErroFerramenta("parametro_invalido", "O id_chargeback deve ser como CB00001.")
        documentos = _documentos_pedidos(argumentos["documentos"])
        lojista.exigir_acesso(usuario, codigo)
        chargebacks, _ = dados_sinteticos.buscar_chargebacks(codigo, LIMITE_DE_CHARGEBACKS)
        caso = next((c for c in chargebacks if c["codigo"] == id_chargeback), None)
        if caso is None:
            raise ErroFerramenta("nao_encontrado", "Chargeback não encontrado para este lojista.")
        conteudo = {"codigo": codigo, "id_chargeback": id_chargeback, "documentos": documentos}
        ensaio = escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # prazo, situação e documentos, já conferidos
        faltam = ensaio["documentos_que_faltam"]
        previa = {
            "id_cliente": codigo,
            "id_chargeback": id_chargeback,
            "motivo": caso["motivo"],
            "prazo_defesa": data_br(caso["prazo_defesa"]),
            "documentos_a_registrar": _rotulos(ensaio["documentos_registrados"]),
            "documentos_ja_registrados": caso["documentos_enviados"] or ["nenhum"],
            "documentos_que_faltam": _rotulos(faltam) or ["nenhum"],
            "o_que_acontece": (
                "A defesa fica completa e o caso segue para a análise" if not faltam
                else "A defesa continua incompleta: o chargeback segue aguardando a defesa até o prazo"
            ),
        }
        return conteudo, previa

    def mensagem_ao_confirmar(self, dados):
        if dados["situacao"] == "em_analise":
            return f"Defesa do chargeback {dados['codigo']} completa: o caso segue para a análise."
        return f"Documentos registrados no chargeback {dados['codigo']}. A defesa ainda está incompleta."

    def referencia_do_resultado(self, dados):
        return dados["codigo"]  # id neutro do chargeback: liga a defesa a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        return escritas_sinteticas.registrar_defesa_chargeback(
            conteudo["codigo"], conteudo["id_chargeback"], conteudo["documentos"], usuario.id_usuario
        )


FERRAMENTA = RegistrarDefesaChargeback()
