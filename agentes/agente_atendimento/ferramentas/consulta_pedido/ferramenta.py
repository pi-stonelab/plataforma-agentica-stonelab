import json

# [SUBSTITUIR: dados de exemplo; trocar por chamada real à API/banco de pedidos]
PEDIDOS = {
    "12345": {"status": "em transporte", "previsao_entrega": "2026-11-14", "itens": ["Fone Bluetooth"]},
    "67890": {"status": "entregue", "previsao_entrega": "2026-11-02", "itens": ["Capa de celular"]},
}


def executar(args: dict) -> str:
    numero = str(args.get("numero_pedido", "")).strip()
    if not numero:
        return "erro: informe o argumento 'numero_pedido'."
    pedido = PEDIDOS.get(numero)
    if pedido is None:
        return f"Pedido {numero} não encontrado."
    return json.dumps(pedido, ensure_ascii=False)
