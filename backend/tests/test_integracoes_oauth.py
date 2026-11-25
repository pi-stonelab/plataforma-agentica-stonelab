"""OAuth2 por pessoa (Google): autorizar com PKCE, trocar o código, renovar, revogar e o provedor de credencial.

O cliente é o de verdade; só o servidor é falso (`apoio_escritorio.py`, no formato do Google). Os tokens do servidor
falso começam por `ya29.`, como os do Google, e nenhum teste os deixa aparecer em log nem em mensagem.
"""

import logging
import threading
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from ferramentas.base import ErroFerramenta
from ferramentas.integracoes import credenciais, oauth
from ferramentas.integracoes.cliente_http import PedidoRecusado, RespostaInvalida
from ferramentas.integracoes.conector import CredencialRecusada
from ferramentas.integracoes.google_workspace import conector as google
from ferramentas.integracoes.google_workspace.conector import CONECTOR as GOOGLE

from .apoio_escritorio import (
    GOOGLE_CLIENT_SECRET,
    GoogleDeTeste,
    ServidorDeEscritorio,
    ambiente_do_google,
    resposta_json,
)
from .apoio_ferramentas import limpar_estado

ANA, BIA = "F0001", "F0002"


@pytest.fixture(autouse=True)
def estado_limpo():
    limpar_estado()
    yield
    limpar_estado()


@pytest.fixture
def servidor(monkeypatch):
    dados = GoogleDeTeste()
    with ServidorDeEscritorio(dados) as servidor:
        for nome, valor in ambiente_do_google(servidor).items():
            monkeypatch.setenv(nome, valor)
        yield servidor, dados


def ligar(dados, pessoa=ANA, com_escrita=False):
    url = GOOGLE.autorizar(pessoa, com_escrita=com_escrita)
    codigo, estado = dados.consentir(pessoa, url)
    return GOOGLE.fluxo().concluir(pessoa, estado, codigo)


# --- o endereço da tela de consentimento --------------------------------------------------------------------------


def test_o_endereco_de_autorizacao_leva_state_pkce_e_so_os_escopos_de_leitura(servidor):
    url = GOOGLE.autorizar(ANA)
    partes = urlsplit(url)
    consulta = {k: v[0] for k, v in parse_qs(partes.query).items()}
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == f"{servidor[0].url}/o/oauth2/v2/auth"
    assert consulta["response_type"] == "code" and consulta["code_challenge_method"] == "S256"
    assert len(consulta["state"]) >= 40 and len(consulta["code_challenge"]) == 43
    assert set(consulta["scope"].split()) == google.ESCOPOS_DE_LEITURA
    assert consulta["access_type"] == "offline" and consulta["prompt"] == "consent"
    assert GOOGLE_CLIENT_SECRET not in url and "code_verifier" not in url  # o segredo e o verificador não saem


def test_escrita_so_e_pedida_a_parte_e_soma_a_leitura(servidor):
    url = GOOGLE.autorizar(ANA, com_escrita=True)
    escopos = set(parse_qs(urlsplit(url).query)["scope"][0].split())
    assert escopos == google.ESCOPOS_DE_LEITURA | google.ESCOPOS_DE_ESCRITA
    assert google.ESCOPOS_DE_LEITURA.isdisjoint(google.ESCOPOS_DE_ESCRITA)
    assert not any(e.endswith(("/drive", "/calendar", "/drive.readonly")) for e in escopos)  # nenhum escopo largo


def test_cada_pedido_tem_um_state_novo_e_um_verificador_novo(servidor):
    primeiro, segundo = GOOGLE.autorizar(ANA), GOOGLE.autorizar(ANA)
    estados = {parse_qs(urlsplit(u).query)["state"][0] for u in (primeiro, segundo)}
    desafios = {parse_qs(urlsplit(u).query)["code_challenge"][0] for u in (primeiro, segundo)}
    assert len(estados) == 2 and len(desafios) == 2


# --- trocar o código por tokens -----------------------------------------------------------------------------------


