from datetime import date, timedelta

NOMES_FANTASIA = (
    "Padaria Trigo Dourado",
    "Mercearia Horizonte",
    "Papelaria Folha Azul",
    "Oficina Roda Viva",
    "Floricultura Jardim Claro",
    "Farmácia Bem Perto",
    "Livraria Capítulo Dois",
    "Barbearia Navalha Fina",
)
SEGMENTOS = ("alimentação", "varejo", "serviços")
CIDADES = (("São Paulo", "SP"), ("Rio de Janeiro", "RJ"), ("Belo Horizonte", "MG"))
TIPOS_TRANSACAO = ("credito", "debito", "pix")
SITUACOES_TRANSACAO = ("aprovada", "aprovada", "aprovada", "estornada", "aprovada", "contestada")
QUANTIDADE_TRANSACOES = {"CLI-0001": 60, "CLI-0002": 12, "CLI-0003": 25, "CLI-0004": 8}

ENDERECOS = {
    "01310100": ("Avenida Paulista", "Bela Vista", "São Paulo", "SP"),
    "20040020": ("Rua da Quitanda", "Centro", "Rio de Janeiro", "RJ"),
    "30130010": ("Avenida Afonso Pena", "Centro", "Belo Horizonte", "MG"),
}


def _montar_clientes():
    clientes = {}
    for numero, nome in enumerate(NOMES_FANTASIA, start=1):
        cidade, uf = CIDADES[numero % len(CIDADES)]
        clientes[f"CLI-{numero:04d}"] = {
            "id_cliente": f"CLI-{numero:04d}",
            "nome_fantasia": nome,
            "segmento": SEGMENTOS[numero % len(SEGMENTOS)],
            "cidade": cidade,
            "uf": uf,
            "situacao": "inadimplente" if numero % 4 == 0 else "ativo",
            "cliente_desde": f"{2019 + numero % 6}-0{1 + numero % 9}-15",
        }
    return clientes


def _montar_transacoes(numero_cliente, quantidade):
    primeiro_dia = date(2026, 1, 3)
    return [
        {
            "id_transacao": f"TRX-{numero_cliente:04d}{i:03d}",
            "data": (primeiro_dia + timedelta(days=5 * i + numero_cliente)).isoformat(),
            "valor": round(40 + (i * 37 + numero_cliente * 11) % 460 + (i % 4) * 0.25, 2),
            "tipo": TIPOS_TRANSACAO[(i + numero_cliente) % len(TIPOS_TRANSACAO)],
            "situacao": SITUACOES_TRANSACAO[(i + numero_cliente) % len(SITUACOES_TRANSACAO)],
        }
        for i in range(quantidade)
    ]


CLIENTES = _montar_clientes()
TRANSACOES = {
    id_cliente: _montar_transacoes(int(id_cliente[-4:]), quantidade)
    for id_cliente, quantidade in QUANTIDADE_TRANSACOES.items()
}


def buscar_cliente(id_cliente):
    cliente = CLIENTES.get(id_cliente)
    return dict(cliente) if cliente else None


def buscar_transacoes(id_cliente, data_inicio, data_fim, limite):
    inicio = data_inicio.isoformat() if data_inicio else ""
    fim = data_fim.isoformat() if data_fim else "9999-12-31"
    no_periodo = [t for t in TRANSACOES.get(id_cliente, []) if inicio <= t["data"] <= fim]
    no_periodo.sort(key=lambda t: (t["data"], t["id_transacao"]), reverse=True)
    return [dict(t) for t in no_periodo[:limite]], len(no_periodo)


def buscar_endereco(cep):
    if cep not in ENDERECOS:
        return None
    logradouro, bairro, cidade, uf = ENDERECOS[cep]
    return {"cep": cep, "logradouro": logradouro, "bairro": bairro, "cidade": cidade, "uf": uf}
