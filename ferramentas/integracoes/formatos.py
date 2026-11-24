"""Leitura e escrita segura de arquivos de escritório: txt, csv, xlsx, docx e pdf (leitura), csv, xlsx e txt (escrita).

Só biblioteca padrão (`zipfile`, `xml.etree`, `csv`), mais o `pypdf` para PDF, importado só quando um PDF chega. O
arquivo vem de uma pessoa ou de uma conta externa, então ele é tratado como hostil:
- nada é executado: macro (`vbaProject.bin`, `.xlsm`, `.docm`), fórmula e script ficam parados; da fórmula só se lê o
  último valor que o Excel guardou;
- zip: poucas partes, nomes sem `..` nem caminho absoluto, tamanho descompactado limitado (zip bomb) e cada parte lida
  com teto, mesmo que o cabeçalho minta;
- XML com `DOCTYPE` ou `ENTITY` é recusado (entidade que se multiplica, entidade externa);
- limites de bytes, linhas, colunas, caracteres e páginas, e o resultado diz quando cortou.

Erro de formato: `ArquivoInvalido` (`parametro_invalido`), com mensagem fixa, sem trecho do arquivo.
Quem usa mascara o que sai (`mascara.py`); aqui só se lê e se escreve.
"""

import csv
import io
import re
import xml.etree.ElementTree as ET
import zipfile

from ferramentas.base import ErroFerramenta

MENSAGEM_ARQUIVO_INVALIDO = "O arquivo está corrompido, protegido ou fora do formato aceito."
MENSAGEM_COM_MACRO = "Arquivos com macro não são aceitos."
MENSAGEM_PDF_INDISPONIVEL = "A leitura de PDF não está instalada nesta plataforma."
BYTES_NO_MAXIMO = 5_000_000
PARTES_NO_MAXIMO = 500
BYTES_DESCOMPACTADOS_NO_MAXIMO = 25_000_000
BYTES_DA_PARTE_NO_MAXIMO = 15_000_000
LINHAS_PADRAO = 200
COLUNAS_PADRAO = 30
CARACTERES_PADRAO = 20_000
PAGINAS_PADRAO = 20
TAMANHO_DA_CELULA = 2000
TAMANHO_DO_NOME_DA_ABA = 31
EXTENSOES_COM_MACRO = (".xlsm", ".xlsb", ".docm", ".xltm", ".dotm")
TIPOS_COM_MACRO = ("macroenabled", "vbaproject")
PADRAO_NUMERO = re.compile(r"-?(0|[1-9][0-9]{0,14})(\.[0-9]{1,6})?")  # sem zero à esquerda: "007" é código, não número
PADRAO_DE_FORMULA = re.compile(r"[=@]|[+-](?!" + PADRAO_NUMERO.pattern + r"$)")
CARACTERE_ILEGAL_NO_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
NS_RELACOES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ArquivoInvalido(ErroFerramenta):
    def __init__(self, mensagem=MENSAGEM_ARQUIVO_INVALIDO):
        super().__init__("parametro_invalido", mensagem)


def _nome_local(etiqueta):
    return etiqueta.rsplit("}", 1)[-1]


# --- zip e xml --------------------------------------------------------------------------------------------------------


def abrir_zip(conteudo):
    """O `ZipFile` de um xlsx/docx depois de conferir tamanho, partes, nomes e macro. Qualquer problema: `ArquivoInvalido`."""
    if len(conteudo) > BYTES_NO_MAXIMO:
        raise ArquivoInvalido("O arquivo é grande demais.")
    try:
        pacote = zipfile.ZipFile(io.BytesIO(conteudo))
        partes = pacote.infolist()
    except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError):
        raise ArquivoInvalido from None
    if not partes or len(partes) > PARTES_NO_MAXIMO:
        raise ArquivoInvalido
    total = 0
    for parte in partes:
        nome = parte.filename
        if nome.startswith(("/", "\\")) or ".." in nome.replace("\\", "/").split("/") or "\x00" in nome:
            raise ArquivoInvalido
        if "vbaproject" in nome.lower() or parte.flag_bits & 0x1:  # 0x1: parte criptografada
            raise ArquivoInvalido(MENSAGEM_COM_MACRO if "vbaproject" in nome.lower() else MENSAGEM_ARQUIVO_INVALIDO)
        total += parte.file_size
        if parte.file_size > BYTES_DA_PARTE_NO_MAXIMO or total > BYTES_DESCOMPACTADOS_NO_MAXIMO:
            raise ArquivoInvalido("O arquivo é grande demais depois de aberto.")
    return pacote