def test_concluir_troca_o_codigo_confere_o_pkce_no_servidor_e_guarda_a_credencial(servidor):
    _, dados = servidor
    credencial = ligar(dados)
    guardada = credenciais.provedor().ler(ANA, "google_workspace")
    assert guardada == credencial and guardada.escopos == google.ESCOPOS_DE_LEITURA
    assert guardada.refresh_token.startswith("1//") and guardada.valida()
    troca = next(p for p in servidor[0].pedidos if p.rota == "/token")
    assert troca.formulario["grant_type"] == "authorization_code" and len(troca.formulario["code_verifier"]) >= 43
    assert troca.formulario["client_secret"] == GOOGLE_CLIENT_SECRET  # o segredo vai só ao endereço de token, no corpo
    assert "client_secret" not in troca.caminho


def test_codigo_interceptado_nao_serve_sem_o_verificador_do_pkce(servidor):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    _, estado = dados.consentir(ANA, url)
    dados.codigos["codigo-roubado"] = {**next(iter(dados.codigos.values())), "desafio": "outro-desafio-qualquer"}
    with pytest.raises(oauth.AutorizacaoRecusada) as erro:
        GOOGLE.fluxo().concluir(ANA, estado, "codigo-roubado")
    assert "codigo-roubado" not in str(erro.value)
    assert credenciais.provedor().ler(ANA, "google_workspace") is None


def test_codigo_ja_usado_e_recusado(servidor):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    GOOGLE.fluxo().concluir(ANA, estado, codigo)
    outro_url = GOOGLE.autorizar(ANA)
    _, outro_estado = dados.consentir(ANA, outro_url)
    with pytest.raises(oauth.AutorizacaoRecusada):
        GOOGLE.fluxo().concluir(ANA, outro_estado, codigo)  # o mesmo código, outro pedido


def test_state_de_uso_unico_preso_a_pessoa_e_com_validade(servidor, monkeypatch):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    with pytest.raises(oauth.AutorizacaoRecusada):  # outra pessoa tenta concluir o pedido da Ana
        GOOGLE.fluxo().concluir(BIA, estado, codigo)
    GOOGLE.fluxo().concluir(ANA, estado, codigo)  # o pedido da Ana continua valendo: a tentativa da Bia não o gasta
    with pytest.raises(oauth.AutorizacaoRecusada):  # uso único: depois de concluído, não vale de novo
        GOOGLE.fluxo().concluir(ANA, estado, codigo)
    with pytest.raises(oauth.AutorizacaoRecusada):  # state inventado
        GOOGLE.fluxo().concluir(ANA, "inventado", "qualquer")
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    agora = credenciais.agora()
    monkeypatch.setattr(credenciais, "agora", lambda: agora + oauth.VALIDADE_DO_ESTADO + timedelta(seconds=1))
    with pytest.raises(oauth.AutorizacaoRecusada):
        GOOGLE.fluxo().concluir(ANA, estado, codigo)


def test_state_roubado_por_outra_pessoa_nao_queima_o_pedido_do_dono(servidor):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    with pytest.raises(oauth.AutorizacaoRecusada):  # a Bia chuta o state da Ana
        GOOGLE.fluxo().concluir(BIA, estado, codigo)
    GOOGLE.fluxo().cancelar(BIA, estado)  # nem cancelando em nome da Ana
    assert GOOGLE.fluxo().concluir(ANA, estado, codigo).access_token  # o pedido da Ana continua valendo


def test_state_de_um_servico_nao_vale_em_outro(servidor):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    fluxo = GOOGLE.fluxo()
    fluxo.configuracao = fluxo.configuracao.__class__(**{**fluxo.configuracao.__dict__, "nome": "microsoft_365"})
    with pytest.raises(oauth.AutorizacaoRecusada):
        fluxo.concluir(ANA, estado, codigo)


def test_a_pessoa_recusou_na_tela_o_pedido_e_esquecido(servidor):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    GOOGLE.fluxo().cancelar(ANA, estado)
    with pytest.raises(oauth.AutorizacaoRecusada):
        GOOGLE.fluxo().concluir(ANA, estado, codigo)


def test_muitos_pedidos_abertos_da_mesma_pessoa_descartam_os_mais_antigos(servidor):
    urls = [GOOGLE.autorizar(ANA) for _ in range(oauth.LIMITE_POR_PESSOA + 2)]
    assert len([p for p in oauth.PEDIDOS_PENDENTES._pedidos.values() if p.id_usuario == ANA]) == oauth.LIMITE_POR_PESSOA
    primeiro = parse_qs(urlsplit(urls[0]).query)["state"][0]
    assert primeiro not in oauth.PEDIDOS_PENDENTES._pedidos


