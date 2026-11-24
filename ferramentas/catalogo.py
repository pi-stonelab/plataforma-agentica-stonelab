import importlib
import re
from contextlib import suppress
from pathlib import Path
from time import monotonic

from ferramentas import governanca, integracoes
from ferramentas.base import montar_registro, resposta

NOME_ARQUIVO_INSTRUCOES = "agents.md"
MENSAGEM_INDISPONIVEL = "Caminho não encontrado ou não liberado para você."
RAIZ = Path(__file__).parent
# Marcadores para pessoas (ferramentas/pendencias.py): saem do texto antes de chegar ao modelo.
PADRAO_MARCADOR = re.compile(r"\s*\[(?:A FAZER \(|DECIDIR \(|aqui conectamos|preencher)[^\]]*\]")
PADRAO_TITULO_VAZIO = re.compile(r"^## .*\n\s*(?=^## |\Z)", re.MULTILINE)
# Ficha ainda planejada começa com "[preencher: o que faz... Sugestão: <frase>]": a interface mostra a sugestão.
PADRAO_SUGESTAO = re.compile(r"Sugest[ãa]o:\s*([^\]]+)\]")
# O motivo técnico de `governanca.motivo_bloqueio` em linguagem de quem usa a tela (o técnico fica no registro).
MOTIVOS_PARA_A_PESSOA = {
    "Usuário inválido.": "Seu perfil não usa ferramentas de dados.",
    "Nível insuficiente.": "Seu cargo não tem o nível que esta ferramenta pede.",
    "Área não permitida.": "Esta ferramenta é de outra área.",
    "Categoria de dado não permitida para o cargo.": "Seu cargo não acessa esse tipo de dado.",
}
MOTIVO_GENERICO = "Não liberada para o seu perfil."
MOTIVO_PLANEJADA = "Ainda não disponível."
FERRAMENTAS = {}


def carregar():
    """Importa as func.py uma vez e devolve {nome: ferramenta}."""
    if not FERRAMENTAS:
        for arquivo in sorted(RAIZ.glob("*/*/func.py")):
            area, nome = arquivo.parts[-3], arquivo.parts[-2]
            modulo = importlib.import_module(f"ferramentas.{area}.{nome}.func")
            FERRAMENTAS[modulo.FERRAMENTA.nome] = modulo.FERRAMENTA
    return FERRAMENTAS


def nomes():
    """Nomes de todas as ferramentas do catálogo, sem entregar os objetos (e o `rodar` deles, MED-3)."""
    return sorted(carregar())


def nomes_e_areas():
    """Conjunto com os nomes das ferramentas e das áreas (para o agente filtrar o que vai ao log)."""
    return {nome for nome in carregar()} | {f.area for f in carregar().values()}


def _buscar(nome):
    return carregar().get(nome) if isinstance(nome, str) else None


def _integracao_desligada(ferramenta):
    """O conector da primeira integração da ficha que está desligada ou mal configurada no .env, ou None."""
    for nome in ferramenta.integracoes:
        conector = integracoes.conector(nome)
        if not conector.configurado():
            return conector
    return None


def _camada_bloqueio(nome, usuario, ferramentas_do_agente):
    ferramenta = _buscar(nome)
    if ferramenta is None:
        return "desconhecida"
    permitidas = (
        ferramentas_do_agente if isinstance(ferramentas_do_agente, (tuple, list, set)) else ()
    )
    if nome not in permitidas:
        return "agente"
    if governanca.motivo_bloqueio(ferramenta, usuario) is not None:
        return "usuario"
    if not ferramenta.esta_ativa():
        return "inativa"
    return "desligada" if _integracao_desligada(ferramenta) is not None else None


def ferramentas_liberadas(usuario, ferramentas_do_agente):
    """O que o modelo pode usar agora: liberado para a pessoa, no agente, ativo e com a integração ligada."""
    # [aqui conectamos com agentes: lista de ferramentas da configuração do agente, KAN-55]
    camadas = {n: _camada_bloqueio(n, usuario, ferramentas_do_agente) for n in carregar()}
    return sorted(nome for nome, camada in camadas.items() if camada is None)


def _ler_arquivo(pasta):
    return (pasta / NOME_ARQUIVO_INSTRUCOES).read_text("utf-8").split("## Para quem mantém")[0]


