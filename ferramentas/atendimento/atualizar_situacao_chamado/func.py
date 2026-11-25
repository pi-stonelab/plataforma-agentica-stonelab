"""Prepara a mudança de situação, o encaminhamento ou a marca de suspeita de fraude de um chamado; grava só
quando quem pediu confirma (duas fases)."""

from ferramentas import dados_sinteticos, escritas_sinteticas, lojista
from ferramentas.base import ErroFerramenta
from ferramentas.confirmacoes import FerramentaComConfirmacao

ROTULOS_DA_SITUACAO = {
    "novo": "Novo",
    "em_atendimento": "Em atendimento",
    "aguardando_lojista": "Aguardando o lojista",
    "aguardando_area_interna": "Aguardando área interna",
    "resolvido": "Resolvido",
    "fechado": "Fechado",
}
DESTINOS = ("N2", "supervisor")
ROTULOS_DO_DESTINO = {"N2": "Atendimento N2", "supervisor": "Supervisor de atendimento"}


class AtualizarSituacaoChamado(FerramentaComConfirmacao):
    nome = "atualizar_situacao_chamado"
    area = "atendimento"
    integracoes = ("crm",)
    nivel_minimo = "N1"
    areas_permitidas = ("atendimento",)
    categorias_dados = ("chamado",)
    campos_liberados = (
        *FerramentaComConfirmacao.campos_liberados, "situacao_atual", "nova_situacao", "encaminhar_para", "suspeita_fraude", "nivel_atendimento",
    )
    sensibilidade = "interna"
    conteudo_terceiros = False
    status = "ativa"
    onde_conferir = "na situação do chamado"
    frase_de_nada_feito = "Nada foi gravado."
    titulo = "Atualizar chamado"
    mensagem_feito = "Chamado atualizado."
    descricao_para_pessoa = (
        "Prepara a mudança de situação de um chamado, o encaminhamento ao N2 ou ao supervisor, ou a marca de suspeita "
        "de fraude; nada muda antes da sua confirmação."
    )
    rotulos_da_previa = {
        "id_cliente": "Lojista",
        "id_chamado": "Chamado",
        "situacao_atual": "Situação atual",
        "nova_situacao": "Nova situação",
        "encaminhar_para": "Encaminhar para",
        "suspeita_fraude": "Suspeita de fraude",
    }
    parametros = {
        "id_cliente": {"tipo": "texto", "obrigatorio": True},
        "id_chamado": {"tipo": "texto", "obrigatorio": True},
        "nova_situacao": {"tipo": "texto", "obrigatorio": False},
        "encaminhar_para": {"tipo": "texto", "obrigatorio": False},
        "suspeita_fraude": {"tipo": "texto", "obrigatorio": False},
    }

    def montar(self, argumentos, usuario):
        codigo, id_chamado = argumentos["id_cliente"], argumentos["id_chamado"]
        nova_situacao = argumentos.get("nova_situacao")
        encaminhar_para = argumentos.get("encaminhar_para")
        suspeita_fraude = escritas_sinteticas.sim_ou_nao(argumentos.get("suspeita_fraude"), "suspeita_fraude")
        if nova_situacao is None and encaminhar_para is None and not suspeita_fraude:
            raise ErroFerramenta(
                "parametro_invalido", "Diga o que muda: nova_situacao, encaminhar_para ou suspeita_fraude."
            )
        if nova_situacao is not None and nova_situacao not in ROTULOS_DA_SITUACAO:
            raise ErroFerramenta("parametro_invalido", f"Situação desconhecida. Use: {', '.join(ROTULOS_DA_SITUACAO)}.")
        if encaminhar_para is not None and encaminhar_para not in DESTINOS:
            raise ErroFerramenta("parametro_invalido", "Encaminhe para N2 ou supervisor.")
        lojista.exigir_acesso(usuario, codigo)
        chamado = dados_sinteticos.buscar_chamado(codigo, id_chamado)
        if chamado is None:
            raise ErroFerramenta("nao_encontrado", "Chamado não encontrado para este lojista.")
        conteudo = {
            "codigo": codigo,
            "id_chamado": id_chamado,
            "nova_situacao": nova_situacao,
            "encaminhar_para": encaminhar_para,
            "suspeita_fraude": suspeita_fraude,
        }
        previa = {
            "id_cliente": codigo,
            "id_chamado": id_chamado,
            "situacao_atual": ROTULOS_DA_SITUACAO.get(chamado["situacao"], chamado["situacao"]),
            "nova_situacao": ROTULOS_DA_SITUACAO[nova_situacao] if nova_situacao else "sem mudança",
            "encaminhar_para": ROTULOS_DO_DESTINO[encaminhar_para] if encaminhar_para else "Não encaminhar",
            "suspeita_fraude": "sim, sobe para o N2" if suspeita_fraude else "não",
        }
        escritas_sinteticas.ensaiar(self._gravar, conteudo, usuario)  # o que a confirmação recusaria, já recusa
        return conteudo, previa

    def mensagem_ao_confirmar(self, dados):
        frases = []
        if dados["encaminhar_para"]:
            frases.append(f"Chamado {dados['id_chamado']} encaminhado ao {ROTULOS_DO_DESTINO[dados['encaminhar_para']].lower()}.")
        if dados["nova_situacao"]:
            frases.append(f"Chamado {dados['id_chamado']} agora está {ROTULOS_DA_SITUACAO[dados['nova_situacao']].lower()}.")
        if dados["suspeita_fraude"]:
            frases.append("Suspeita de fraude marcada: o chamado subiu para o N2.")
        return " ".join(frases)

    def referencia_do_resultado(self, dados):
        return dados["id_chamado"]  # id neutro do chamado alterado: no registro, liga a escrita a quem confirmou

    def efetivar(self, conteudo, usuario):
        return self._gravar(conteudo, usuario)

    def _gravar(self, conteudo, usuario):
        lojista.exigir_acesso(usuario, conteudo["codigo"])
        chamado = escritas_sinteticas.atualizar_chamado(
            conteudo["codigo"], conteudo["id_chamado"], usuario.id_usuario, conteudo["nova_situacao"],
            conteudo["encaminhar_para"], conteudo["suspeita_fraude"],
        )
        return {
            "id_chamado": chamado["codigo"],
            "situacao": chamado["situacao"],
            "nivel_atendimento": chamado["nivel_atendimento"],
            "suspeita_fraude": chamado["suspeita_fraude"],
            "nova_situacao": conteudo["nova_situacao"],
            "encaminhar_para": conteudo["encaminhar_para"],
        }


FERRAMENTA = AtualizarSituacaoChamado()