def test_app_com_segredo_errado_e_credencial_da_plataforma_recusada(servidor, monkeypatch):
    _, dados = servidor
    url = GOOGLE.autorizar(ANA)
    codigo, estado = dados.consentir(ANA, url)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-segredo-errado-0123456789")
    with pytest.raises(CredencialRecusada) as erro:
        GOOGLE.fluxo().concluir(ANA, estado, codigo)
    assert "segredo" not in str(erro.value).lower()


def test_consentimento_granular_guarda_so_o_que_o_servico_concedeu(servidor):
    _, dados = servidor
    dados.escopos_concedidos_a_menos = [google.CALENDARIO_LEITURA]
    credencial = ligar(dados, com_escrita=True)
    assert credencial.escopos == {google.CALENDARIO_LEITURA}


def test_resposta_de_token_fora_do_formato_nao_vira_credencial(servidor):
    _, dados = servidor
    original = dados.endereco_de_token
    for quebrada in ({"access_token": "ya29.c", "token_type": "Bearer", "expires_in": 3600},
                     {"access_token": "ya29.token-valido-123", "token_type": "MAC", "expires_in": 3600},
                     {"access_token": "ya29.token-valido-123", "token_type": "Bearer", "expires_in": "muito"},
                     {"access_token": "ya29.token com espaco", "token_type": "Bearer", "expires_in": 3600}):
        url = GOOGLE.autorizar(ANA)
        codigo, estado = dados.consentir(ANA, url)
        dados.endereco_de_token = lambda pedido, resposta=quebrada: resposta_json(resposta)
        with pytest.raises(RespostaInvalida):
            GOOGLE.fluxo().concluir(ANA, estado, codigo)
    dados.endereco_de_token = original
    assert credenciais.provedor().ler(ANA, "google_workspace") is None


# --- o provedor: renovar, revogar, simultâneo ---------------------------------------------------------------------


def test_token_vencido_e_renovado_sozinho_e_o_token_de_renovacao_fica(servidor):
    _, dados = servidor
    antiga = ligar(dados)
    dados.vencer(antiga.access_token)
    credenciais.provedor().guardar(ANA, "google_workspace", credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, antiga.refresh_token))
    fluxo = GOOGLE.fluxo()
    novo = credenciais.provedor().token_de_acesso(ANA, fluxo, {google.CALENDARIO_LEITURA})
    assert novo != antiga.access_token
    guardada = credenciais.provedor().ler(ANA, "google_workspace")
    assert guardada.access_token == novo and guardada.refresh_token == antiga.refresh_token  # o Google não troca
    assert guardada.escopos == antiga.escopos


def test_token_ainda_valido_nao_chama_o_servico(servidor):
    srv, dados = servidor
    ligar(dados)
    antes = len(srv.pedidos)
    credenciais.provedor().token_de_acesso(ANA, GOOGLE.fluxo(), {google.CALENDARIO_LEITURA})
    assert len(srv.pedidos) == antes


def test_duas_chamadas_ao_mesmo_tempo_renovam_uma_vez_so(servidor):
    srv, dados = servidor
    antiga = ligar(dados)
    credenciais.provedor().guardar(ANA, "google_workspace", credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, antiga.refresh_token))
    fluxo = GOOGLE.fluxo()
    resultados = []
    trava = threading.Barrier(6)

    def pedir_token():
        trava.wait()
        resultados.append(credenciais.provedor().token_de_acesso(ANA, fluxo, {google.CALENDARIO_LEITURA}))

    linhas = [threading.Thread(target=pedir_token) for _ in range(6)]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()
    renovacoes = [p for p in srv.pedidos if p.formulario and p.formulario.get("grant_type") == "refresh_token"]
    assert len(renovacoes) == 1 and len(set(resultados)) == 1