def _primeiro_paragrafo(pasta):
    try:
        texto = _ler_arquivo(pasta)
    except OSError:
        return ""
    paragrafos = [p for p in texto.split("\n\n") if p.strip() and not p.startswith("#")]
    return " ".join(paragrafos[0].split()) if paragrafos else ""


def _primeira_frase(pasta):
    """Primeira frase do primeiro parágrafo depois do título, usada nas listas."""
    return re.split(r"(?<=\.)\s", _primeiro_paragrafo(pasta))[0]


def _descricao(pasta):
    """Primeira frase útil para a interface: sem marcadores; na ficha planejada, a frase sugerida."""
    paragrafo = _primeiro_paragrafo(pasta)
    sugestao = PADRAO_SUGESTAO.search(paragrafo) if paragrafo.startswith("[") else None
    if sugestao:
        frase = sugestao.group(1).strip().rstrip(".")
        return frase[:1].upper() + frase[1:] + "."
    limpo = " ".join(PADRAO_MARCADOR.sub("", paragrafo).split())
    return re.split(r"(?<=\.)\s", limpo)[0] if limpo else ""


def _status_para_interface(ferramenta):
    """`planejada` e `inativa` como na ficha; ativa com uma integração desligada ou mal configurada: `inativa`."""
    if ferramenta.status == "planejada":
        return "planejada"
    if not ferramenta.esta_ativa() or _integracao_desligada(ferramenta) is not None:
        return "inativa"
    return "ativa"


def _motivo_para_a_pessoa(ferramenta, status, motivo_tecnico):
    """Por que a pessoa não pode usar a ferramenta agora, em linguagem simples; None se pode."""
    if motivo_tecnico is not None:
        return MOTIVOS_PARA_A_PESSOA.get(motivo_tecnico, MOTIVO_GENERICO)
    if status == "planejada":
        return MOTIVO_PLANEJADA
    if status == "inativa":
        desligada = _integracao_desligada(ferramenta)
        if desligada is not None:
            return f"{desligada.rotulo}: integração desligada pela administração da plataforma."
        return "Desativada pela administração da plataforma."
    return None


def listar_fichas(usuario):
    """O catálogo inteiro no formato `Ferramenta` do contrato do front (frontend/CONTRATO_API.md §4.10).

    Cada ficha vem marcada para `usuario` (o `governanca.Usuario` do login): `liberada` é True só se a pessoa
    pode usar a ferramenta agora (permissão, status e integração ligada); `motivo` explica o porquê em
    linguagem simples (o motivo técnico de `governanca.motivo_bloqueio` fica no registro). `descricao` é a
    `descricao_para_pessoa` da ficha, se houver; senão a primeira frase do `agents.md`. A D10 (não listar as
    ferramentas para a pessoa) foi revogada pelo Pedro em 22/11. Só texto e listas, nunca o objeto (MED-3).
    [A FAZER (Marcelo e Isabel, back-end, KAN-60): a rota GET /ferramentas devolve esta lista; o perfil
    GestorDeAcessos, que não usa ferramentas, recebe 403 antes de chegar aqui]
    """
    fichas = []
    for nome, ferramenta in sorted(carregar().items()):
        status = _status_para_interface(ferramenta)
        motivo = _motivo_para_a_pessoa(ferramenta, status, governanca.motivo_bloqueio(ferramenta, usuario))
        descricao = getattr(ferramenta, "descricao_para_pessoa", "") or _descricao(RAIZ / ferramenta.area / nome)
        fichas.append(
            {
                "nome": nome,
                "area": ferramenta.area,
                "descricao": descricao,
                "acesso": ferramenta.acesso,
                "sensibilidade": ferramenta.sensibilidade,
                "status": status,
                "integracoes": list(ferramenta.integracoes),
                "liberada": motivo is None,
                "motivo": motivo,
            }
        )
    return fichas


def _lista(texto, titulo, itens):
    """Troca o corpo da seção `## titulo` de `texto` pela lista `- nome: primeira frase` dos itens."""
    linhas = "\n".join(f"- `{nome}`: {_primeira_frase(destino)}" for nome, destino in itens)
    padrao = re.compile(rf"(## {titulo}\n).*?(?=\n## |\Z)", re.DOTALL)
    return padrao.sub(lambda m: f"{m.group(1)}\n{linhas}\n", texto)


