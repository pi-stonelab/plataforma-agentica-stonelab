"""Quem é o funcionário que usa a plataforma, lido do diretório do mock.

Ponto único para montar o `Usuario` a partir de um ID já validado (pelo login no back-end ou pelo
`ID_USUARIO` do modo terminal). Quem monta o usuário por outro caminho pula a checagem de situação.
"""

from . import dados_sinteticos, governanca

SITUACAO_ATIVA = "ativo"  # DOC-MOCK §8.4: desligado e afastado não usam a plataforma


def buscar_usuario(id_usuario):
    """O `governanca.Usuario` do funcionário ativo, ou None.

    Nível, área e carteiras vêm do cargo e do time do diretório. Devolve None se o ID não existe ou
    se a situação não é exatamente `ativo` (desligado, afastado ou qualquer outra): negar por padrão.
    Diretório fora do ar levanta ConnectionError, para não virar "funcionário não encontrado".
    """
    funcionario = dados_sinteticos.buscar_funcionario(id_usuario)
    if funcionario is None or funcionario["situacao"] != SITUACAO_ATIVA:
        return None
    return governanca.usuario_do_cargo(funcionario["id"], funcionario["cargo"], tuple(funcionario["carteiras"]))
