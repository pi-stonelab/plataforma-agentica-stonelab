"""CEP (ViaCEP) e cotação (PTAX do Banco Central) de verdade, pelo catálogo, contra um servidor local no formato
das APIs reais (`apoio_http.py`). Prova o pedido que sai (caminho e consulta), a resposta e o modo simulado.
"""

from datetime import date, datetime, time

import pytest
from ferramentas import catalogo, integracoes
from ferramentas.base import MENSAGEM_TERCEIROS
from ferramentas.dados_sinteticos import HOJE_DO_MOCK
from ferramentas.integracoes.apis_publicas.conector import CONECTOR as APIS
from ferramentas.integracoes.apis_publicas.conector import FUSO_DA_COTACAO, MENSAGEM_TESTE_SIMULADO
from mock.falhas import desligar_todas, ligar

from .apoio_ferramentas import (
    FUNCIONARIO_DO_CARGO,
    limpar_estado,
    mundo_do_mock,
    usuario_do_diretorio,
)
from .apoio_http import (
    FERIADO,
    JSON,
    ServidorHttp,
    ambiente_das_apis_publicas,
    boletim_de_fechamento,
    porta_que_recusa,
    responder_das_apis_publicas,
)

CEP = "consultar_endereco_cep"
COTACAO = "consultar_cotacao_moeda"
AGENTE = (CEP, COTACAO)


@pytest.fixture(scope="module")
def ana():
    return usuario_do_diretorio(mundo_do_mock(), FUNCIONARIO_DO_CARGO["atendente_n1"])


@pytest.fixture(autouse=True)
def estado_limpo():
    limpar_estado()
    integracoes.reiniciar()
    yield
    limpar_estado()
    integracoes.reiniciar()
    desligar_todas()


@pytest.fixture
def servidor(monkeypatch):
    with ServidorHttp() as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        yield rodando


def executar(nome, argumentos, usuario):
    return catalogo.executar(nome, argumentos, usuario, AGENTE)


def pedidos_de_cotacao(servidor):
    return [caminho for _, caminho in servidor.pedidos if "CotacaoMoedaDia" in caminho]


# --- CEP -------------------------------------------------------------------------------------------


def test_cep_vem_do_viacep_com_hifen_e_a_fonte_como_conteudo_de_terceiros(servidor, ana):
    resposta = executar(CEP, {"cep": "01.310-100"}, ana)
    assert resposta == {
        "status": "ok",
        "dados": {
            "conteudo_de_terceiros": {
                "cep": "01310-100",
                "logradouro": "Avenida Paulista",
                "bairro": "Bela Vista",
                "cidade": "São Paulo",
                "uf": "SP",
                "fonte": "ViaCEP",
            }
        },
        "mensagem": MENSAGEM_TERCEIROS,
        "tipo_erro": None,
    }
    assert servidor.pedidos == [("GET", "/ws/01310100/json/")]


def test_cep_inexistente_e_nao_encontrado(servidor, ana):
    resposta = executar(CEP, {"cep": "99999-999"}, ana)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("nao_encontrado", "CEP não encontrado.")


@pytest.mark.parametrize("erro", [True, "true"])
def test_cep_aceita_o_erro_do_viacep_como_booleano_e_como_texto(erro, ana, monkeypatch):
    def responder(metodo, caminho):
        return 200, JSON, b'{"erro": ' + (b"true" if erro is True else b'"true"') + b"}"

    with ServidorHttp(responder) as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        assert executar(CEP, {"cep": "12345678"}, ana)["tipo_erro"] == "nao_encontrado"


def test_cep_fora_do_formato_nem_chega_ao_viacep(servidor, ana):
    for cep in ("0131010", "01310-1000", "abcde-fgh", "01310/100"):
        assert executar(CEP, {"cep": cep}, ana)["tipo_erro"] == "parametro_invalido"
    assert servidor.pedidos == []


@pytest.mark.parametrize(
    "corpo",
    [
        b'{"cep": "99999-999", "logradouro": "x", "bairro": "x", "localidade": "x", "uf": "SP"}',  # outro CEP
        b'{"cep": "01310-100", "logradouro": "x", "bairro": "x", "localidade": "x", "uf": "Sao Paulo"}',
        b'{"cep": "01310-100", "bairro": "x", "localidade": "x", "uf": "SP"}',  # falta campo
        b'["nao", "e", "objeto"]',
    ],
)
def test_cep_resposta_fora_do_formato_vira_integracao_indisponivel(corpo, ana, monkeypatch):
    with ServidorHttp(lambda metodo, caminho: (200, JSON, corpo)) as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        resposta = executar(CEP, {"cep": "01310100"}, ana)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == (
        "integracao_indisponivel",
        "Sem resposta do serviço: APIs públicas (CEP e câmbio). Tente de novo em um minuto.",
    )


