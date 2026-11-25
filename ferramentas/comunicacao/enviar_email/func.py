"""Prepara um e-mail a um contato do lojista; envia por SMTP só quando quem pediu confirma (duas fases)."""

from ferramentas import dados_sinteticos, email_smtp, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.integracoes.email.conector import CONECTOR as EMAIL
from ferramentas.mascara import mascarar_valor

# Sem `papel_contato`: o financeiro e, se o lojista não tiver, o sócio.
PAPEIS_SEM_ESCOLHA = ("financeiro", "socio")
TAMANHO_ASSUNTO = 120
TAMANHO_CORPO = 2000
LIVRE = "texto_livre"


class EnviarEmail(FerramentaComConfirmacao):
    nome = "enviar_email"
    area = "comunicacao"
    integracoes = ("email",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("contato",)
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "assunto", "corpo", "id_mensagem")
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
    titulo = "Enviar e-mail"
    descricao_para_pessoa = "Prepara um e-mail para um contato do lojista; ele só sai depois que você confirma."
    rotulos_da_previa = {"para": "Para", "assunto": "Assunto", "corpo": "Mensagem"}
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "assunto": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_ASSUNTO},
        "corpo": {"tipo": "texto", "obrigatorio": True, "tamanho_maximo": TAMANHO_CORPO},
        "papel_contato": {"tipo": "texto", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        email_smtp.exigir_configuracao()  # sem envio configurado, nem a prévia: ela nunca poderia sair
        codigo, papel = argumentos["id_cliente"], argumentos.get("papel_contato")
        assunto = mascarar_valor(LIVRE, argumentos["assunto"])  # vai o que a pessoa revisou
        corpo = mascarar_valor(LIVRE, argumentos["corpo"])
        if not assunto or not corpo:
            raise ErroFerramenta("parametro_invalido", "Assunto e corpo não podem ficar vazios.")
        if not email_smtp.assunto_valido(assunto):  # a mesma regra do envio: quebra de linha injeta cabeçalho
            raise ErroFerramenta("parametro_invalido", email_smtp.MENSAGEM_ASSUNTO_INVALIDO)
        if not email_smtp.corpo_valido(corpo):
            raise ErroFerramenta("parametro_invalido", email_smtp.MENSAGEM_CORPO_INVALIDO)
        if papel is not None and papel not in dados_sinteticos.PAPEIS_CONTATO:
            raise ErroFerramenta("parametro_invalido", "Papel de contato desconhecido.")
        lojista.exigir_acesso(usuario, codigo)
        papeis = (papel,) if papel else PAPEIS_SEM_ESCOLHA
        contato = dados_sinteticos.contato_para_email(codigo, papeis)
        if contato is None:
            raise ErroFerramenta("nao_encontrado", "O lojista não tem contato com esse papel.")
        para = {"codigo": codigo, "papel": contato["papel"], "email": contato["email"]}
        conteudo = {**para, "assunto": assunto, "corpo": corpo}
        previa = {"para": para, "assunto": assunto, "corpo": corpo}
        return conteudo, previa

    def texto_do_campo(self, campo, valor):
        if campo == "para" and isinstance(valor, dict):
            return f"{valor.get('email')} ({valor.get('papel')} do {valor.get('codigo')})"
        return super().texto_do_campo(campo, valor)

    def efetivar(self, conteudo, usuario):
        # A carteira pode ter mudado desde a prévia: confere de novo antes de enviar.
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        config = email_smtp.exigir_configuracao()
        funcionario = dados_sinteticos.contato_do_funcionario(usuario.id_usuario)  # o lojista responde a ele
        id_mensagem = EMAIL.chamar(  # o disjuntor e a saúde da integração contam este envio
            "enviar",
            lambda: email_smtp.enviar(conteudo["email"], conteudo["assunto"], conteudo["corpo"], config, funcionario),
        )
        para = {"codigo": conteudo["codigo"], "papel": conteudo["papel"]}
        return {"id_mensagem": id_mensagem, "para": para}


FERRAMENTA = EnviarEmail()
