"""Microsoft 365: agenda do Outlook, OneDrive e Excel e Word da conta de quem pede, nas sete ferramentas de `documentos_e_agenda/`.

O cliente é o de verdade; só os servidores são falsos (`apoio_escritorio.py`, no formato do Microsoft Graph): um para o
login e o Graph e outro, em outra porta, para o download temporário que o Graph indica com um redirecionamento.
"""

import io
import json
import logging
import threading
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from ferramentas import catalogo, confirmacoes
from ferramentas.confirmacoes import MENSAGEM_EFEITO_INCERTO
from ferramentas.integracoes import credenciais, formatos
from ferramentas.integracoes.conector import FALHAS_PARA_PAUSAR
from ferramentas.integracoes.google_workspace.conector import CONECTOR as GOOGLE
from ferramentas.integracoes.microsoft_365 import conector as microsoft
from ferramentas.integracoes.microsoft_365.conector import CONECTOR as MICROSOFT
from ferramentas.integracoes.registro import estado_integracoes

from .apoio_escritorio import (
    MICROSOFT_CLIENT_SECRET,
    MICROSOFT_TENANT,
    DownloadDeTeste,
    MicrosoftDeTeste,
    ServidorDeEscritorio,
    ambiente_da_microsoft,
    ambiente_do_google,
    resposta_json,
)
from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)

EVENTOS, ARQUIVOS, LER_PLANILHA, LER_DOCUMENTO = (
    "listar_eventos_agenda", "buscar_arquivos", "ler_planilha", "ler_documento",
)
CRIAR_EVENTO, ADICIONAR_LINHA, CRIAR_PLANILHA = "criar_evento_agenda", "adicionar_linha_planilha", "criar_planilha"
AGENTE = (EVENTOS, ARQUIVOS, LER_PLANILHA, LER_DOCUMENTO, CRIAR_EVENTO, ADICIONAR_LINHA, CRIAR_PLANILHA)
PLANILHA, DOCUMENTO = "01PLANILHAAAA", "01DOCUMENTOAA"
ANA_ID = "F0001"


@pytest.fixture(scope="module")
def engine():
    return mundo_do_mock()


@pytest.fixture(autouse=True)
def estado_limpo(engine):
    limpar_estado()
    yield
    limpar_estado()


@pytest.fixture
def ana(engine):
    return usuario_do_diretorio(engine, FUNCIONARIO_DO_CARGO["atendente_n1"])


@pytest.fixture
def servidor(monkeypatch):
    dados = MicrosoftDeTeste()
    with ServidorDeEscritorio(dados) as graph, ServidorDeEscritorio(DownloadDeTeste(dados)) as download:
        dados.url_de_download = download.url
        for nome, valor in ambiente_da_microsoft(graph).items():
            monkeypatch.setenv(nome, valor)
        graph.download = download
        yield graph, dados


def ligar_conta(dados, com_escrita=False, pessoa=ANA_ID):
    url = MICROSOFT.autorizar(pessoa, com_escrita=com_escrita)
    codigo, estado = dados.consentir(pessoa, url)
    return MICROSOFT.fluxo().concluir(pessoa, estado, codigo)


@pytest.fixture
def conta(servidor):
    ligar_conta(servidor[1])
    return servidor


@pytest.fixture
def conta_com_escrita(servidor):
    ligar_conta(servidor[1], com_escrita=True)
    return servidor


def usar(nome, argumentos, usuario):
    return catalogo.executar(nome, argumentos, usuario, AGENTE)


def dados_de(nome, argumentos, usuario):
    resposta = usar(nome, argumentos, usuario)
    assert resposta["status"] == "ok", resposta
    dados = resposta["dados"]
    return dados.get("conteudo_de_terceiros", dados)


def pedidos_ao_graph(servidor):
    return [p for p in servidor.pedidos if not p.rota.endswith("/token")]


def escritas(servidor):
    return [p for p in pedidos_ao_graph(servidor) if p.metodo != "GET"]


# --- OAuth da Microsoft ----------------------------------------------------------------------------------------------