def _parte(pacote, nome, obrigatoria=True):
    """Os bytes de uma parte, lidos com teto. Faltando: `ArquivoInvalido` (ou None se não for obrigatória)."""
    try:
        with pacote.open(nome) as parte:
            dados = parte.read(BYTES_DA_PARTE_NO_MAXIMO + 1)
    except KeyError:
        if obrigatoria:
            raise ArquivoInvalido from None
        return None
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError, NotImplementedError):
        raise ArquivoInvalido from None
    if len(dados) > BYTES_DA_PARTE_NO_MAXIMO:
        raise ArquivoInvalido("O arquivo é grande demais depois de aberto.")
    return dados


def _conferir_xml(dados):
    minusculas = dados.lower()
    if b"<!doctype" in minusculas or b"<!entity" in minusculas:
        raise ArquivoInvalido
    return dados


def _arvore(dados):
    try:
        return ET.fromstring(_conferir_xml(dados))
    except ET.ParseError:
        raise ArquivoInvalido from None


def _eventos(dados):
    """Os elementos do XML, um a um (para parar cedo numa planilha grande)."""
    try:
        yield from ET.iterparse(io.BytesIO(_conferir_xml(dados)), events=("end",))
    except ET.ParseError:
        raise ArquivoInvalido from None


def conferir_tipos(pacote):
    """Recusa pacote que se declara com macro, mesmo com extensão de arquivo comum."""
    tipos = _parte(pacote, "[Content_Types].xml", obrigatoria=False)
    if tipos is not None and any(marca in tipos.lower().decode("utf-8", "ignore") for marca in TIPOS_COM_MACRO):
        raise ArquivoInvalido(MENSAGEM_COM_MACRO)


def conferir_nome(nome):
    """O nome do arquivo não pode indicar macro. A conferência de verdade é pelo conteúdo; esta é a de cortesia."""
    if (nome or "").lower().endswith(EXTENSOES_COM_MACRO):
        raise ArquivoInvalido(MENSAGEM_COM_MACRO)


# --- txt e csv --------------------------------------------------------------------------------------------------------


def _decodificar(conteudo):
    if b"\x00" in conteudo[:8192]:
        raise ArquivoInvalido
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ArquivoInvalido


def _sem_controle(texto):
    return "".join(c for c in texto if c in "\t\n" or ord(c) >= 32)


def ler_txt(conteudo, limite=CARACTERES_PADRAO):
    """{"texto", "truncado"}."""
    if len(conteudo) > BYTES_NO_MAXIMO:
        raise ArquivoInvalido("O arquivo é grande demais.")
    texto = _sem_controle(_decodificar(conteudo).replace("\r\n", "\n").replace("\r", "\n"))
    return {"texto": texto[:limite], "truncado": len(texto) > limite}


def ler_csv(conteudo, limite_linhas=LINHAS_PADRAO, limite_colunas=COLUNAS_PADRAO):
    """{"linhas", "truncado"}. O separador (`,`, `;` ou tabulação) é descoberto pela primeira linha."""
    if len(conteudo) > BYTES_NO_MAXIMO:
        raise ArquivoInvalido("O arquivo é grande demais.")
    texto = _sem_controle(_decodificar(conteudo).replace("\r\n", "\n").replace("\r", "\n"))
    primeira = texto.split("\n", 1)[0]
    separador = max(",;\t", key=primeira.count) if any(s in primeira for s in ",;\t") else ","
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=separador)
    linhas, truncado = [], False
    try:
        for linha in leitor:
            if len(linhas) >= limite_linhas:
                truncado = True
                break
            truncado = truncado or len(linha) > limite_colunas
            linhas.append([celula[:TAMANHO_DA_CELULA] for celula in linha[:limite_colunas]])
    except csv.Error:
        raise ArquivoInvalido from None
    return {"linhas": linhas, "truncado": truncado}


