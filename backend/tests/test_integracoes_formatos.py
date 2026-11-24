"""Leitura e escrita de txt, csv, xlsx, docx e pdf (`ferramentas/integracoes/formatos.py`), com arquivo hostil.

Os arquivos são montados aqui, na mão (zipfile e texto), sem biblioteca de escritório. Quando existe, o openpyxl é
usado só para conferir que o que escrevemos abre em outro programa.
"""

import io
import sys
import zipfile

import pytest
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import formatos
from ferramentas.integracoes.formatos import ArquivoInvalido

from .apoio_escritorio import docx_de_teste

PRINCIPAL = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def zip_com(partes, compressao=zipfile.ZIP_DEFLATED):
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", compressao) as pacote:
        for nome, conteudo in partes.items():
            pacote.writestr(nome, conteudo)
    return saida.getvalue()


def xlsx_a_mao(linhas_xml, textos=(), aba="Dados", tipos="<Types/>"):
    """Um xlsx com `<row>` escritos à mão e a tabela de textos compartilhados."""
    compartilhados = "".join(f"<si><t>{t}</t></si>" for t in textos)
    return zip_com({
        "[Content_Types].xml": tipos,
        "xl/workbook.xml": f'<workbook xmlns="{PRINCIPAL}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                           f'<sheets><sheet name="{aba}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst xmlns="{PRINCIPAL}">{compartilhados}</sst>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{PRINCIPAL}"><sheetData>{linhas_xml}</sheetData></worksheet>',
    })