def test_autorizacao_revogada_apaga_a_conta_e_pede_para_ligar_de_novo(servidor):
    _, dados = servidor
    antiga = ligar(dados)
    credenciais.provedor().guardar(ANA, "google_workspace", credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, antiga.refresh_token))
    del dados.renovacoes[antiga.refresh_token]  # a pessoa revogou o acesso na conta Google
    with pytest.raises(credenciais.ContaNaoLigada) as erro:
        credenciais.provedor().token_de_acesso(ANA, GOOGLE.fluxo(), {google.CALENDARIO_LEITURA})
    assert erro.value.tipo_erro == "integracao_indisponivel" and "não está ligada" in erro.value.mensagem
    assert credenciais.provedor().ler(ANA, "google_workspace") is None
    assert not GOOGLE.conta_ligada(ANA)


def test_renovacao_recusada_por_rotacao_de_outro_processo_nao_apaga_a_conta(servidor):
    """O serviço trocou o token de renovação para outro processo: o nosso ficou velho e foi recusado. A credencial
    nova, guardada por esse outro processo, não pode ser apagada (a pessoa continua ligada)."""
    _, dados = servidor
    antiga = ligar(dados)
    vencida = credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, antiga.refresh_token)
    credenciais.provedor().guardar(ANA, "google_workspace", vencida)
    novo_dono = credenciais.Credencial(
        "ya29.token-novo-do-outro-processo", credenciais.agora() + timedelta(hours=1), antiga.escopos, "renovacao-nova-0001")
    fluxo = GOOGLE.fluxo()
    original = fluxo.renovar

    def renovar_enquanto_outro_processo_troca(credencial):
        credenciais.provedor().guardar(ANA, "google_workspace", novo_dono)  # o outro processo termina antes
        return original(credencial)

    fluxo.renovar = renovar_enquanto_outro_processo_troca
    del dados.renovacoes[antiga.refresh_token]  # o serviço já não aceita o token velho
    token = credenciais.provedor().token_de_acesso(ANA, fluxo, {google.CALENDARIO_LEITURA}, recusado=antiga.access_token)
    assert token == novo_dono.access_token
    assert credenciais.provedor().ler(ANA, "google_workspace") == novo_dono


def test_sem_token_de_renovacao_o_vencimento_pede_para_ligar_de_novo(servidor):
    _, dados = servidor
    antiga = ligar(dados)
    credenciais.provedor().guardar(ANA, "google_workspace", credenciais.Credencial(
        antiga.access_token, credenciais.agora() - timedelta(minutes=1), antiga.escopos, None))
    with pytest.raises(credenciais.ContaNaoLigada):
        credenciais.provedor().token_de_acesso(ANA, GOOGLE.fluxo(), {google.CALENDARIO_LEITURA})


def test_sem_conta_ou_sem_o_escopo_a_mensagem_diz_o_que_fazer(servidor):
    _, dados = servidor
    fluxo = GOOGLE.fluxo()
    with pytest.raises(credenciais.ContaNaoLigada) as sem_conta:
        credenciais.provedor().token_de_acesso(ANA, fluxo, {google.CALENDARIO_LEITURA})
    assert sem_conta.value.mensagem.startswith("A conta Google Workspace desta pessoa não está ligada.")
    ligar(dados)
    with pytest.raises(credenciais.PermissaoInsuficiente) as sem_escopo:
        credenciais.provedor().token_de_acesso(ANA, fluxo, {google.CALENDARIO_ESCRITA})
    assert "permissão de escrita" in sem_escopo.value.mensagem and "reconectar" in sem_escopo.value.mensagem
    assert isinstance(sem_conta.value, ErroFerramenta) and isinstance(sem_escopo.value, ErroFerramenta)


def test_escopo_mais_amplo_concedido_antes_cobre_o_minimo(servidor):
    credenciais.provedor().guardar(ANA, "google_workspace", credenciais.Credencial(
        "ya29.token-de-teste-1", credenciais.agora() + timedelta(hours=1),
        frozenset({google.CALENDARIO_ESCRITA, google.AUTH + "drive"}), "1//renovacao"))
    fluxo = GOOGLE.fluxo()
    provedor = credenciais.provedor()
    assert provedor.token_de_acesso(ANA, fluxo, {google.CALENDARIO_LEITURA, google.PLANILHAS_LEITURA})
    with pytest.raises(credenciais.PermissaoInsuficiente):
        provedor.token_de_acesso(ANA, fluxo, {google.DOCUMENTOS_LEITURA, google.PLANILHAS_ESCRITA, google.CALENDARIO_ESCRITA, "outro"})


