from fastapi.testclient import TestClient

from app.main import app


def test_health_responde_ok_com_banco():
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco": "ok"}


def test_ferramentas_da_raiz_sao_importaveis():
    """O back-end precisa enxergar o catálogo da frente 4."""
    from ferramentas import catalogo

    assert "consultar_transacoes_cliente" in catalogo.carregar()
