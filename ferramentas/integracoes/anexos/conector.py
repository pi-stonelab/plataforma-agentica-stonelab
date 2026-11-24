"""Anexos do chat: os arquivos que a pessoa envia na conversa (entrada) e os que o agente entrega (saída).

A plataforma guarda tudo numa pasta própria (`ANEXOS_DIRETORIO`), separada por pessoa, e nunca em outro lugar do
disco: o nome de arquivo que chega é só um rótulo, o caminho é montado aqui, a partir de um id sorteado. Quem pede um
arquivo diz o id (`ANX-` + 12 letras de entrada, `ARQ-` + 12 letras de saída), nunca um caminho. O que o agente vê e devolve
é o id, o nome seguro, o tipo e o tamanho: o caminho do servidor não sai daqui.

Configuração (.env): `ANEXOS_DIRETORIO` (caminho absoluto da pasta, fora do repositório, onde a plataforma grava;
preencher liga a integração) e `ANEXOS_MODO` (`real`, `simulado` ou `desligado`; no simulado os arquivos ficam na
memória, com alguns de exemplo).

Regras (valem nos dois modos):
- tipos de entrada: txt, csv, xlsx, docx e pdf; de saída: csv, xlsx e txt; até 5 MB por arquivo;
- arquivo com macro, nome sem tipo conhecido, "zip" que não é xlsx/docx ou texto com byte nulo é recusado no envio;
- até 30 arquivos e 50 MB por pessoa (conferidos sob uma trava por pessoa: envios ao mesmo tempo não passam do limite);
- arquivo com mais de 7 dias some: nenhuma listagem, leitura ou download o enxerga, e ele é apagado na hora em que
  alguém o procura e, no máximo uma vez por hora, numa varredura de todas as pessoas (`expurgar_vencidos`);
- gravação atômica, permissão 0600 (só o usuário da plataforma) e abertura sem seguir link simbólico.

Pontos de ligação:
[A FAZER (Marcelo, back-end): rota de envio do chat (sugestão: POST /conversas/{id}/anexos): confere o token, lê o
arquivo (multipart) até 5 MB e chama `anexos.guardar_entrada(id_usuario_do_token, nome, bytes)`, devolvendo o `anexo_id`
à interface; na montagem do turno, listar os anexos da conversa para o agente (`listar_entradas`). Rota de download
(sugestão: GET /arquivos/{arquivo_id}): confere o token e chama `anexos.abrir_saida(id_usuario_do_token, arquivo_id)`,
respondendo com `Content-Disposition: attachment`, o tipo do arquivo e `X-Content-Type-Options: nosniff`]
[A FAZER (Larissa, interface): botão de anexar no chat (txt, csv, xlsx, docx e pdf, até 5 MB) e o link de download
do arquivo que o agente entrega, com o `arquivo_id` que vem na resposta da ferramenta]
"""

import errno
import os
import re
import secrets
import stat
import string
import threading
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import formatos
from ferramentas.integracoes.conector import Conector, ConfiguracaoInvalida, TravasPorChave
from ferramentas.integracoes.escritorio_simulado import PLANILHAS
from ferramentas.integracoes.registro import registrar

PADRAO_ID_ANEXO = re.compile(r"ANX-[A-Z]{12}")
PADRAO_ID_SAIDA = re.compile(r"ARQ-[A-Z]{12}")
PADRAO_ID_USUARIO = re.compile(r"[A-Za-z0-9_-]{1,40}")
PREFIXO_DO_ARQUIVO = re.compile(r"((?:ANX|ARQ)-[A-Z]{12})__(.+)")
TIPOS_DE_ENTRADA = ("txt", "csv", "xlsx", "docx", "pdf")
TIPOS_DE_SAIDA = ("csv", "xlsx", "txt")
TIPOS_DE_OFFICE = ("xlsx", "docx")
INTERVALO_DO_EXPURGO = timedelta(hours=1)  # no mais: a varredura de todas as pessoas roda a cada envio, no máximo uma vez por hora
ARQUIVOS_POR_PESSOA = 30
BYTES_POR_PESSOA = 50_000_000
RETENCAO = timedelta(days=7)
TAMANHO_DO_NOME = 80  # BYTES do nome sem extensão (o limite do sistema de arquivos é em bytes, não em letras)
NOME_PADRAO = "arquivo"
TAMANHO_DO_ID = 16  # "ANX-" + 12 letras
PASTAS = ("entrada", "saida")
MENSAGEM_TIPO_NAO_ACEITO = f"Tipo de arquivo não aceito. Aceitos: {', '.join(TIPOS_DE_ENTRADA)}."
MENSAGEM_LIMITE_DA_PESSOA = "Há arquivos demais guardados para esta pessoa. Eles são apagados depois de 7 dias."
MENSAGEM_NAO_ENCONTRADO = "Arquivo não encontrado."
MENSAGEM_ARMAZENAMENTO = "armazenamento de anexos indisponível"
MENSAGEM_PEDIDO_INVALIDO = "O nome do arquivo ou a pessoa não são aceitos pelo armazenamento de anexos."
ID_DO_SIMULADO = {  # anexos de exemplo (o "hoje" do mock): letras, como os ids de verdade
    "csv": "ANX-SIMULADOCSVX", "txt": "ANX-SIMULADOTXTX", "xlsx": "ANX-SIMULADOXLSX",
}


