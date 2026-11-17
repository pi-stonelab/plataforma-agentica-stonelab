"""Prepara um e-mail a um contato do lojista; envia por SMTP só quando quem pediu confirma (duas fases)."""

from ferramentas import dados_sinteticos, email_smtp, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao
from ferramentas.mascara import mascarar_valor

# Sem `papel_contato`: o financeiro e, se o lojista não tiver, o sócio.
PAPEIS_SEM_ESCOLHA = ("financeiro", "socio")
TAMANHO_ASSUNTO = 120
TAMANHO_CORPO = 2000
LIVRE = "texto_livre"
ESPACO = 32  # abaixo disso são caracteres de controle, como a quebra de linha


class EnviarEmail(FerramentaComConfirmacao):
    nome = "enviar_email"
    area = "comunicacao"
    integracoes = ("google_workspace", "microsoft_365")  # o envio de hoje é por SMTP (email_smtp)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento", "financeiro")
    categorias_dados = ("contato",)
    campos_liberados = (*FerramentaComConfirmacao.campos_liberados, "assunto", "corpo", "id_mensagem")
    sensibilidade = "pessoal"
    conteudo_terceiros = False
    status = "ativa"
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
        if any(ord(caractere) < ESPACO for caractere in assunto):  # quebra de linha no assunto injeta cabeçalho
            raise ErroFerramenta("parametro_invalido", "O assunto deve ter uma linha só.")
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

    def efetivar(self, conteudo, usuario):
        # A carteira pode ter mudado desde a prévia: confere de novo antes de enviar.
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        config = email_smtp.exigir_configuracao()
        funcionario = dados_sinteticos.contato_do_funcionario(usuario.id_usuario)  # o lojista responde a ele
        id_mensagem = email_smtp.enviar(
            conteudo["email"], conteudo["assunto"], conteudo["corpo"], config, funcionario
        )
        para = {"codigo": conteudo["codigo"], "papel": conteudo["papel"]}
        return {"id_mensagem": id_mensagem, "para": para}


FERRAMENTA = EnviarEmail()