def test_viacep_fora_do_ar_tres_vezes_pausa_e_nao_derruba_a_cotacao(ana, monkeypatch):
    with porta_que_recusa() as url_recusada, ServidorHttp() as ptax:
        monkeypatch.setenv("VIACEP_URL", url_recusada)
        monkeypatch.setenv("BCB_PTAX_URL", ambiente_das_apis_publicas(ptax)["BCB_PTAX_URL"])
        for _ in range(3):
            assert executar(CEP, {"cep": "01310100"}, ana)["tipo_erro"] == "integracao_indisponivel"
        assert integracoes.conector("apis_publicas").saude() == "pausada"
        assert executar(COTACAO, {"moeda": "USD"}, ana)["status"] == "ok"


def test_cep_no_modo_simulado_nao_usa_rede_e_diz_que_e_exemplo(servidor, ana, monkeypatch):
    monkeypatch.setenv("APIS_PUBLICAS_MODO", "simulado")
    endereco = executar(CEP, {"cep": "20040-020"}, ana)["dados"]["conteudo_de_terceiros"]
    assert (endereco["cidade"], endereco["cep"], endereco["fonte"]) == (
        "Rio de Janeiro",
        "20040-020",
        "Endereço de exemplo (modo simulado)",
    )
    fora = executar(CEP, {"cep": "01001-000"}, ana)  # um CEP real, mas fora dos 3 de exemplo
    assert (fora["tipo_erro"], fora["mensagem"]) == (
        "nao_encontrado",
        "No modo de demonstração só há os CEPs 01310-100, 20040-020 e 30130-010.",
    )
    assert servidor.pedidos == []


def test_apis_publicas_desligadas_saem_do_indice_e_o_agente_ouve_o_aviso(servidor, ana, monkeypatch):
    monkeypatch.setenv("APIS_PUBLICAS_MODO", "desligado")
    assert catalogo.ferramentas_liberadas(ana, AGENTE) == []
    aviso = (
        "As consultas de CEP e de câmbio não estão ligadas nesta plataforma. Avise o usuário e não tente de novo."
    )
    for nome, argumentos in ((CEP, {"cep": "01310100"}), (COTACAO, {"moeda": "USD"})):
        resposta = executar(nome, argumentos, ana)
        assert (resposta["tipo_erro"], resposta["mensagem"]) == ("ferramenta_inativa", aviso)
    assert servidor.pedidos == []


def test_apis_publicas_mal_configuradas_tambem_saem_do_indice(ana, monkeypatch):
    monkeypatch.setenv("VIACEP_URL", "http://viacep.example")  # sem https fora do localhost
    assert catalogo.ferramentas_liberadas(ana, AGENTE) == []
    assert executar(CEP, {"cep": "01310100"}, ana)["tipo_erro"] == "ferramenta_inativa"


def test_falha_simulada_derruba_cep_e_cotacao_sem_chamar_a_rede_nem_pausar(servidor, ana):
    ligar("apis_publicas")
    for _ in range(4):
        assert executar(CEP, {"cep": "01310100"}, ana)["tipo_erro"] == "integracao_indisponivel"
    assert executar(COTACAO, {"moeda": "USD"}, ana)["tipo_erro"] == "integracao_indisponivel"
    assert servidor.pedidos == []
    assert APIS.saude() == "indisponivel"
    desligar_todas()
    assert APIS.saude() != "pausada"  # a falha simulada não conta no disjuntor


def test_pedido_recusado_pelo_servico_nao_pausa_a_integracao(ana, monkeypatch):
    def responder(metodo, caminho):
        if "CotacaoMoedaDia" in caminho:
            return 400, {"Content-Type": "text/html"}, b"<h1>Bad Request</h1>"
        return responder_das_apis_publicas(metodo, caminho)

    with ServidorHttp(responder) as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        for _ in range(4):
            resposta = executar(COTACAO, {"moeda": "USD"}, ana)
            assert (resposta["tipo_erro"], resposta["mensagem"]) == (
                "parametro_invalido",
                "O serviço recusou o pedido. Confira os dados enviados.",
            )
        assert APIS.saude_por_servico()["ptax"] == "ok"


# --- cotação ---------------------------------------------------------------------------------------