TRAVAS_DAS_PESSOAS = TravasPorChave()  # uma por pessoa e pasta: conferir a cota e gravar andam juntos
ULTIMO_EXPURGO = {"quando": None}


def nome_seguro(nome):
    """O nome como a plataforma guarda: sem pasta, sem caractere de controle ou especial, até 74 bytes.

    Devolve `(raiz, extensao)`: a extensão em minúsculas (vazia se não tem). O nome só serve de rótulo."""
    base = re.split(r"[\\/]", str(nome))[-1]
    base = unicodedata.normalize("NFC", base)
    base = re.sub(r"[^\w .()-]", "_", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    raiz, ponto, extensao = base.rpartition(".")
    if not ponto:
        raiz, extensao = extensao, ""
    raiz = _cortar_em_bytes(raiz.strip(" ."), TAMANHO_DO_NOME - 6).strip(" .") or NOME_PADRAO
    return raiz, _cortar_em_bytes(extensao.lower()[:5], 10)


def _cortar_em_bytes(texto, limite):
    """O começo de `texto` com no máximo `limite` bytes em UTF-8, sem partir uma letra no meio."""
    return texto.encode("utf-8")[:limite].decode("utf-8", "ignore")


def _sortear(prefixo):
    return prefixo + "-" + "".join(secrets.choice(string.ascii_uppercase) for _ in range(12))


def _agora():
    return datetime.now(UTC)


def conferir_conteudo(extensao, conteudo):
    """Confere se `conteudo` é mesmo um arquivo do tipo `extensao`, sem interpretá-lo. Problema: `ArquivoInvalido`."""
    if not conteudo:
        raise formatos.ArquivoInvalido
    if len(conteudo) > formatos.BYTES_NO_MAXIMO:
        raise formatos.ArquivoInvalido("O arquivo é grande demais (até 5 MB).")
    if extensao in TIPOS_DE_OFFICE:
        formatos.conferir_tipos(formatos.abrir_zip(conteudo))
    elif extensao == "pdf":
        if not conteudo.startswith(b"%PDF-"):
            raise formatos.ArquivoInvalido
    else:
        formatos.ler_txt(conteudo, limite=1)  # recusa byte nulo e codificação que não é texto


class _Armazenamento:
    """O que o armazenamento faz, igual na pasta de verdade e na memória (modo simulado)."""

    def guardar(self, pasta, prefixo, id_usuario, raiz, extensao, conteudo):
        raise NotImplementedError

    def listar(self, pasta, id_usuario):
        raise NotImplementedError

    def abrir(self, pasta, id_usuario, id_arquivo):
        raise NotImplementedError

    @staticmethod
    def _conferir_cota(existentes, conteudo):
        if len(existentes) >= ARQUIVOS_POR_PESSOA or sum(m["tamanho"] for m in existentes) + len(conteudo) > BYTES_POR_PESSOA:
            raise ErroFerramenta("integracao_indisponivel", MENSAGEM_LIMITE_DA_PESSOA)


def _meta(id_arquivo, nome, tamanho, criado_em):
    _, _, extensao = nome.rpartition(".")
    return {"id": id_arquivo, "nome": nome, "tipo": extensao, "tamanho": tamanho, "criado_em": criado_em.isoformat(timespec="seconds")}


class ArmazenamentoLocal(_Armazenamento):
    """Os arquivos numa pasta do servidor: `<raiz>/<entrada|saida>/<id_usuario>/<id>__<nome seguro>`."""

    def __init__(self, raiz):
        self.raiz = Path(raiz)

    def _pasta(self, pasta, id_usuario, criar=False):
        if pasta not in PASTAS or not PADRAO_ID_USUARIO.fullmatch(id_usuario):
            raise ValueError("pasta ou pessoa inválida")
        caminho = self.raiz / pasta / id_usuario
        if criar:
            caminho.mkdir(mode=0o700, parents=True, exist_ok=True)
        return caminho

    def listar(self, pasta, id_usuario):
        """Os arquivos da pessoa que ainda estão na retenção. O vencido (mais de 7 dias) é apagado na hora: nenhuma
        leitura, listagem ou abertura enxerga arquivo vencido, mesmo que a pessoa não envie nada novo (LGPD)."""
        caminho = self._pasta(pasta, id_usuario)
        if not caminho.is_dir():
            return []
        limite = _agora() - RETENCAO
        metas = []
        with os.scandir(caminho) as itens:
            for item in itens:
                achado = PREFIXO_DO_ARQUIVO.fullmatch(item.name)
                if achado is None or not item.is_file(follow_symlinks=False):
                    continue
                dados = item.stat(follow_symlinks=False)
                criado_em = datetime.fromtimestamp(dados.st_mtime, UTC)
                if criado_em < limite:
                    Path(item.path).unlink(missing_ok=True)
                    continue
                metas.append(_meta(achado.group(1), achado.group(2), dados.st_size, criado_em))
        return sorted(metas, key=lambda m: m["criado_em"], reverse=True)

    def expurgar_vencidos(self):
        """Apaga os arquivos vencidos de TODAS as pessoas (quem nunca mais volta também não guarda dado para sempre).
        Devolve quantos apagou."""
        apagados = 0
        for pasta in PASTAS:
            raiz = self.raiz / pasta
            if not raiz.is_dir():
                continue
            with os.scandir(raiz) as pessoas:
                nomes = [p.name for p in pessoas if p.is_dir(follow_symlinks=False) and PADRAO_ID_USUARIO.fullmatch(p.name)]
            for id_usuario in nomes:
                antes = len(list(self._pasta(pasta, id_usuario).iterdir()))
                self.listar(pasta, id_usuario)  # listar apaga o que venceu
                apagados += antes - len(list(self._pasta(pasta, id_usuario).iterdir()))
        return apagados

    def _caminho(self, pasta, id_usuario, meta):
        return self._pasta(pasta, id_usuario) / f"{meta['id']}__{meta['nome']}"

    def guardar(self, pasta, prefixo, id_usuario, raiz, extensao, conteudo):
        caminho = self._pasta(pasta, id_usuario, criar=True)
        self._expurgar_de_tempos_em_tempos()
        with TRAVAS_DAS_PESSOAS.da((pasta, id_usuario)):  # sem ela, 37 envios juntos passariam do limite de 30
            self._conferir_cota(self.listar(pasta, id_usuario), conteudo)
            return self._gravar(caminho, pasta, prefixo, raiz, extensao, conteudo)

    def _expurgar_de_tempos_em_tempos(self):
        agora = _agora()
        ultimo = ULTIMO_EXPURGO["quando"]
        if ultimo is None or agora - ultimo >= INTERVALO_DO_EXPURGO:
            ULTIMO_EXPURGO["quando"] = agora
            self.expurgar_vencidos()

    def _gravar(self, caminho, pasta, prefixo, raiz, extensao, conteudo):
        nome = f"{raiz}.{extensao}"
        for _ in range(5):  # o id é sorteado; se já existir, sorteia de novo
            id_arquivo = _sortear(prefixo)
            final = caminho / f"{id_arquivo}__{nome}"
            parcial = caminho / f".{id_arquivo}.parte"
            try:
                descritor = os.open(parcial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            except FileExistsError:
                continue
            try:
                with os.fdopen(descritor, "wb") as arquivo:
                    arquivo.write(conteudo)
                os.replace(parcial, final)
            finally:
                parcial.unlink(missing_ok=True)
            return _meta(id_arquivo, nome, len(conteudo), _agora())
        raise OSError("sem id livre")

    def abrir(self, pasta, id_usuario, id_arquivo):
        for meta in self.listar(pasta, id_usuario):
            if meta["id"] == id_arquivo:
                descritor = os.open(self._caminho(pasta, id_usuario, meta), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(descritor, "rb") as arquivo:
                    if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                        break
                    return meta, arquivo.read(formatos.BYTES_NO_MAXIMO + 1)[: formatos.BYTES_NO_MAXIMO]
        raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)

    def testar(self):
        """Grava, lê e apaga um arquivo de prova na raiz. Falha: `OSError`."""
        self.raiz.mkdir(mode=0o700, parents=True, exist_ok=True)
        prova = self.raiz / f".prova-{secrets.token_hex(4)}"
        try:
            prova.write_bytes(b"ok")
            if prova.read_bytes() != b"ok":
                raise OSError("leitura diferente da gravação")
        finally:
            prova.unlink(missing_ok=True)


class ArmazenamentoEmMemoria(_Armazenamento):
    """O modo simulado: os arquivos ficam na memória, por pessoa, e somem quando a plataforma reinicia."""

    def __init__(self):
        self._trava = threading.Lock()
        self._dados = {}

    def limpar(self):
        with self._trava:
            self._dados.clear()

    def _pessoa(self, pasta, id_usuario):
        if pasta not in PASTAS or not PADRAO_ID_USUARIO.fullmatch(id_usuario):
            raise ValueError("pasta ou pessoa inválida")
        if (pasta, id_usuario) not in self._dados:
            self._dados[(pasta, id_usuario)] = dict(_amostras()) if pasta == "entrada" else {}
        return self._dados[(pasta, id_usuario)]

    def listar(self, pasta, id_usuario):
        with self._trava:
            return sorted((dict(m) for m, _ in self._pessoa(pasta, id_usuario).values()), key=lambda m: m["id"])

    def guardar(self, pasta, prefixo, id_usuario, raiz, extensao, conteudo):
        with self._trava:
            arquivos = self._pessoa(pasta, id_usuario)
            self._conferir_cota([m for m, _ in arquivos.values()], conteudo)
            id_arquivo = _sortear(prefixo)
            meta = _meta(id_arquivo, f"{raiz}.{extensao}", len(conteudo), _agora())
            arquivos[id_arquivo] = (meta, conteudo)
            return dict(meta)

    def abrir(self, pasta, id_usuario, id_arquivo):
        with self._trava:
            achado = self._pessoa(pasta, id_usuario).get(id_arquivo)
        if achado is None:
            raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)
        return dict(achado[0]), achado[1]


def _amostras():
    """Os anexos de exemplo do modo simulado: indicadores agregados, nunca dado de lojista nem de pessoa."""
    hoje = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    semana = PLANILHAS["SIM-PLAN-CHAMADOS"]["abas"]["Semana"]
    recebiveis = PLANILHAS["SIM-PLAN-RECEBIVEIS"]["abas"]["Resumo"]
    csv_texto = "\r\n".join(";".join(linha) for linha in semana) + "\r\n"
    ata = (
        "Ata da reunião de alinhamento do time de atendimento.\n"
        "1. A fila de recebimento fechou a semana dentro do prazo.\n"
        "2. A fila de disputas teve nove chamados estourados e será revisada na próxima reunião.\n"
    )
    conteudos = {
        "csv": ("chamados_da_semana.csv", csv_texto.encode("utf-8")),
        "txt": ("ata_da_reuniao.txt", ata.encode("utf-8")),
        "xlsx": ("fechamento_de_recebiveis.xlsx", formatos.escrever_xlsx(recebiveis, "Resumo")),
    }
    return {
        ID_DO_SIMULADO[tipo]: (_meta(ID_DO_SIMULADO[tipo], nome, len(conteudo), hoje), conteudo)
        for tipo, (nome, conteudo) in conteudos.items()
    }


class ConectorAnexos(Conector):
    nome = "anexos"
    rotulo = "Anexos do chat"
    tipo = "interno"
    credencial = "plataforma"
    modo_padrao = "desligado"
    variavel_modo = "ANEXOS_MODO"
    variavel_que_liga = "ANEXOS_DIRETORIO"
    variaveis = ("ANEXOS_MODO", "ANEXOS_DIRETORIO")
    servicos = ("armazenamento",)
    fonte_real = "Anexos do chat"
    fonte_simulada = "Anexos do chat simulados (modo de demonstração): arquivos de exemplo, nada é gravado de verdade"
    mensagem_desligada = "Os anexos do chat não estão ligados nesta plataforma."
    como_ligar = "preencha ANEXOS_DIRETORIO com uma pasta onde a plataforma possa gravar (ou use ANEXOS_MODO=simulado)"
    dicas = {
        "ANEXOS_DIRETORIO": (
            "ANEXOS_DIRETORIO inválido: use o caminho absoluto de uma pasta onde a plataforma possa gravar, fora do"
            " repositório (veja ferramentas/integracoes/anexos/README.md)."
        ),
    }

    def __init__(self):
        super().__init__()
        self.simulado = ArmazenamentoEmMemoria()

    def fonte(self, ambiente=os.environ):
        return self.fonte_simulada if self.demonstracao(ambiente) else self.fonte_real

    def _raiz(self, ambiente):
        valor = (ambiente.get("ANEXOS_DIRETORIO") or "").strip()
        caminho = Path(valor) if valor and "\x00" not in valor else None
        if caminho is None or not caminho.is_absolute() or ".." in caminho.parts or caminho == Path(caminho.anchor):
            raise ConfiguracaoInvalida("ANEXOS_DIRETORIO")
        if caminho.exists() and not caminho.is_dir():
            raise ConfiguracaoInvalida("ANEXOS_DIRETORIO")
        return caminho

    def conferir_configuracao(self, ambiente=os.environ):
        self._raiz(ambiente)

    def _armazenamento(self, ambiente):
        if self._ligado(ambiente) == "simulado":
            return self.simulado
        return ArmazenamentoLocal(self._raiz(ambiente))

    def _usar(self, etapa, ambiente, funcao):
        """`funcao(armazenamento)` protegida pelo disjuntor. Erro do disco vira falha de integração, sem o caminho."""
        armazenamento = self._armazenamento(ambiente)

        def chamada():
            try:
                return funcao(armazenamento)
            except ValueError:  # pessoa ou pasta fora do formato: o pedido está errado, o disco está bem
                raise ErroFerramenta("parametro_invalido", MENSAGEM_PEDIDO_INVALIDO) from None
            except OSError as erro:
                if erro.errno == errno.ENAMETOOLONG:  # nome grande demais: culpa do arquivo, não do armazenamento
                    raise ErroFerramenta("parametro_invalido", MENSAGEM_PEDIDO_INVALIDO) from None
                raise ConnectionError(MENSAGEM_ARMAZENAMENTO) from None

        return self.chamar(etapa, chamada, servico="armazenamento")

    # --- entrada: o que a pessoa anexou ------------------------------------------------------------------------------

    def guardar_entrada(self, id_usuario, nome, conteudo, ambiente=os.environ):
        """Guarda o anexo da pessoa e devolve `{anexo_id, nome, tipo, tamanho}`. Arquivo fora das regras: `ArquivoInvalido`."""
        raiz, extensao = nome_seguro(nome)
        formatos.conferir_nome(f"{raiz}.{extensao}")
        if extensao not in TIPOS_DE_ENTRADA:
            raise formatos.ArquivoInvalido(MENSAGEM_TIPO_NAO_ACEITO)
        conferir_conteudo(extensao, conteudo)
        meta = self._usar(
            "guardar_entrada", ambiente, lambda a: a.guardar("entrada", "ANX", id_usuario, raiz, extensao, conteudo)
        )
        return {"anexo_id": meta["id"], "nome": meta["nome"], "tipo": meta["tipo"], "tamanho": meta["tamanho"]}

    def listar_entradas(self, id_usuario, ambiente=os.environ):
        """Os anexos da pessoa, do mais recente ao mais antigo: `[{anexo_id, nome, tipo, tamanho}]`."""
        metas = self._usar("listar_entradas", ambiente, lambda a: a.listar("entrada", id_usuario))
        return [{"anexo_id": m["id"], "nome": m["nome"], "tipo": m["tipo"], "tamanho": m["tamanho"]} for m in metas]

    def ler_entrada(self, id_usuario, anexo_id, aba, limite_linhas, limite_caracteres, ambiente=os.environ):
        """O conteúdo do anexo, no formato do tipo: `texto` (txt, docx, pdf) ou `linhas` (csv, xlsx), e `truncado`."""
        if not PADRAO_ID_ANEXO.fullmatch(anexo_id):
            raise ErroFerramenta("parametro_invalido", "O anexo_id deve ter o formato ANX-ABCDEFGHIJKL.")
        meta, conteudo = self._usar("ler_entrada", ambiente, lambda a: a.abrir("entrada", id_usuario, anexo_id))
        tipo = meta["tipo"]
        if tipo == "txt":
            lido = formatos.ler_txt(conteudo, limite_caracteres)
        elif tipo == "csv":
            lido = formatos.ler_csv(conteudo, limite_linhas)
        elif tipo == "xlsx":
            lido = formatos.ler_xlsx(conteudo, aba, limite_linhas)
        elif tipo == "docx":
            lido = formatos.ler_docx(conteudo, limite_caracteres)
        elif tipo == "pdf":
            lido = formatos.ler_pdf(conteudo, limite=limite_caracteres)
        else:
            raise formatos.ArquivoInvalido(MENSAGEM_TIPO_NAO_ACEITO)
        return {"anexo_id": anexo_id, "nome": meta["nome"], "tipo": tipo, "tamanho": meta["tamanho"], **lido}

    # --- saída: o que o agente entrega -----------------------------------------------------------------------------------

    def guardar_saida(self, id_usuario, nome, formato, conteudo, ambiente=os.environ):
        """Guarda o arquivo gerado e devolve `{arquivo_id, nome, formato, tamanho}`; o caminho nunca sai daqui."""
        raiz, _ = nome_seguro(nome)
        if formato not in TIPOS_DE_SAIDA:
            raise ErroFerramenta("parametro_invalido", f"O formato deve ser um destes: {', '.join(TIPOS_DE_SAIDA)}.")
        if not conteudo or len(conteudo) > formatos.BYTES_NO_MAXIMO:
            raise ErroFerramenta("parametro_invalido", "O arquivo ficou vazio ou grande demais (até 5 MB).")
        meta = self._usar("guardar_saida", ambiente, lambda a: a.guardar("saida", "ARQ", id_usuario, raiz, formato, conteudo))
        return {"arquivo_id": meta["id"], "nome": meta["nome"], "formato": formato, "tamanho": meta["tamanho"]}

    def abrir_saida(self, id_usuario, arquivo_id, ambiente=os.environ):
        """`({arquivo_id, nome, formato, tamanho}, bytes)` do arquivo entregue a esta pessoa. Outra pessoa: `nao_encontrado`."""
        if not PADRAO_ID_SAIDA.fullmatch(arquivo_id):
            raise ErroFerramenta("nao_encontrado", MENSAGEM_NAO_ENCONTRADO)
        meta, conteudo = self._usar("abrir_saida", ambiente, lambda a: a.abrir("saida", id_usuario, arquivo_id))
        return {"arquivo_id": arquivo_id, "nome": meta["nome"], "formato": meta["tipo"], "tamanho": meta["tamanho"]}, conteudo

    # --- teste e reinício ----------------------------------------------------------------------------------------------

    def testar(self, ambiente=os.environ):
        if self._ligado(ambiente) == "simulado":
            return "Modo simulado: os anexos ficam na memória, com três arquivos de exemplo por pessoa."

        def provar(armazenamento):
            armazenamento.testar()

        self._usar("testar", ambiente, provar)
        return "A pasta de anexos aceitou gravar e ler um arquivo de prova (apagado em seguida)."

    def expurgar_vencidos(self, ambiente=os.environ):
        """Apaga o que passou da retenção, de todas as pessoas. O back-end pode rodar isto de tempos em tempos (um
        agendador por dia basta); sem ele, a varredura de hora em hora dentro do envio já cobre. Quantos apagou."""
        if self._ligado(ambiente) == "simulado":
            return 0  # a memória some quando a plataforma reinicia
        return self._usar("expurgar", ambiente, lambda a: a.expurgar_vencidos())

    def reiniciar(self):
        super().reiniciar()
        self.simulado.limpar()
        ULTIMO_EXPURGO["quando"] = None


CONECTOR = registrar(ConectorAnexos())