# --- xlsx -------------------------------------------------------------------------------------------------------------


def _coluna_de(referencia):
    """"C12" -> 2 (índice da coluna, a partir de 0). Fora do formato: -1."""
    letras = re.match(r"[A-Z]{1,3}", referencia or "")
    if letras is None:
        return -1
    indice = 0
    for letra in letras.group():
        indice = indice * 26 + ord(letra) - 64
    return indice - 1


def _texto_do_item(elemento):
    """O texto de um `<si>` ou `<is>`: o `<t>` direto e os `<t>` de cada pedaço formatado (`<r>`), sem o fonético."""
    partes = []
    for filho in elemento:
        nome = _nome_local(filho.tag)
        if nome == "t":
            partes.append(filho.text or "")
        elif nome == "r":
            partes.extend(t.text or "" for t in filho if _nome_local(t.tag) == "t")
    return "".join(partes)[:TAMANHO_DA_CELULA]


def _textos_compartilhados(pacote):
    dados = _parte(pacote, "xl/sharedStrings.xml", obrigatoria=False)
    if dados is None:
        return []
    return [_texto_do_item(item) for item in _arvore(dados) if _nome_local(item.tag) == "si"]


def _abas(pacote):
    """[(nome, caminho da parte)] na ordem do arquivo."""
    livro = _arvore(_parte(pacote, "xl/workbook.xml"))
    relacoes = {
        item.get("Id"): item.get("Target", "")
        for item in _arvore(_parte(pacote, "xl/_rels/workbook.xml.rels"))
        if _nome_local(item.tag) == "Relationship"
    }
    abas = []
    for item in livro.iter():
        if _nome_local(item.tag) != "sheet":
            continue
        alvo = relacoes.get(item.get(f"{{{NS_RELACOES}}}id"), "")
        caminho = alvo.lstrip("/") if alvo.startswith("/") else "xl/" + alvo
        abas.append((item.get("name") or "", caminho))
    if not abas:
        raise ArquivoInvalido
    return abas


def _valor_da_celula(celula, textos):
    tipo = celula.get("t")
    if tipo == "inlineStr":
        return next((_texto_do_item(f) for f in celula if _nome_local(f.tag) == "is"), "")
    valor = next((f.text or "" for f in celula if _nome_local(f.tag) == "v"), "")
    if tipo == "s":
        try:
            return textos[int(valor)]
        except (ValueError, IndexError):
            raise ArquivoInvalido from None
    if tipo == "b":
        return "VERDADEIRO" if valor == "1" else "FALSO"
    return valor[:TAMANHO_DA_CELULA]


