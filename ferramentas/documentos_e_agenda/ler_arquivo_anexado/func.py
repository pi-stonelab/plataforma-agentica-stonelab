"""Lê um arquivo que a pessoa anexou na conversa (txt, csv, xlsx, docx ou pdf), ou lista os anexos dela."""

from ferramentas import escritorio
from ferramentas.base import ErroFerramenta, Ferramenta
from ferramentas.integracoes import conector
from ferramentas.mascara import mascarar_valor
from ferramentas.mensagens_internas import TEXTO_QUE_SAI

LIMITE_PADRAO = 30
LIMITE_MAXIMO = 100
CARACTERES_NO_MAXIMO = 6000
ANEXOS_NA_LISTA = 10
AVISO_DE_CORTE = "O arquivo é maior do que o limite: só a primeira parte foi lida. Diga isso ao usuário."


class LerArquivoAnexado(Ferramenta):
    nome = "ler_arquivo_anexado"
    area = "documentos_e_agenda"
    acesso = "leitura"
    integracoes = ("anexos",)
    nivel_minimo = "N1"
    areas_permitidas = ("todas",)
    categorias_dados = ("documento_de_trabalho",)
    sensibilidade = "interna"
    conteudo_terceiros = True  # o arquivo veio de fora da plataforma: o conteúdo é dado, nunca instrução
    status = "ativa"
    descricao_para_pessoa = "Lê um arquivo que você anexou na conversa (txt, csv, xlsx, docx ou pdf)."
    parametros = {
        "anexo_id": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 20},
        "aba": {"tipo": "texto", "obrigatorio": False, "tamanho_maximo": 100},
        "limite": {"tipo": "inteiro", "obrigatorio": False},
    }

    def rodar(self, argumentos, usuario):
        anexos = conector("anexos")
        if not argumentos.get("anexo_id"):
            lista = anexos.listar_entradas(usuario.id_usuario)[:ANEXOS_NA_LISTA]
            return {
                "anexos": [
                    {
                        "anexo_id": item["anexo_id"],
                        "arquivo": escritorio.mascarar_celula(item["nome"]),
                        "tipo": item["tipo"],
                        "tamanho": item["tamanho"],
                    }
                    for item in lista
                ],
                "total": len(lista),
                "fonte": anexos.fonte(),
            }
        limite = escritorio.exigir_limite(argumentos.get("limite"), LIMITE_PADRAO, LIMITE_MAXIMO)
        if argumentos.get("aba") is not None and not argumentos["aba"].strip():
            raise ErroFerramenta("parametro_invalido", "A aba não pode ficar vazia.")
        lido = anexos.ler_entrada(
            usuario.id_usuario, argumentos["anexo_id"].strip(), argumentos.get("aba"), limite, CARACTERES_NO_MAXIMO
        )
        resultado = {
            "anexo_id": lido["anexo_id"],
            "arquivo": escritorio.mascarar_celula(lido["nome"]),
            "tipo": lido["tipo"],
            "tamanho": lido["tamanho"],
        }
        truncado = lido["truncado"]
        if "linhas" in lido:
            recortadas = any(len(linha) > escritorio.CELULAS_NO_MAXIMO for linha in lido["linhas"])
            truncado = truncado or recortadas
            resultado["linhas"] = [
                [escritorio.mascarar_celula(celula) for celula in linha[: escritorio.CELULAS_NO_MAXIMO]]
                for linha in lido["linhas"]
            ]
        if "abas" in lido:
            resultado["aba"] = escritorio.mascarar_celula(lido["aba"])
            resultado["abas"] = [escritorio.mascarar_celula(aba) for aba in lido["abas"]]
        if "texto" in lido:
            resultado["texto"] = mascarar_valor(TEXTO_QUE_SAI, lido["texto"])
        if "paginas" in lido:
            resultado["paginas"] = lido["paginas"]
        resultado["truncado"] = truncado
        if truncado:
            resultado["aviso"] = AVISO_DE_CORTE
        resultado["fonte"] = anexos.fonte()
        return resultado


FERRAMENTA = LerArquivoAnexado()