def test_o_endereco_de_autorizacao_vai_ao_diretorio_da_empresa_com_leitura_e_offline_access(servidor):
    url = MICROSOFT.autorizar(ANA_ID)
    partes = urlsplit(url)
    consulta = {k: v[0] for k, v in parse_qs(partes.query).items()}
    assert partes.path == "/oauth2/v2.0/authorize" and consulta["code_challenge_method"] == "S256"
    assert set(consulta["scope"].split()) == {"Calendars.Read", "Files.Read", "offline_access"}
    assert consulta["response_mode"] == "query" and consulta["prompt"] == "select_account"
    assert MICROSOFT_CLIENT_SECRET not in url


def test_em_producao_o_endereco_inclui_o_tenant(monkeypatch):
    for nome, valor in ambiente_da_microsoft(type("S", (), {"url": "http://127.0.0.1:1"})()).items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.delenv("MICROSOFT_URL")
    assert urlsplit(MICROSOFT.autorizar(ANA_ID)).path == f"/{MICROSOFT_TENANT}/oauth2/v2.0/authorize"
    monkeypatch.delenv("MICROSOFT_TENANT")
    assert urlsplit(MICROSOFT.autorizar(ANA_ID)).path == "/organizations/oauth2/v2.0/authorize"


def test_escrita_pede_as_permissoes_de_escrita_sem_nenhuma_all(servidor):
    escopos = set(parse_qs(urlsplit(MICROSOFT.autorizar(ANA_ID, com_escrita=True)).query)["scope"][0].split())
    assert escopos == {"Calendars.Read", "Files.Read", "Calendars.ReadWrite", "Files.ReadWrite", "offline_access"}
    assert not any(e.endswith(".All") for e in escopos)


def test_os_escopos_devolvidos_com_o_prefixo_do_graph_sao_normalizados(servidor):
    credencial = ligar_conta(servidor[1])
    assert credencial.escopos == {"Calendars.Read", "Files.Read"}
    assert credencial.refresh_token and credencial.valida()


def test_a_renovacao_troca_o_token_de_renovacao_e_o_antigo_deixa_de_valer(servidor):
    _, dados = servidor
    antiga = ligar_conta(dados)
    credenciais.provedor().guardar(ANA_ID, "microsoft_365", credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, antiga.refresh_token))
    credenciais.provedor().token_de_acesso(ANA_ID, MICROSOFT.fluxo(), {"Calendars.Read"})
    guardada = credenciais.provedor().ler(ANA_ID, "microsoft_365")
    assert guardada.refresh_token != antiga.refresh_token and guardada.escopos == antiga.escopos
    assert antiga.refresh_token not in dados.renovacoes and guardada.refresh_token in dados.renovacoes


def test_sem_segredo_do_app_o_pedido_de_token_segue_sem_client_secret(servidor, monkeypatch):
    srv, dados = servidor
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "")
    ligar_conta(dados)
    troca = next(p for p in srv.pedidos if p.rota.endswith("/token"))
    assert "client_secret" not in troca.formulario and troca.formulario["client_id"]


def test_desligar_nao_chama_revogacao_porque_a_microsoft_nao_tem(servidor):
    srv, dados = servidor
    ligar_conta(dados)
    antes = len(srv.pedidos)
    MICROSOFT.fluxo().desligar(ANA_ID)
    assert len(srv.pedidos) == antes and not MICROSOFT.conta_ligada(ANA_ID)