def ler_xlsx(conteudo, aba=None, limite_linhas=LINHAS_PADRAO, limite_colunas=COLUNAS_PADRAO):
    """{"abas", "aba", "linhas", "truncado"}: a aba pedida (ou a primeira), células como texto.

    Fórmula: vale o último resultado que o Excel guardou na célula, nada é calculado. Datas chegam como o número de
    série do Excel (o formato da célula não é interpretado)."""
    pacote = abrir_zip(conteudo)
    conferir_tipos(pacote)
    abas = _abas(pacote)
    nomes = [nome for nome, _ in abas]
    escolhida = nomes[0] if aba is None else aba
    if escolhida not in nomes:
        raise ErroFerramenta("nao_encontrado", f"Aba não encontrada. Abas do arquivo: {', '.join(nomes)}.")
    caminho = dict(abas)[escolhida]
    textos = _textos_compartilhados(pacote)
    linhas, truncado = [], False
    for _, elemento in _eventos(_parte(pacote, caminho)):
        if _nome_local(elemento.tag) != "row":
            continue
        if len(linhas) >= limite_linhas:
            truncado = True
            break
        linha = []
        for celula in elemento:
            if _nome_local(celula.tag) != "c":
                continue
            coluna = _coluna_de(celula.get("r")) if celula.get("r") else len(linha)
            if coluna >= limite_colunas:
                truncado = True
                continue
            if coluna >= 0:
                linha.extend([""] * (coluna - len(linha)))
                linha.append(_valor_da_celula(celula, textos))
        while linha and linha[-1] == "":
            linha.pop()
        numero = elemento.get("r")
        if numero and numero.isdigit():  # linha em branco no meio do arquivo continua em branco
            alvo = min(int(numero) - 1, limite_linhas)
            while len(linhas) < alvo:
                linhas.append([])
        linhas.append(linha)
        elemento.clear()
    while linhas and not any(linhas[-1]):
        linhas.pop()
    return {"abas": nomes, "aba": escolhida, "linhas": linhas[:limite_linhas], "truncado": truncado}


# --- docx -------------------------------------------------------------------------------------------------------------


def _texto_do_paragrafo(paragrafo):
    partes = []
    for item in paragrafo.iter():
        nome = _nome_local(item.tag)
        if nome == "t" and item.text:
            partes.append(item.text)
        elif nome == "tab":
            partes.append("\t")
        elif nome in ("br", "cr"):
            partes.append("\n")
    return "".join(partes)


def _blocos_do_docx(corpo):
    for bloco in corpo:
        nome = _nome_local(bloco.tag)
        if nome == "p":
            yield _texto_do_paragrafo(bloco)
        elif nome == "tbl":
            for linha in bloco.iter():
                if _nome_local(linha.tag) == "tr":
                    celulas = [
                        " ".join(_texto_do_paragrafo(p) for p in celula.iter() if _nome_local(p.tag) == "p").strip()
                        for celula in linha
                        if _nome_local(celula.tag) == "tc"
                    ]
                    yield "\t".join(celulas)


def ler_docx(conteudo, limite=CARACTERES_PADRAO):
    """{"texto", "truncado"}: parágrafos e tabelas (células separadas por tabulação). Imagem, cabeçalho e comentário ficam de fora."""
    pacote = abrir_zip(conteudo)
    conferir_tipos(pacote)
    raiz = _arvore(_parte(pacote, "word/document.xml"))
    corpo = next((filho for filho in raiz if _nome_local(filho.tag) == "body"), None)
    if corpo is None:
        raise ArquivoInvalido
    partes, tamanho = [], 0
    for bloco in _blocos_do_docx(corpo):
        partes.append(bloco)
        tamanho += len(bloco) + 1
        if tamanho > limite:
            break
    texto = _sem_controle("\n".join(partes))
    return {"texto": texto[:limite], "truncado": tamanho > limite or len(texto) > limite}


# --- pdf --------------------------------------------------------------------------------------------------------------


def ler_pdf(conteudo, limite_paginas=PAGINAS_PADRAO, limite=CARACTERES_PADRAO):
    """{"texto", "paginas", "truncado"}. PDF só de imagem (digitalizado) não tem texto: devolve vazio, sem OCR."""
    if len(conteudo) > BYTES_NO_MAXIMO:
        raise ArquivoInvalido("O arquivo é grande demais.")
    if not conteudo.startswith(b"%PDF-"):
        raise ArquivoInvalido
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        raise ErroFerramenta("integracao_indisponivel", MENSAGEM_PDF_INDISPONIVEL) from None
    try:
        leitor = PdfReader(io.BytesIO(conteudo), strict=False)
        if leitor.is_encrypted:
            raise ArquivoInvalido
        paginas = len(leitor.pages)
        partes, tamanho = [], 0
        for pagina in leitor.pages[:limite_paginas]:
            partes.append(pagina.extract_text() or "")
            tamanho += len(partes[-1])
            if tamanho > limite:
                break
    except ArquivoInvalido:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError, OSError):
        raise ArquivoInvalido from None
    texto = _sem_controle("\n".join(partes))
    return {"texto": texto[:limite], "paginas": paginas, "truncado": paginas > limite_paginas or len(texto) > limite}