def test_desligar_revoga_no_google_e_esquece_a_conta(servidor):
    _, dados = servidor
    credencial = ligar(dados)
    GOOGLE.fluxo().desligar(ANA)
    assert dados.revogados == [credencial.refresh_token]
    assert not GOOGLE.conta_ligada(ANA)


def test_desligar_esquece_a_conta_mesmo_se_a_revogacao_falhar(servidor):
    srv, dados = servidor
    ligar(dados)
    srv.responder = lambda pedido: (500, {}, b"")
    GOOGLE.fluxo().desligar(ANA)
    assert not GOOGLE.conta_ligada(ANA)


def test_cada_pessoa_tem_a_sua_conta(servidor):
    _, dados = servidor
    ligar(dados, ANA)
    assert GOOGLE.conta_ligada(ANA) and not GOOGLE.conta_ligada(BIA)


def test_o_provedor_so_aceita_a_interface_certa():
    with pytest.raises(TypeError):
        credenciais.usar(object())
    with pytest.raises(TypeError):
        credenciais.ProvedorDeCredencial()  # abstrata: ler, guardar e apagar são do back-end

    class SoLer(credenciais.ProvedorDeCredencial):
        def ler(self, id_usuario, servico):
            return None

    with pytest.raises(TypeError):
        SoLer()


# --- segredo nunca aparece -----------------------------------------------------------------------------------------


def test_token_e_segredo_nao_aparecem_em_log_mensagem_nem_repr(servidor, caplog):
    srv, dados = servidor
    caplog.set_level(logging.DEBUG)
    credencial = ligar(dados)
    srv.responder = lambda pedido: (500, {}, b"")
    antiga = credenciais.Credencial(credencial.access_token, credenciais.agora() - timedelta(minutes=1),
                                    credencial.escopos, credencial.refresh_token)
    credenciais.provedor().guardar(ANA, "google_workspace", antiga)
    with pytest.raises(ConnectionError) as erro:
        credenciais.provedor().token_de_acesso(ANA, GOOGLE.fluxo(), {google.CALENDARIO_LEITURA})
    segredos = [credencial.access_token, credencial.refresh_token, GOOGLE_CLIENT_SECRET]
    textos = [caplog.text, str(erro.value), repr(credencial), repr(GOOGLE.fluxo().configuracao)]
    for segredo in segredos:
        assert all(segredo not in texto for texto in textos)


# --- testar --------------------------------------------------------------------------------------------------------


def test_testar_confere_o_app_sem_nenhuma_conta(servidor):
    srv, _ = servidor
    frase = GOOGLE.testar()
    assert "aceitou o app" in frase and "Nenhuma conta foi ligada" in frase
    assert [p.rota for p in srv.pedidos] == ["/token"]


def test_testar_com_segredo_errado_diz_que_a_credencial_foi_recusada(servidor, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-segredo-errado-0123456789")
    with pytest.raises(CredencialRecusada):
        GOOGLE.testar()


def test_o_terminal_mostra_o_resultado_do_teste_sem_segredo(servidor, monkeypatch):
    from ferramentas.integracoes.__main__ import principal

    linhas = []
    ambiente = {**ambiente_do_google(servidor[0]), "MODO_TERMINAL": "1"}
    principal(["testar", "google_workspace"], ambiente=ambiente, escrever=linhas.append)
    assert "Google Workspace (modo real): O serviço aceitou o app" in linhas[0]
    assert GOOGLE_CLIENT_SECRET not in linhas[0]
    with pytest.raises(SystemExit) as saida:
        principal(["testar", "google_workspace"], ambiente={**ambiente, "GOOGLE_CLIENT_SECRET": "curto"}, escrever=linhas.append)
    assert "GOOGLE_CLIENT_SECRET" in str(saida.value) and "curto" not in str(saida.value)


def test_pedido_recusado_do_endereco_de_token_e_um_parametro_invalido(servidor):
    srv, _ = servidor
    srv.responder = lambda pedido: (400, {}, b'{"error": "invalid_request"}')
    url = GOOGLE.autorizar(ANA)
    estado = parse_qs(urlsplit(url).query)["state"][0]
    with pytest.raises(oauth.AutorizacaoRecusada):
        GOOGLE.fluxo().concluir(ANA, estado, "codigo")
    assert issubclass(PedidoRecusado, ErroFerramenta)