def _texto_do_caminho(caminho, liberadas):
    """Texto do nível pedido; ValueError se o caminho não existe ou não está liberado.

    A raiz já lista as ferramentas liberadas (`area/nome` e a primeira frase da ficha), para o
    modelo poder ler a ficha direto, sem passar pelo texto da área (P1 da crítica B).
    """
    ferramentas = carregar()
    areas = sorted({ferramentas[n].area for n in liberadas})
    if caminho == "":
        texto = _lista(_ler_arquivo(RAIZ), "Áreas", [(a, RAIZ / a) for a in areas])
        fichas = [(f"{ferramentas[n].area}/{n}", RAIZ / ferramentas[n].area / n) for n in liberadas]
        return _lista(texto, "Ferramentas liberadas para você", sorted(fichas))
    if caminho in areas:
        itens = [(n, RAIZ / caminho / n) for n in liberadas if ferramentas[n].area == caminho]
        return _lista(_ler_arquivo(RAIZ / caminho), "Ferramentas", itens)
    nome = caminho.split("/")[-1]
    if nome in liberadas:
        area = ferramentas[nome].area
        if caminho in (nome, f"{area}/{nome}"):
            return _ler_arquivo(RAIZ / area / nome) + _situacao_agora(ferramentas[nome])
    raise ValueError


def _situacao_agora(ferramenta):
    """O que a ficha não sabe de antemão e o modelo precisa ver: o que está liberado agora no .env (canais, chats,
    projetos) e se a integração está em demonstração. A ferramenta que tem isso escreve `situacao_para_o_agente`."""
    situacao = getattr(ferramenta, "situacao_para_o_agente", None)
    try:
        texto = situacao() if callable(situacao) else ""
    except ConnectionError:  # configuração errada: a ficha nem aparece (a integração some do índice)
        texto = ""
    return f"\n\n## Liberado agora\n\n{texto}" if texto else ""


def ler(caminho, usuario, ferramentas_do_agente):
    """Texto para o modelo: raiz (""), área ou ferramenta, só com o que está liberado."""
    liberadas = ferramentas_liberadas(usuario, ferramentas_do_agente)
    try:
        texto = _texto_do_caminho(str(caminho).strip(), liberadas)
    except (OSError, ValueError):
        return MENSAGEM_INDISPONIVEL
    texto = PADRAO_TITULO_VAZIO.sub("", PADRAO_MARCADOR.sub("", texto))
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def registrar_bloqueio(nome, usuario, contexto, camada):
    """Deixa o registro (sem argumentos nem dados) de uma tentativa que não chegou a rodar (MED-2).

    `camada` diz quem barrou: "agente" (o agente não leu ou não tem a ferramenta), "usuario",
    "inativa", "desconhecida" ou "desligada". Nas quatro primeiras a resposta é a mesma ("não encontrada"):
    a pessoa nunca vê a camada. "desligada" só chega aqui depois de passar pelo agente e pela permissão da
    pessoa, então pode dizer a verdade: a integração está desligada, avise o usuário e não tente de novo.
    Se o destino do registro falhar, a negação continua valendo e `governanca.registrar` já deixou o erro no log.
    """
    ferramenta = _buscar(nome)
    desligada = _integracao_desligada(ferramenta) if camada == "desligada" else None
    if desligada is not None:
        resultado = resposta("erro", None, desligada.aviso_desligada(), "ferramenta_inativa")
    else:
        resultado = resposta("erro", None, "Ferramenta não encontrada.", "ferramenta_inexistente")
    registro = montar_registro(ferramenta, usuario, contexto, resultado, camada, monotonic())
    with suppress(governanca.RegistroIndisponivel):
        governanca.registrar(registro)
    return resultado


def executar(nome, argumentos, usuario, ferramentas_do_agente, contexto=None):
    """Roda a ferramenta se ela está liberada; senão responde como se não existisse."""
    camada = _camada_bloqueio(nome, usuario, ferramentas_do_agente)
    if camada is None:
        return carregar()[nome].executar(argumentos, usuario, contexto)
    return registrar_bloqueio(nome, usuario, contexto, camada)