# --- escrita ----------------------------------------------------------------------------------------------------------


def celula_como_texto(valor):
    """O valor da célula como texto que uma planilha nunca executa: o que parece fórmula ganha um apóstrofo na frente."""
    texto = "" if valor is None else str(valor)
    texto = _sem_controle(texto.replace("\r", " ").replace("\n", " "))
    return "'" + texto if PADRAO_DE_FORMULA.match(texto) else texto


def escrever_csv(linhas):
    """Bytes UTF-8 com BOM e `;` (abre certo no Excel em português). Células com cara de fórmula viram texto."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    for linha in linhas:
        escritor.writerow([celula_como_texto(celula) for celula in linha])
    return saida.getvalue().encode("utf-8-sig")


def escrever_txt(texto):
    return _sem_controle(str(texto).replace("\r\n", "\n").replace("\r", "\n")).encode("utf-8")


def _letra_da_coluna(indice):
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _xml_seguro(texto):
    return CARACTERE_ILEGAL_NO_XML.sub("", texto)


def _celula_xlsx(referencia, valor):
    texto = "" if valor is None else str(valor)
    if PADRAO_NUMERO.fullmatch(texto):
        return f'<c r="{referencia}"><v>{texto}</v></c>'
    escapado = _xml_seguro(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<c r="{referencia}" t="inlineStr"><is><t xml:space="preserve">{escapado}</t></is></c>'


def nome_de_aba(nome):
    """Nome aceito pelo Excel: até 31 caracteres, sem `[ ] : * ? / \\`, nem apóstrofo nas pontas."""
    limpo = re.sub(r"[\[\]:*?/\\\x00-\x1f]", " ", str(nome)).strip().strip("'").strip()
    return limpo[:TAMANHO_DO_NOME_DA_ABA] or "Planilha"


def escrever_xlsx(linhas, aba="Planilha"):
    """Bytes de um .xlsx com uma aba. Texto fica texto (nada vira fórmula, nem o que começa com `=`); número vira número."""
    corpo = "".join(
        f'<row r="{numero}">'
        + "".join(_celula_xlsx(f"{_letra_da_coluna(coluna)}{numero}", valor) for coluna, valor in enumerate(linha))
        + "</row>"
        for numero, linha in enumerate(linhas, start=1)
    )
    cabecalho = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    principal = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relacoes = "http://schemas.openxmlformats.org/package/2006/relationships"
    tipo_relacao = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    nome = _xml_seguro(nome_de_aba(aba)).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    partes = {
        "[Content_Types].xml": (
            f'{cabecalho}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'
        ),
        "_rels/.rels": (
            f'{cabecalho}<Relationships xmlns="{relacoes}"><Relationship Id="rId1" '
            f'Type="{tipo_relacao}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'{cabecalho}<workbook xmlns="{principal}" xmlns:r="{tipo_relacao}">'
            f'<sheets><sheet name="{nome}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{cabecalho}<Relationships xmlns="{relacoes}">'
            f'<Relationship Id="rId1" Type="{tipo_relacao}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{tipo_relacao}/styles" Target="styles.xml"/></Relationships>'
        ),
        "xl/styles.xml": (
            f'{cabecalho}<styleSheet xmlns="{principal}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font>'
            '</fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/>'
            '</fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        ),
        "xl/worksheets/sheet1.xml": f'{cabecalho}<worksheet xmlns="{principal}"><sheetData>{corpo}</sheetData></worksheet>',
    }
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as pacote:
        for caminho, texto in partes.items():
            pacote.writestr(caminho, texto)
    return saida.getvalue()