def test_cotacao_sem_data_usa_hoje_do_mock_e_o_boletim_de_fechamento(servidor, ana):
    resposta = executar(COTACAO, {"moeda": "usd"}, ana)
    fechamento = boletim_de_fechamento("USD", HOJE_DO_MOCK)
    assert resposta["status"] == "ok"
    assert resposta["dados"] == {
        "moeda": "USD",
        "nome_da_moeda": "Dólar dos Estados Unidos",
        "data": "2026-10-15",
        "boletim": "Fechamento PTAX",
        "cotacao_compra": "R$ " + f"{fechamento['cotacaoCompra']:.4f}".replace(".", ","),
        "cotacao_venda": "R$ " + f"{fechamento['cotacaoVenda']:.4f}".replace(".", ","),
        "fonte": "Banco Central do Brasil (PTAX)",
    }
    assert pedidos_de_cotacao(servidor) == [
        (
            "/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
            "?@moeda='USD'&@dataCotacao='10-15-2026'&$top=100&$format=json"
        )
    ]


def test_cotacao_no_fim_de_semana_volta_para_sexta_sem_perguntar_sabado_e_domingo(servidor, ana):
    resposta = executar(COTACAO, {"moeda": "EUR", "data": "2026-10-11"}, ana)  # domingo
    assert resposta["dados"]["data"] == "2026-10-09"
    assert [c.split("@dataCotacao=")[1][:12] for c in pedidos_de_cotacao(servidor)] == ["'10-09-2026'"]


def test_cotacao_no_feriado_volta_para_o_dia_util_anterior(servidor, ana):
    assert FERIADO == date(2026, 10, 12)
    resposta = executar(COTACAO, {"moeda": "GBP", "data": "2026-10-12"}, ana)
    assert resposta["dados"]["data"] == "2026-10-09"
    dias = [c.split("@dataCotacao=")[1][:12] for c in pedidos_de_cotacao(servidor)]
    assert dias == ["'10-12-2026'", "'10-09-2026'"]


def test_cotacao_sem_boletim_em_7_dias_e_nao_encontrado(servidor, ana):
    resposta = executar(COTACAO, {"moeda": "USD", "data": "2026-01-15"}, ana)  # fora do que o servidor tem
    assert (resposta["tipo_erro"], resposta["mensagem"]) == (
        "nao_encontrado",
        "Sem boletim do Banco Central nos 7 dias até essa data.",
    )
    assert len(pedidos_de_cotacao(servidor)) == 5  # os dias úteis da semana; sábado e domingo não vão


@pytest.mark.parametrize(
    ("argumentos", "mensagem"),
    [
        ({"moeda": "US"}, "Use o código de 3 letras da moeda, como USD."),
        ({"moeda": "U$D"}, "Use o código de 3 letras da moeda, como USD."),
        ({"moeda": "XYZ"}, "O Banco Central não publica cotação dessa moeda."),
        ({"moeda": "USD", "data": "2026-10-16"}, "A data não pode ser depois de hoje (15/10/2026)."),
        ({"moeda": "USD", "data": "0999-01-04"}, "O Banco Central tem cotação a partir de 01/01/1985."),
        ({"moeda": "USD", "data": "14/10/2026"}, (
            "O parâmetro data deve ser uma data no formato AAAA-MM-DD, como 2026-10-14."
        )),
    ],
)
def test_cotacao_recusa_moeda_e_data_fora_da_regra(servidor, ana, argumentos, mensagem):
    resposta = executar(COTACAO, argumentos, ana)
    assert (resposta["tipo_erro"], resposta["mensagem"]) == ("parametro_invalido", mensagem)
    assert pedidos_de_cotacao(servidor) == []


def test_cotacao_aceita_so_as_moedas_que_o_banco_central_lista_e_guarda_a_lista(servidor, ana):
    for moeda in ("USD", "JPY", "CHF"):
        assert executar(COTACAO, {"moeda": moeda}, ana)["status"] == "ok"
    assert [c for _, c in servidor.pedidos if c.endswith("/Moedas?$top=100&$format=json")] == [
        "/olinda/servico/PTAX/versao/v1/odata/Moedas?$top=100&$format=json"
    ]


def test_cotacao_sem_fechamento_usa_o_boletim_mais_recente(ana, monkeypatch):
    def responder(metodo, caminho):
        if "CotacaoMoedaDia" in caminho:
            status, cabecalhos, _ = responder_das_apis_publicas(metodo, caminho)
            corpo = (
                b'{"value": [{"cotacaoCompra": 5.1, "cotacaoVenda": 5.2, "dataHoraCotacao": "2026-10-15 10:04:23.355",'
                b' "tipoBoletim": "Abertura"}, {"cotacaoCompra": 5.3, "cotacaoVenda": 5.4,'
                b' "dataHoraCotacao": "2026-10-15 11:04:23.355", "tipoBoletim": "Intermedi\\u00e1rio"}]}'
            )
            return status, cabecalhos, corpo
        return responder_das_apis_publicas(metodo, caminho)

    with ServidorHttp(responder) as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        dados = executar(COTACAO, {"moeda": "USD"}, ana)["dados"]
    assert (dados["boletim"], dados["cotacao_compra"], dados["cotacao_venda"]) == (
        "Intermediário",
        "R$ 5,3000",
        "R$ 5,4000",
    )