@pytest.mark.parametrize(
    "variavel",
    ["MICROSOFT_CLIENT_ID", "MICROSOFT_TENANT", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_REDIRECT_URI", "ESCRITORIO_DOMINIOS"],
)
def test_configuracao_errada_aponta_so_a_variavel_sem_o_valor(servidor, monkeypatch, variavel):
    monkeypatch.setenv(variavel, "valor com espaço e ' aspas")
    problema = MICROSOFT.problema_de_configuracao()
    assert variavel in problema and "valor com espaço" not in problema


def test_testar_confere_o_app_sem_conta(servidor):
    srv, _ = servidor
    assert "aceitou o app" in MICROSOFT.testar()
    assert [p.rota for p in srv.pedidos] == ["/oauth2/v2.0/token"]


# --- agenda ----------------------------------------------------------------------------------------------------------


def test_lista_eventos_convertendo_utc_para_brasilia_com_dia_inteiro_e_sem_cancelados(conta, ana):
    servidor, dados = conta
    dados.evento(ANA_ID, "Reunião de plantão", "2026-10-16T17:00:00", "2026-10-16T18:00:00",
                 location={"displayName": "Sala 2"}, attendees=[{}, {}])
    dados.evento(ANA_ID, "Treinamento de cobrança", "2026-10-15T12:00:00", "2026-10-15T13:30:00")
    dados.evento(ANA_ID, "Feriado da empresa", "2026-10-17T00:00:00", "2026-10-18T00:00:00", dia_inteiro=True)
    cancelado = dados.evento(ANA_ID, "Cancelada", "2026-10-15T14:00:00", "2026-10-15T15:00:00")
    cancelado["isCancelled"] = True
    resultado = dados_de(EVENTOS, {}, ana)
    assert [e["titulo"] for e in resultado["eventos"]] == ["Treinamento de cobrança", "Reunião de plantão", "Feriado da empresa"]
    treino, reuniao, feriado = resultado["eventos"]
    assert (treino["inicio"], treino["fim"]) == ("2026-10-15T09:00", "2026-10-15T10:30")  # 12h UTC = 9h em Brasília
    assert reuniao["local"] == "Sala 2" and reuniao["convidados"] == 2
    assert (feriado["inicio"], feriado["fim"], feriado["dia_inteiro"]) == ("2026-10-17", "2026-10-18", True)
    assert resultado["fonte"] == MICROSOFT.fonte_real and resultado["truncado"] is False
    chamada = pedidos_ao_graph(servidor)[-1]
    assert chamada.token == credenciais.provedor().ler(ANA_ID, "microsoft_365").access_token
    assert chamada.cabecalhos["prefer"] == 'outlook.timezone="UTC"'


def test_o_limite_corta_a_lista_e_dado_pessoal_no_titulo_sai_mascarado(conta, ana):
    _, dados = conta
    dados.evento(ANA_ID, "Ligar para 123.456.789-09", "2026-10-15T12:00:00", "2026-10-15T13:00:00")
    for hora in (14, 15):
        dados.evento(ANA_ID, f"Evento {hora}", f"2026-10-15T{hora}:00:00", f"2026-10-15T{hora}:30:00")
    resultado = dados_de(EVENTOS, {"limite": 2}, ana)
    assert resultado["total"] == 2 and resultado["truncado"] is True
    assert "123.456.789-09" not in json.dumps(resultado)


def test_cria_o_evento_em_utc_com_transaction_id_convidados_liberados_e_assinatura(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(CRIAR_EVENTO, {
        "titulo": "Alinhamento", "data": "2026-10-20", "hora_inicio": "14:30", "duracao_minutos": 45,
        "convidados": "bia@stone.example", "local": "Sala 3", "descricao": "Pauta do mês",
    }, ana)
    assert previa["servico"] == "Microsoft 365" and pedidos_ao_graph(servidor) == []
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["status"] == "ok" and resultado["dados"]["fonte"] == MICROSOFT.fonte_real
    (criado,) = dados.eventos[ANA_ID]
    assert criado["start"] == {"dateTime": "2026-10-20T17:30:00", "timeZone": "UTC"}  # 14h30 em Brasília
    assert criado["end"]["dateTime"] == "2026-10-20T18:15:00" and len(criado["transactionId"]) == 32
    assert criado["attendees"] == [{"emailAddress": {"address": "bia@stone.example"}, "type": "required"}]
    assert criado["location"] == {"displayName": "Sala 3"}
    assert "Pauta do mês" in criado["body"]["content"] and "Ana" in criado["body"]["content"]


def test_convidado_de_fora_nao_vira_previa_e_a_repeticao_do_pedido_nao_duplica(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    fora = usar(CRIAR_EVENTO, {"titulo": "x", "data": "2026-10-20", "hora_inicio": "10:00", "convidados": "a@externo.example"}, ana)
    assert fora["tipo_erro"] == "parametro_invalido" and pedidos_ao_graph(servidor) == []
    previa = dados_de(CRIAR_EVENTO, {"titulo": "Único", "data": "2026-10-20", "hora_inicio": "10:00"}, ana)
    confirmacoes.confirmar(previa["confirmacao_id"], ana)
    repeticao = servidor.pedidos[-1]
    dados(repeticao)  # o mesmo transactionId de novo, como numa repetição de rede
    assert len(dados.eventos[ANA_ID]) == 1


def test_409_na_criacao_do_evento_conta_como_criado(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(CRIAR_EVENTO, {"titulo": "Repetido", "data": "2026-10-20", "hora_inicio": "10:00"}, ana)
    dados.proximas.append(resposta_json({"error": {"code": "ErrorItemExists", "message": "exists"}}, 409))
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["status"] == "ok" and servidor is not None


# --- conta, escopo e recusas -----------------------------------------------------------------------------------------


def test_sem_conta_ligada_manda_conectar_sem_chamar_o_graph(servidor, ana):
    resposta = usar(EVENTOS, {}, ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel" and "não está ligada" in resposta["mensagem"]
    assert pedidos_ao_graph(servidor[0]) == []


def test_escrita_sem_a_permissao_de_escrita_pede_para_reconectar_e_nada_e_escrito(conta, ana):
    servidor, dados = conta
    previa = dados_de(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": "a|b"}, ana)
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["tipo_erro"] == "integracao_indisponivel" and "permissão de escrita" in resultado["mensagem"]
    assert escritas(servidor) == [] and len(dados.itens[PLANILHA]["abas"]["Resumo"]) == 3


@pytest.mark.parametrize("quando", ["permissao_do_app", "item_sem_acesso", "limite", "item_inexistente"])
def test_recusas_do_graph_viram_os_tipos_de_erro_padronizados(conta, ana, quando):
    _, dados = conta
    dados.proximas.append({
        "permissao_do_app": dados.erro_de_escopo(), "item_sem_acesso": dados.erro_sem_acesso(),
        "limite": dados.erro_de_limite(), "item_inexistente": dados._nao_achou(),
    }[quando])
    resposta = usar(LER_PLANILHA, {"id_arquivo": PLANILHA}, ana)
    esperado = {
        "permissao_do_app": "integracao_indisponivel", "item_sem_acesso": "permissao_negada",
        "limite": "integracao_indisponivel", "item_inexistente": "nao_encontrado",
    }[quando]
    assert resposta["tipo_erro"] == esperado
    if quando == "limite":
        assert "9 segundos" in resposta["mensagem"] and MICROSOFT.saude() != "pausada"


def test_token_recusado_no_meio_renova_e_repete_uma_vez(conta, ana):
    servidor, dados = conta
    atual = credenciais.provedor().ler(ANA_ID, "microsoft_365")
    dados.vencer(atual.access_token)
    dados_de(EVENTOS, {}, ana)
    renovacoes = [p for p in servidor.pedidos if p.formulario and p.formulario.get("grant_type") == "refresh_token"]
    assert len(renovacoes) == 1
    assert credenciais.provedor().ler(ANA_ID, "microsoft_365").access_token != atual.access_token


def test_concessao_revogada_pede_para_ligar_de_novo(conta, ana):
    _, dados = conta
    atual = credenciais.provedor().ler(ANA_ID, "microsoft_365")
    dados.vencer(atual.access_token)
    dados.renovacoes.clear()
    resposta = usar(EVENTOS, {}, ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel" and not MICROSOFT.conta_ligada(ANA_ID)


def test_tres_falhas_pausam_a_integracao_e_o_erro_nao_vaza_endereco_nem_token(conta, ana, caplog):
    servidor, _ = conta
    caplog.set_level(logging.DEBUG)
    servidor.responder = lambda pedido: (503, {}, b"detalhe interno")
    respostas = [usar(EVENTOS, {}, ana) for _ in range(3)]
    assert {r["tipo_erro"] for r in respostas} == {"integracao_indisponivel"}
    assert MICROSOFT.saude() == "pausada"
    antes = len(servidor.pedidos)
    usar(EVENTOS, {}, ana)
    assert len(servidor.pedidos) == antes
    token = credenciais.provedor().ler(ANA_ID, "microsoft_365").access_token
    texto = json.dumps(respostas, ensure_ascii=False) + caplog.text
    for segredo in (token, MICROSOFT_CLIENT_SECRET, servidor.url, "detalhe interno"):
        assert segredo not in texto
    assert {i["nome"]: i["saude"] for i in estado_integracoes()}["microsoft_365"] == "pausada"


# --- OneDrive --------------------------------------------------------------------------------------------------------


def test_busca_arquivos_por_nome_e_filtra_por_tipo(conta, ana):
    servidor, _ = conta
    todos = dados_de(ARQUIVOS, {"consulta": "teste"}, ana)
    assert {(a["titulo"], a["tipo"]) for a in todos["arquivos"]} == {
        ("Acompanhamento de testes.xlsx", "planilha"), ("Guia de testes.docx", "documento"),
        ("Relatórios de teste", "pasta"),
    }
    so_documentos = dados_de(ARQUIVOS, {"consulta": "teste", "tipo": "documento"}, ana)
    assert [a["id_arquivo"] for a in so_documentos["arquivos"]] == [DOCUMENTO]
    assert pedidos_ao_graph(servidor)[-1].rota == "/v1.0/me/drive/root/search(q='teste')"


def test_a_aspa_simples_da_busca_e_dobrada_e_o_resto_e_codificado(conta, ana):
    servidor, _ = conta
    dados_de(ARQUIVOS, {"consulta": "joao's #a/b?c"}, ana)
    caminho = pedidos_ao_graph(servidor)[-1].caminho.split("?")[0]
    assert caminho == "/v1.0/me/drive/root/search(q='joao''s%20%23a%2Fb%3Fc')"


def test_le_a_planilha_do_excel_sem_as_colunas_vazias_do_retangulo(conta, ana):
    servidor, _ = conta
    resultado = dados_de(LER_PLANILHA, {"id_arquivo": PLANILHA}, ana)
    assert resultado["titulo"] == "Acompanhamento de testes" and resultado["aba"] == "Resumo"
    assert resultado["linhas"] == [["Semana", "Abertos", "Fechados"], ["28/09", "10", "8"], ["05/10", "12", "11"]]
    assert resultado["truncado"] is False
    assert "range(address='A1:Z31')" in unquote_rota(pedidos_ao_graph(servidor)[-1])


def unquote_rota(pedido):
    from urllib.parse import unquote

    return unquote(pedido.rota)


def test_aba_pelo_nome_com_espaco_intervalo_e_aba_inexistente(conta, ana):
    resultado = dados_de(LER_PLANILHA, {"id_arquivo": PLANILHA, "aba": "Outra aba", "intervalo": "A1:B2"}, ana)
    assert resultado["linhas"] == [["Fila", "Total"], ["Recebimento", "7"]]
    resposta = usar(LER_PLANILHA, {"id_arquivo": PLANILHA, "aba": "Nada"}, ana)
    assert resposta["tipo_erro"] == "nao_encontrado" and "Resumo" not in resposta["mensagem"]
    assert resposta["dados"] == {"conteudo_de_terceiros": {"abas": ["Resumo", "Outra aba", "Vazia"]}}


def test_planilha_longa_vem_truncada_e_celula_com_cpf_sai_mascarada(conta, ana):
    _, dados = conta
    dados.itens[PLANILHA]["abas"]["Resumo"] = [["123.456.789-09", "maria@empresa.example"]] + [["Linha", str(n)] for n in range(1, 61)]
    resultado = dados_de(LER_PLANILHA, {"id_arquivo": PLANILHA, "limite": 10}, ana)
    assert len(resultado["linhas"]) == 10 and resultado["truncado"] is True
    assert "123.456.789-09" not in json.dumps(resultado) and "maria@empresa.example" not in json.dumps(resultado)


def test_arquivo_que_nao_e_planilha_ou_documento_do_office_e_recusado_com_clareza(conta, ana):
    assert usar(LER_PLANILHA, {"id_arquivo": DOCUMENTO}, ana)["tipo_erro"] == "parametro_invalido"
    assert usar(LER_DOCUMENTO, {"id_arquivo": PLANILHA}, ana)["tipo_erro"] == "parametro_invalido"
    pasta = usar(LER_DOCUMENTO, {"id_arquivo": "01PASTAAAAAAA"}, ana)
    assert pasta["tipo_erro"] == "parametro_invalido" and "documento do Word" in pasta["mensagem"]


def test_arquivo_de_outra_pessoa_nao_e_encontrado(conta, ana):
    _, dados = conta
    dados.itens[PLANILHA]["dono"] = "F0099"
    assert usar(LER_PLANILHA, {"id_arquivo": PLANILHA}, ana)["tipo_erro"] == "nao_encontrado"


# --- Word: download em outro servidor --------------------------------------------------------------------------------


def test_le_o_docx_seguindo_o_redirecionamento_sem_mandar_o_token_ao_outro_servidor(conta, ana):
    servidor, _ = conta
    resultado = dados_de(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)
    assert resultado["titulo"] == "Guia de testes"
    assert "Primeiro parágrafo do guia." in resultado["texto"] and "Abrir\tAna" in resultado["texto"]
    token = credenciais.provedor().ler(ANA_ID, "microsoft_365").access_token
    assert any(p.token == token and p.rota.endswith("/content") for p in servidor.pedidos)
    (baixado,) = servidor.download.pedidos
    assert "authorization" not in baixado.cabecalhos and token not in str(baixado)


def test_redirecionamento_para_dominio_nao_liberado_e_recusado(conta, ana):
    servidor, dados = conta
    dados.url_de_download = "http://localhost:1"  # outro nome de host: fora da lista de domínios de download
    resposta = usar(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)
    assert resposta["tipo_erro"] == "integracao_indisponivel"
    assert servidor.download.pedidos == []


def test_docx_com_macro_ou_entidade_xml_malicioso_nao_e_lido(conta, ana):
    _, dados = conta
    malicioso = formatos_com(
        "word/document.xml",
        '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x "bomba">]><w:document xmlns:w="urn:w"><w:body/></w:document>',
    )
    dados.itens[DOCUMENTO]["docx"] = malicioso
    resposta = usar(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)
    assert resposta["tipo_erro"] == "parametro_invalido" and "bomba" not in json.dumps(resposta)
    dados.itens[DOCUMENTO]["docx"] = formatos_com("word/vbaProject.bin", "x")
    assert usar(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)["tipo_erro"] == "parametro_invalido"


def formatos_com(parte_extra, conteudo):
    import zipfile

    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as pacote:
        pacote.writestr("[Content_Types].xml", "<Types/>")
        if parte_extra != "word/document.xml":
            pacote.writestr("word/document.xml", '<w:document xmlns:w="urn:w"><w:body/></w:document>')
        pacote.writestr(parte_extra, conteudo)
    return saida.getvalue()


def test_documento_grande_demais_nem_e_baixado(conta, ana):
    servidor, dados = conta
    dados.itens[DOCUMENTO]["docx"] = b"x" * (formatos.BYTES_NO_MAXIMO + 1)
    assert usar(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)["tipo_erro"] == "parametro_invalido"
    assert servidor.download.pedidos == []


# --- escrita no Excel ------------------------------------------------------------------------------------------------


def test_adiciona_a_linha_abaixo_da_ultima_com_formato_texto_e_sem_virar_data_nem_formula(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": "12/10 | 14 | =HYPERLINK(\"x\")", "aba": "Resumo"}, ana)
    assert previa["planilha"] == "Acompanhamento de testes" and previa["valores"] == ["12/10", "14", '=HYPERLINK("x")']
    assert len(dados.itens[PLANILHA]["abas"]["Resumo"]) == 3 and escritas(servidor) == []
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["dados"] == {"aba": "Resumo", "linhas_adicionadas": 1, "fonte": MICROSOFT.fonte_real}
    assert dados.itens[PLANILHA]["abas"]["Resumo"][3] == ["12/10", 14, '=HYPERLINK("x")']  # texto, número e texto
    formato, valores = escritas(servidor)
    assert formato.corpo == {"numberFormat": [["@", "General", "General"]]}
    assert valores.corpo == {"values": [["12/10", 14, "'=HYPERLINK(\"x\")"]]}
    assert unquote_rota(valores).endswith("worksheets/Resumo/range(address='A4:C4')")
    assert dados_de(LER_PLANILHA, {"id_arquivo": PLANILHA}, ana)["linhas"][3][:2] == ["12/10", "14"]


def test_linha_so_com_numeros_nao_manda_formato_e_a_aba_vazia_comeca_na_linha_um(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": "1 | 2.5", "aba": "Vazia"}, ana)
    confirmacoes.confirmar(previa["confirmacao_id"], ana)
    (unica,) = escritas(servidor)
    assert unica.corpo == {"values": [[1, 2.5]]} and unquote_rota(unica).endswith("range(address='A1:B1')")
    assert dados.itens[PLANILHA]["abas"]["Vazia"] == [[1, 2.5]]


def test_aba_inexistente_na_linha_lista_as_abas_e_nada_e_escrito(conta_com_escrita, ana):
    servidor, _ = conta_com_escrita
    resposta = usar(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": "a|b", "aba": "Nada"}, ana)
    assert resposta["tipo_erro"] == "nao_encontrado" and escritas(servidor) == []


def test_cria_a_planilha_como_xlsx_sem_sobrescrever_e_devolve_o_id(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    argumentos = {"titulo": "Fechamento: out/2026?", "colunas": "Fila | Total", "linhas": "Recebimento | 7\nCobrança | =1+1"}
    previa = dados_de(CRIAR_PLANILHA, argumentos, ana)
    assert previa["tamanho"] == "2 linhas de dados, 2 colunas" and escritas(servidor) == []
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["status"] == "ok" and resultado["dados"]["id_arquivo"] in dados.itens
    criada = dados.itens[resultado["dados"]["id_arquivo"]]
    assert criada["nome"] == "Fechamento out 2026.xlsx"
    (escrita,) = escritas(servidor)
    assert escrita.consulta == {"@microsoft.graph.conflictBehavior": "rename"}
    assert escrita.cabecalhos["content-type"] == formatos.TIPO_XLSX
    assert next(iter(criada["abas"].values())) == [["Fila", "Total"], ["Recebimento", "7"], ["Cobrança", "=1+1"]]
    segunda = dados_de(CRIAR_PLANILHA, argumentos, ana)
    outra = confirmacoes.confirmar(segunda["confirmacao_id"], ana)
    assert outra["dados"]["id_arquivo"] != resultado["dados"]["id_arquivo"]
    assert dados_de(LER_PLANILHA, {"id_arquivo": resultado["dados"]["id_arquivo"]}, ana)["linhas"][1] == ["Recebimento", "7"]


@pytest.mark.parametrize("titulo", ["../../etc/passwd", "a/b\\c:d", "***", "x" * 100, "  .. "])
def test_titulo_estranho_vira_nome_de_arquivo_seguro(conta_com_escrita, ana, titulo):
    servidor, _ = conta_com_escrita
    previa = dados_de(CRIAR_PLANILHA, {"titulo": titulo, "colunas": "a|b"}, ana)
    confirmacoes.confirmar(previa["confirmacao_id"], ana)
    (escrita,) = escritas(servidor)
    caminho = unquote_rota(escrita).removeprefix("/v1.0/me/drive/root:/").removesuffix(":/content")
    assert "/" not in caminho and ".." not in caminho and caminho.endswith(".xlsx") and len(caminho) <= 105


def test_a_planilha_enviada_abre_em_outro_programa(conta_com_escrita, ana):
    openpyxl = pytest.importorskip("openpyxl")
    servidor, _ = conta_com_escrita
    previa = dados_de(CRIAR_PLANILHA, {"titulo": "Teste", "colunas": "Fila|Total", "linhas": "Recebimento|7"}, ana)
    confirmacoes.confirmar(previa["confirmacao_id"], ana)
    (envio,) = escritas(servidor)
    linhas = [[c.value for c in linha] for linha in openpyxl.load_workbook(io.BytesIO(envio.bruto)).active.iter_rows()]
    assert linhas == [["Fila", "Total"], ["Recebimento", 7]]


# --- duas contas e o modo simulado -----------------------------------------------------------------------------------


def test_com_google_e_microsoft_ligados_o_agente_precisa_dizer_qual(servidor, ana, monkeypatch):
    for nome, valor in ambiente_do_google(servidor[0]).items():
        monkeypatch.setenv(nome, valor)
    ligar_conta(servidor[1])
    assert dados_de(EVENTOS, {}, ana)["fonte"] == MICROSOFT.fonte_real  # só a Microsoft tem conta ligada
    assert GOOGLE.conta_ligada(ANA_ID) is False
    assert usar(EVENTOS, {"servico": "google"}, ana)["tipo_erro"] == "integracao_indisponivel"  # conta Google não ligada


def test_modo_simulado_responde_com_as_mesmas_chaves_e_sem_rede(monkeypatch, ana):
    monkeypatch.setenv("MICROSOFT_MODO", "simulado")
    eventos = dados_de(EVENTOS, {}, ana)
    assert "simulado" in eventos["fonte"] and eventos["eventos"]
    planilha = dados_de(LER_PLANILHA, {"id_arquivo": "SIM-PLAN-CHAMADOS"}, ana)
    assert set(planilha) == {"titulo", "aba", "intervalo", "linhas", "truncado", "fonte"}
    previa = dados_de(ADICIONAR_LINHA, {"id_arquivo": "SIM-PLAN-CHAMADOS", "valores": "novo | 1"}, ana)
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["status"] == "ok" and "Modo de demonstração" in resultado["mensagem"]


def test_sem_configuracao_o_conector_fica_desligado(monkeypatch):
    monkeypatch.delenv("MICROSOFT_MODO", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    assert MICROSOFT.saude() == "desligada"
    assert microsoft.ESCOPOS_DE_LEITURA.isdisjoint(microsoft.ESCOPOS_DE_ESCRITA)


# --- escrita concorrente e resposta estranha (achados 4 e 6 da revisão) ----------------------------------------------


def test_duas_linhas_ao_mesmo_tempo_da_mesma_pessoa_ficam_cada_uma_na_sua_linha(conta_com_escrita, ana):
    _, dados = conta_com_escrita
    previas = [
        dados_de(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": f"linha {n} | x", "aba": "Resumo"}, ana)
        for n in range(4)
    ]
    resultados = []
    largada = threading.Barrier(len(previas))

    def confirmar(previa):
        largada.wait()
        resultados.append(confirmacoes.confirmar(previa["confirmacao_id"], ana))

    linhas = [threading.Thread(target=confirmar, args=(previa,)) for previa in previas]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()
    assert [r["status"] for r in resultados] == ["ok"] * 4, resultados
    gravadas = sorted(linha[0] for linha in dados.itens[PLANILHA]["abas"]["Resumo"][3:])
    assert gravadas == ["linha 0", "linha 1", "linha 2", "linha 3"]  # nenhuma sobrescreveu a outra


def test_linha_sobrescrita_por_outra_pessoa_no_meio_da_escrita_nao_vira_pronto_falso(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(ADICIONAR_LINHA, {"id_arquivo": PLANILHA, "valores": "minha | x", "aba": "Resumo"}, ana)

    def responder(pedido):
        resposta = dados(pedido)
        if pedido.metodo == "PATCH" and "values" in (pedido.corpo or {}):  # outra pessoa grava na mesma linha em seguida
            dados.itens[PLANILHA]["abas"]["Resumo"][3] = ["da outra pessoa", "y"]
        return resposta

    servidor.responder = responder
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["tipo_erro"] == "integracao_indisponivel" and resultado["mensagem"] == MENSAGEM_EFEITO_INCERTO


def test_escrita_aceita_com_resposta_fora_do_formato_diz_que_pode_ter_acontecido(conta_com_escrita, ana):
    servidor, dados = conta_com_escrita
    previa = dados_de(CRIAR_PLANILHA, {"titulo": "Fechamento", "colunas": "A|B", "linhas": "a|b"}, ana)

    def responder(pedido):
        resposta = dados(pedido)
        if pedido.metodo == "PUT":
            return 201, {"Content-Type": "application/json"}, b"{}"  # criou, mas a resposta não traz id nem link
        return resposta

    servidor.responder = responder
    resultado = confirmacoes.confirmar(previa["confirmacao_id"], ana)
    assert resultado["mensagem"] == MENSAGEM_EFEITO_INCERTO


def test_documento_enorme_vira_parametro_invalido_e_nao_pausa_a_integracao(conta, ana):
    servidor, dados = conta
    dados.itens[DOCUMENTO]["docx"] = b"x" * (formatos.BYTES_NO_MAXIMO)  # o tamanho declarado cabe; o download passa do teto
    servidor.download.responder = lambda pedido: (200, {"Content-Type": "application/octet-stream"}, b"x" * (formatos.BYTES_NO_MAXIMO + 10))
    for _ in range(FALHAS_PARA_PAUSAR + 2):
        assert usar(LER_DOCUMENTO, {"id_arquivo": DOCUMENTO}, ana)["tipo_erro"] == "parametro_invalido"
    assert MICROSOFT.saude() != "pausada"