def pdf_de_teste(paginas):
    """Um PDF mínimo e válido, uma linha de texto por página, montado na mão."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>"]
    filhos = " ".join(f"{3 + 2 * n} 0 R" for n in range(len(paginas)))
    objetos.append(f"<< /Type /Pages /Kids [{filhos}] /Count {len(paginas)} >>")
    for n, texto in enumerate(paginas):
        fluxo = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET"
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * n} 0 R "
            "/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>"
        )
        objetos.append(f"<< /Length {len(fluxo)} >>\nstream\n{fluxo}\nendstream")
    saida = bytearray(b"%PDF-1.4\n")
    posicoes = []
    for numero, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{corpo}\nendobj\n".encode()
    inicio_da_tabela = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicao in posicoes:
        saida += f"{posicao:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_da_tabela}\n%%EOF\n".encode()
    return bytes(saida)


# --- txt e csv ---------------------------------------------------------------------------------------------------------


def test_txt_le_utf8_com_bom_e_windows_1252_e_tira_caractere_de_controle():
    assert formatos.ler_txt("﻿olá\r\nmundo\x07".encode())["texto"] == "olá\nmundo"
    assert formatos.ler_txt("ação".encode("cp1252"))["texto"] == "ação"


def test_txt_corta_no_limite_e_avisa():
    lido = formatos.ler_txt(b"a" * 100, limite=10)
    assert lido == {"texto": "a" * 10, "truncado": True}


@pytest.mark.parametrize("conteudo", [b"abc\x00def", b"\x00" * 10])
def test_txt_com_byte_nulo_e_binario_nao_e_texto(conteudo):
    with pytest.raises(ArquivoInvalido):
        formatos.ler_txt(conteudo)
    with pytest.raises(ArquivoInvalido):
        formatos.ler_csv(conteudo)


def test_arquivo_de_texto_grande_demais_nem_e_lido():
    with pytest.raises(ArquivoInvalido):
        formatos.ler_txt(b"a" * (formatos.BYTES_NO_MAXIMO + 1))


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("a;b;c\n1;2;3", [["a", "b", "c"], ["1", "2", "3"]]),
        ("a,b,c\n1,2,3", [["a", "b", "c"], ["1", "2", "3"]]),
        ("a\tb\n1\t2", [["a", "b"], ["1", "2"]]),
        ('x;"y;z"\n"1\n2";3', [["x", "y;z"], ["1\n2", "3"]]),
    ],
)
def test_csv_descobre_o_separador_e_respeita_aspas(texto, esperado):
    assert formatos.ler_csv(texto.encode())["linhas"] == esperado


def test_csv_corta_linhas_colunas_e_celula_gigante():
    texto = "\n".join(",".join(str(c) for c in range(50)) for _ in range(10)) + "\n" + "x" * 5000
    lido = formatos.ler_csv(texto.encode(), limite_linhas=5, limite_colunas=3)
    assert len(lido["linhas"]) == 5 and all(len(linha) == 3 for linha in lido["linhas"]) and lido["truncado"] is True
    gigante = formatos.ler_csv(("a," + "y" * 5000).encode())["linhas"][0][1]
    assert len(gigante) == formatos.TAMANHO_DA_CELULA


# --- xlsx --------------------------------------------------------------------------------------------------------------


def test_xlsx_le_textos_compartilhados_numeros_booleanos_e_texto_na_celula():
    linhas = (
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
        '<row r="2"><c r="A2"><v>10</v></c><c r="B2" t="inlineStr"><is><t>texto &amp; mais</t></is></c><c r="C2" t="b"><v>1</v></c></row>'
    )
    lido = formatos.ler_xlsx(xlsx_a_mao(linhas, ["Fila", "Total"]))
    assert lido == {"abas": ["Dados"], "aba": "Dados", "linhas": [["Fila", "Total"], ["10", "texto & mais", "VERDADEIRO"]], "truncado": False}


def test_xlsx_formula_vale_o_ultimo_resultado_guardado_e_o_texto_da_formula_nunca_aparece():
    linhas = (
        '<row r="1"><c r="A1"><f>HYPERLINK("http://x.example","clique")</f><v>2</v></c>'
        '<c r="B1" t="str"><f>CONCATENATE("a","b")</f><v>ab</v></c><c r="C1"><f>1+1</f></c></row>'
    )
    lido = formatos.ler_xlsx(xlsx_a_mao(linhas))
    assert lido["linhas"] == [["2", "ab"]] and "HYPERLINK" not in str(lido)


def test_xlsx_celulas_afastadas_mantem_a_posicao_e_linha_em_branco_continua_em_branco():
    linhas = '<row r="1"><c r="A1"><v>1</v></c></row><row r="4"><c r="C4"><v>9</v></c></row>'
    assert formatos.ler_xlsx(xlsx_a_mao(linhas))["linhas"] == [["1"], [], [], ["", "", "9"]]


def test_xlsx_escolhe_a_aba_e_diz_quais_existem():
    pacote = formatos.escrever_xlsx([["a"]], "Primeira")
    assert formatos.ler_xlsx(pacote, aba="Primeira")["aba"] == "Primeira"
    with pytest.raises(ErroFerramenta) as erro:
        formatos.ler_xlsx(pacote, aba="Nada")
    assert erro.value.tipo_erro == "nao_encontrado" and "Primeira" in erro.value.mensagem


def test_xlsx_corta_linhas_e_colunas_e_diz_que_cortou():
    linhas = [[str(c) for c in range(40)] for _ in range(300)]
    lido = formatos.ler_xlsx(formatos.escrever_xlsx(linhas), limite_linhas=50, limite_colunas=10)
    assert len(lido["linhas"]) == 50 and all(len(l) == 10 for l in lido["linhas"]) and lido["truncado"] is True


def test_xlsx_com_macro_e_recusado_pelo_conteudo_e_pelo_nome():
    com_macro = zip_com({
        "[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<w/>", "xl/vbaProject.bin": "binario",
    })
    with pytest.raises(ArquivoInvalido) as erro:
        formatos.ler_xlsx(com_macro)
    assert erro.value.mensagem == formatos.MENSAGEM_COM_MACRO
    declarado = xlsx_a_mao("", tipos='<Types><Override ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>')
    with pytest.raises(ArquivoInvalido) as outro:
        formatos.ler_xlsx(declarado)
    assert outro.value.mensagem == formatos.MENSAGEM_COM_MACRO
    for nome in ("planilha.xlsm", "A.DOCM", "x.xlsb"):
        with pytest.raises(ArquivoInvalido):
            formatos.conferir_nome(nome)


@pytest.mark.parametrize(
    "xml",
    [
        '<!DOCTYPE x [<!ENTITY a "bomba">]><worksheet xmlns="' + PRINCIPAL + '"><sheetData/></worksheet>',
        '<!doctype x SYSTEM "http://invasor.example/x.dtd"><worksheet xmlns="' + PRINCIPAL + '"/>',
        '<?xml version="1.0"?><!ENTITY b SYSTEM "file:///etc/passwd"><worksheet xmlns="' + PRINCIPAL + '"/>',
    ],
)
def test_xml_com_doctype_ou_entidade_nao_e_interpretado(xml):
    pacote = xlsx_a_mao("")
    with zipfile.ZipFile(io.BytesIO(pacote)) as original:
        partes = {nome: original.read(nome) for nome in original.namelist()}
    partes["xl/worksheets/sheet1.xml"] = xml
    with pytest.raises(ArquivoInvalido) as erro:
        formatos.ler_xlsx(zip_com(partes))
    assert "bomba" not in erro.value.mensagem and "passwd" not in erro.value.mensagem


def test_zip_bomb_e_recusado_pelo_tamanho_descompactado_sem_descompactar():
    bomba = zip_com({
        "[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<w/>",
        "xl/worksheets/sheet1.xml": b"0" * (formatos.BYTES_DA_PARTE_NO_MAXIMO + 1),
    })
    assert len(bomba) < formatos.BYTES_NO_MAXIMO  # cabe no limite do arquivo: o que pesa é o descompactado
    with pytest.raises(ArquivoInvalido) as erro:
        formatos.ler_xlsx(bomba)
    assert "grande demais" in erro.value.mensagem
    varias = zip_com({f"parte{n}.xml": b"0" * 10_000_000 for n in range(3)})
    with pytest.raises(ArquivoInvalido):
        formatos.ler_docx(varias)


def test_zip_que_mente_no_tamanho_declarado_e_lido_com_teto():
    pacote = bytearray(zip_com({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": b"0" * 40_000_000}))
    tamanho_real = (40_000_000).to_bytes(4, "little")
    falso = (100).to_bytes(4, "little")
    for sinal, deslocamento in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        posicao = 0
        while (posicao := pacote.find(sinal, posicao)) != -1:
            if pacote[posicao + deslocamento : posicao + deslocamento + 4] == tamanho_real:
                pacote[posicao + deslocamento : posicao + deslocamento + 4] = falso
            posicao += 4
    assert len(pacote) < formatos.BYTES_NO_MAXIMO
    with pytest.raises(ArquivoInvalido):
        formatos.ler_xlsx(bytes(pacote))


def test_zip_com_muitas_partes_e_recusado():
    with pytest.raises(ArquivoInvalido):
        formatos.ler_xlsx(zip_com({f"p{n}.xml": "x" for n in range(formatos.PARTES_NO_MAXIMO + 1)}))


@pytest.mark.parametrize("nome", ["../fora.xml", "/etc/passwd", "a/../../b.xml", "..\\fora.xml"])
def test_zip_com_caminho_que_sai_da_pasta_e_recusado(nome):
    with pytest.raises(ArquivoInvalido):
        formatos.ler_xlsx(zip_com({"[Content_Types].xml": "<Types/>", nome: "x"}))


@pytest.mark.parametrize("conteudo", [b"", b"nao e um zip", b"PK\x03\x04quebrado", b"PK\x05\x06" + b"\x00" * 18])
def test_arquivo_que_nao_e_zip_ou_esta_quebrado_vira_arquivo_invalido(conteudo):
    for leitor in (formatos.ler_xlsx, formatos.ler_docx):
        with pytest.raises(ArquivoInvalido) as erro:
            leitor(conteudo)
        assert erro.value.tipo_erro == "parametro_invalido" and "nao e um zip" not in erro.value.mensagem


def test_zip_com_parte_criptografada_e_recusado():
    pacote = bytearray(formatos.escrever_xlsx([["a"]]))
    for sinal in (b"PK\x03\x04", b"PK\x01\x02"):  # liga o bit "criptografado" nos cabeçalhos local e central
        posicao = 0
        while (posicao := pacote.find(sinal, posicao)) != -1:
            deslocamento = posicao + (6 if sinal == b"PK\x03\x04" else 8)
            pacote[deslocamento] |= 0x1
            posicao += 4
    with pytest.raises(ArquivoInvalido):
        formatos.ler_xlsx(bytes(pacote))


def test_xlsx_com_indice_de_texto_fora_da_tabela_nao_estoura():
    with pytest.raises(ArquivoInvalido):
        formatos.ler_xlsx(xlsx_a_mao('<row r="1"><c r="A1" t="s"><v>99</v></c></row>', ["unico"]))


# --- docx --------------------------------------------------------------------------------------------------------------


def test_docx_le_paragrafos_e_tabela_com_tabulacao():
    lido = formatos.ler_docx(docx_de_teste(["Título", "Corpo do texto."], [["a", "b"], ["c", "d"]]))
    assert lido == {"texto": "Título\nCorpo do texto.\na\tb\nc\td", "truncado": False}


def test_docx_corta_no_limite_e_avisa():
    lido = formatos.ler_docx(docx_de_teste(["palavra " * 100] * 10), limite=300)
    assert len(lido["texto"]) <= 300 and lido["truncado"] is True


def test_docx_com_macro_ou_doctype_e_recusado():
    base = {"[Content_Types].xml": "<Types/>", "word/document.xml": '<w:document xmlns:w="urn:w"><w:body/></w:document>'}
    with pytest.raises(ArquivoInvalido):
        formatos.ler_docx(zip_com({**base, "word/vbaProject.bin": "x"}))
    with pytest.raises(ArquivoInvalido):
        formatos.ler_docx(zip_com({**base, "word/document.xml": '<!DOCTYPE d [<!ENTITY e "x">]><w:document xmlns:w="urn:w"/>'}))
    with pytest.raises(ArquivoInvalido):
        formatos.ler_docx(zip_com({"[Content_Types].xml": "<Types/>"}))  # sem word/document.xml


def test_docx_nao_segue_link_nem_objeto_incorporado():
    corpo = '<w:p><w:hyperlink><w:r><w:t>clique</w:t></w:r></w:hyperlink></w:p><w:p><w:r><w:object>x</w:object><w:t>fim</w:t></w:r></w:p>'
    pacote = zip_com({
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": f'<w:document xmlns:w="urn:w"><w:body>{corpo}</w:body></w:document>',
        "word/_rels/document.xml.rels": '<Relationships><Relationship Target="http://invasor.example/x" TargetMode="External"/></Relationships>',
    })
    assert formatos.ler_docx(pacote)["texto"] == "clique\nfim"


# --- pdf ---------------------------------------------------------------------------------------------------------------


def test_pdf_le_o_texto_das_paginas_e_respeita_o_limite_de_paginas():
    pytest.importorskip("pypdf")
    pdf = pdf_de_teste([f"Pagina {letra}" for letra in "ABCDE"])
    lido = formatos.ler_pdf(pdf, limite_paginas=3)
    assert lido["paginas"] == 5 and lido["truncado"] is True
    assert "Pagina A" in lido["texto"] and "Pagina C" in lido["texto"] and "Pagina D" not in lido["texto"]
    assert formatos.ler_pdf(pdf)["truncado"] is False


def test_pdf_corta_o_texto_no_limite_de_caracteres():
    pytest.importorskip("pypdf")
    lido = formatos.ler_pdf(pdf_de_teste(["x" * 500, "y" * 500]), limite=100)
    assert len(lido["texto"]) == 100 and lido["truncado"] is True


@pytest.mark.parametrize("conteudo", [b"%PDF-1.4\nlixo sem estrutura", b"texto qualquer", b"%PDF-" + b"\x00" * 50, b""])
def test_pdf_quebrado_ou_falso_vira_arquivo_invalido(conteudo):
    pytest.importorskip("pypdf")
    with pytest.raises(ArquivoInvalido):
        formatos.ler_pdf(conteudo)


def test_pdf_protegido_por_senha_e_recusado():
    pypdf = pytest.importorskip("pypdf")
    escritor = pypdf.PdfWriter()
    escritor.add_blank_page(100, 100)
    try:
        escritor.encrypt("senha", algorithm="RC4-128")
    except Exception:  # noqa: BLE001 - sem a biblioteca de criptografia neste ambiente
        pytest.skip("pypdf sem suporte a criptografia aqui")
    saida = io.BytesIO()
    escritor.write(saida)
    with pytest.raises(ArquivoInvalido):
        formatos.ler_pdf(saida.getvalue())


def test_sem_o_pypdf_instalado_a_ferramenta_diz_que_nao_le_pdf(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(ErroFerramenta) as erro:
        formatos.ler_pdf(b"%PDF-1.4\n")
    assert erro.value.tipo_erro == "integracao_indisponivel" and erro.value.mensagem == formatos.MENSAGEM_PDF_INDISPONIVEL


# --- escrita -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("=1+1", "'=1+1"), ("@SOMA(A1)", "'@SOMA(A1)"), ("+cmd|x", "'+cmd|x"), ("-2+3", "'-2+3"), ("-5", "-5"), ("+5", "+5"),
     ("12/10", "12/10"), ("texto", "texto"), ("a\nb\rc", "a b c"), (None, ""), (7, "7")],
)
def test_celula_com_cara_de_formula_ganha_apostrofo(valor, esperado):
    assert formatos.celula_como_texto(valor) == esperado


def test_csv_escrito_abre_no_excel_em_portugues_e_nao_carrega_formula():
    conteudo = formatos.escrever_csv([["Fila", "Obs"], ["Recebimento", "=HYPERLINK(\"http://x.example\")"], ["a;b", 'c"d']])
    assert conteudo.startswith(b"\xef\xbb\xbf")
    lido = formatos.ler_csv(conteudo)["linhas"]
    assert lido[1] == ["Recebimento", "'=HYPERLINK(\"http://x.example\")"] and lido[2] == ["a;b", 'c"d']


def test_xlsx_escrito_guarda_texto_como_texto_e_numero_como_numero():
    pacote = formatos.escrever_xlsx([["a", "007", "=1+1", "12/10"], ["1", "2.5", "-3", "x & <y>"]], "Dados")
    assert formatos.ler_xlsx(pacote)["linhas"] == [["a", "007", "=1+1", "12/10"], ["1", "2.5", "-3", "x & <y>"]]
    with zipfile.ZipFile(io.BytesIO(pacote)) as aberto:
        planilha = aberto.read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in planilha and '<c r="B1" t="inlineStr">' in planilha and '<c r="A2"><v>1</v></c>' in planilha


def test_xlsx_escrito_remove_caractere_ilegal_no_xml_e_limpa_o_nome_da_aba():
    pacote = formatos.escrever_xlsx([["a\x00b\x08c"]], "Aba/com:coisas?[*]" + "x" * 40)
    lido = formatos.ler_xlsx(pacote)
    assert lido["linhas"] == [["abc"]] and len(lido["aba"]) <= 31 and not set(lido["aba"]) & set("[]:*?/\\")
    assert formatos.nome_de_aba("''") == "Planilha" and formatos.nome_de_aba("") == "Planilha"


def test_xlsx_escrito_abre_no_openpyxl():
    openpyxl = pytest.importorskip("openpyxl")
    pacote = formatos.escrever_xlsx([["Fila", "Total"], ["Recebimento", "7"], ["=1+1", "2.5"]], "Teste")
    folha = openpyxl.load_workbook(io.BytesIO(pacote)).active
    assert [[c.value for c in linha] for linha in folha.iter_rows()] == [["Fila", "Total"], ["Recebimento", 7], ["=1+1", 2.5]]
    assert folha["A3"].data_type == "s"  # texto, não fórmula


def test_xlsx_do_openpyxl_com_formula_e_lido_sem_calcular():
    openpyxl = pytest.importorskip("openpyxl")
    livro = openpyxl.Workbook()
    folha = livro.active
    folha.append(["a", "b"])
    folha.append([1, "=A2+1"])
    saida = io.BytesIO()
    livro.save(saida)
    assert formatos.ler_xlsx(saida.getvalue())["linhas"] == [["a", "b"], ["1"]]


def test_txt_escrito_tira_controle_e_normaliza_quebra_de_linha():
    assert formatos.escrever_txt("a\r\nb\x00c") == b"a\nbc"