@pytest.mark.parametrize(
    "corpo",
    [
        b'{"value": [{"cotacaoCompra": "5,1", "cotacaoVenda": 5.2, "dataHoraCotacao": "x", "tipoBoletim": "x"}]}',
        b'{"value": [{"cotacaoCompra": -1, "cotacaoVenda": 5.2, "dataHoraCotacao": "x", "tipoBoletim": "x"}]}',
        b'{"value": [{"cotacaoCompra": true, "cotacaoVenda": 5.2, "dataHoraCotacao": "x", "tipoBoletim": "x"}]}',
        b'{"valor": []}',
    ],
)
def test_cotacao_resposta_fora_do_formato_vira_integracao_indisponivel(corpo, ana, monkeypatch):
    def responder(metodo, caminho):
        if "CotacaoMoedaDia" in caminho:
            return 200, JSON, corpo
        return responder_das_apis_publicas(metodo, caminho)

    with ServidorHttp(responder) as rodando:
        for nome, valor in ambiente_das_apis_publicas(rodando).items():
            monkeypatch.setenv(nome, valor)
        assert executar(COTACAO, {"moeda": "USD"}, ana)["tipo_erro"] == "integracao_indisponivel"


def test_cotacao_no_modo_simulado_nao_usa_rede_e_diz_que_e_ilustrativa(servidor, ana, monkeypatch):
    monkeypatch.setenv("APIS_PUBLICAS_MODO", "simulado")
    dados = executar(COTACAO, {"moeda": "USD", "data": "2026-10-10"}, ana)["dados"]  # sábado
    assert (dados["data"], dados["cotacao_compra"]) == ("2026-10-09", "R$ 5,3500")
    assert "ilustrativos" in dados["fonte"]
    jpy = executar(COTACAO, {"moeda": "JPY"}, ana)
    assert (jpy["tipo_erro"], jpy["mensagem"]) == ("parametro_invalido", "No modo de demonstração só há EUR, GBP, USD.")
    antiga = executar(COTACAO, {"moeda": "USD", "data": "0001-01-01"}, ana)
    assert antiga["tipo_erro"] == "parametro_invalido"
    depois = executar(COTACAO, {"moeda": "USD", "data": "2026-11-20"}, ana)
    assert depois["mensagem"] == "Nesta plataforma de demonstração, hoje é 15/10/2026. Escolha uma data até esse dia."
    assert servidor.pedidos == []


def test_modo_real_usa_o_dia_de_verdade_e_o_simulado_o_do_mock(servidor, ana, monkeypatch):
    sexta_real = datetime.combine(date(2026, 11, 20), time(15), FUSO_DA_COTACAO)
    monkeypatch.setattr(APIS, "agora_real", lambda: sexta_real)
    assert APIS.hoje() == date(2026, 11, 20)
    resposta = executar(COTACAO, {"moeda": "USD"}, ana)  # o servidor de teste não tem boletim de novembro
    assert resposta["tipo_erro"] == "nao_encontrado"
    primeira = next(c for c in pedidos_de_cotacao(servidor))
    assert primeira.split("@dataCotacao=")[1][:12] == "'11-20-2026'"
    monkeypatch.setenv("APIS_PUBLICAS_MODO", "simulado")
    assert APIS.hoje() == HOJE_DO_MOCK


def test_testar_no_modo_simulado_responde_sem_rede(servidor):
    assert APIS.testar({"APIS_PUBLICAS_MODO": "simulado"}) == MENSAGEM_TESTE_SIMULADO
    assert servidor.pedidos == []


def test_cotacao_e_cep_sao_liberados_para_todo_cargo_com_area_e_para_nenhum_transversal():
    mundo = mundo_do_mock()
    for cargo, id_funcionario in FUNCIONARIO_DO_CARGO.items():
        usuario = usuario_do_diretorio(mundo, id_funcionario)
        liberadas = set(catalogo.ferramentas_liberadas(usuario, AGENTE))
        esperado = set(AGENTE) if usuario.area else set()
        assert liberadas == esperado, cargo


def test_conector_recusa_moeda_ou_dia_fora_do_formato_antes_de_montar_a_url():
    for moeda in ("usd", "US", "USD'&@x='1"):
        with pytest.raises(ValueError):
            APIS.boletins(moeda, HOJE_DO_MOCK)
    with pytest.raises(ValueError):
        APIS.endereco("01310-100")
