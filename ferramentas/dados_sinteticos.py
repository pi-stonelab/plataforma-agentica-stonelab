"""Fachada do mock para as ferramentas: lê o banco por `mock/consultas.py` e devolve dicts.

Sem SQL aqui e nenhuma regra de permissão (isso é da governança). Banco ou sistema simulado fora do
ar vira ConnectionError, que `Ferramenta.executar` responde como `integracao_indisponivel`, sem
repassar o texto do erro. Valores em reais saem como texto ("R$ 1.842,30") para o modelo não
converter centavos.
"""

from mock import consultas
from mock.banco import criar_engine, url_padrao
from mock.falhas import SistemaIndisponivel
from mock.gerar import garantir_mundo_local
from sqlalchemy.exc import ArgumentError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as TempoEsgotadoNoPool

ENDERECOS = {
    "01310100": ("Avenida Paulista", "Bela Vista", "São Paulo", "SP"),
    "20040020": ("Rua da Quitanda", "Centro", "Rio de Janeiro", "RJ"),
    "30130010": ("Avenida Afonso Pena", "Centro", "Belo Horizonte", "MG"),
}
CAMPOS_DO_CADASTRO = (
    "codigo",
    "nome_fantasia",
    "segmento",
    "porte",
    "cidade",
    "uf",
    "situacao",
    "data_entrada",
)
FALHAS_DE_INTEGRACAO = (SistemaIndisponivel, OperationalError, InterfaceError, TempoEsgotadoNoPool)
_CONEXAO = {"engine": None}


def configurar(origem):
    """Define o banco do mock: URL ou engine.

    Sem chamar, vale `mock.banco.url_padrao()`: a variável MOCK_DATABASE_URL, se declarada, ou o
    SQLite local em dados_locais/, que é gerado sozinho na primeira vez. `DATABASE_URL` (banco da plataforma) nunca é usada.
    """
    _CONEXAO["engine"] = criar_engine(origem) if isinstance(origem, str) else origem


def _engine():
    """Engine do mock, criado na primeira consulta. URL inválida não repete o texto dela."""
    if _CONEXAO["engine"] is None:
        try:
            url = url_padrao()
            garantir_mundo_local(url)  # SQLite local novo: gera o mock na primeira vez
            _CONEXAO["engine"] = criar_engine(url)
        except (ValueError, ArgumentError, OSError, OperationalError):  # a mensagem pode trazer a senha
            raise ConnectionError("integração indisponível") from None
    return _CONEXAO["engine"]


def _ler(consulta, *argumentos):
    """Roda uma consulta do mock; banco ou sistema fora do ar vira ConnectionError."""
    try:
        return consulta(_engine(), *argumentos)
    except FALHAS_DE_INTEGRACAO:
        raise ConnectionError("integração indisponível") from None


def reais(centavos):
    """Centavos inteiros em texto no padrão brasileiro: 184230 vira "R$ 1.842,30"."""
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def buscar_funcionario(id_funcionario):
    """Cargo, área, carteiras e situação de um funcionário do diretório do mock, ou None."""
    return _ler(consultas.buscar_funcionario, id_funcionario)


def carteira_do_lojista(codigo):
    """Só o necessário para decidir o escopo (`carteira`), ou None se o lojista não existe."""
    return _ler(consultas.carteira_do_lojista, codigo)


def buscar_cliente(codigo):
    """Cadastro do lojista sem contatos nem conta (campos de CAMPOS_DO_CADASTRO), ou None."""
    lojista = _ler(consultas.buscar_lojista, codigo)
    return {campo: lojista[campo] for campo in CAMPOS_DO_CADASTRO} if lojista else None


def buscar_transacoes(codigo, data_inicio, data_fim, limite):
    """Vendas do lojista no período: (lista, total no período), da mais recente para a mais antiga."""
    resposta = _ler(consultas.buscar_vendas, codigo, data_inicio, data_fim, limite)
    vendas = [
        {
            "codigo": venda["codigo"],
            "data_hora": venda["data_hora"],
            "modalidade": venda["modalidade"],
            "parcelas": venda["parcelas"],
            "valor_bruto": reais(venda["valor_bruto_centavos"]),
            "valor_liquido": reais(venda["valor_liquido_centavos"]),
            "situacao": venda["situacao"],
        }
        for venda in resposta["itens"]
    ]
    return vendas, resposta["total"]


def buscar_liquidacoes(codigo, data_inicio, data_fim, limite):
    """Liquidações do lojista no período: (lista, total no período), da mais recente à mais antiga."""
    resposta = _ler(consultas.buscar_liquidacoes, codigo, data_inicio, data_fim, limite)
    liquidacoes = [
        {
            "id_liquidacao": item["id"],
            "data": item["data"],
            "valor": reais(item["valor_total_centavos"]),
            "situacao": item["situacao"],
            "motivo_falha": item["motivo_falha"],
        }
        for item in resposta["itens"]
    ]
    return liquidacoes, resposta["total"]


def buscar_faturas_em_atraso(codigo):
    """Faturas vencidas do lojista: (lista, total, soma dos valores da lista em texto)."""
    resposta = _ler(consultas.buscar_faturas, codigo, True)
    faturas = [
        {
            "codigo": item["codigo"],
            "tipo": item["tipo"],
            "mes_referencia": item["mes_referencia"],
            "vencimento": item["vencimento"],
            "valor": reais(item["valor_centavos"]),
            "situacao": item["situacao"],
            "dias_em_atraso": item["dias_em_atraso"],
        }
        for item in resposta["itens"]
    ]
    soma = sum(item["valor_centavos"] for item in resposta["itens"])
    return faturas, resposta["total"], reais(soma)


def buscar_chamados(codigo, limite):
    """Chamados do lojista, sem o resumo (texto livre): (lista, total), do mais recente ao mais antigo."""
    resposta = _ler(consultas.buscar_chamados, codigo, limite)
    campos = (
        "codigo",
        "protocolo",
        "categoria",
        "prioridade",
        "situacao",
        "aberto_por",
        "aberto_em",
        "dias_em_aberto",
        "id_liquidacao",
        "id_fatura",
    )
    return [{campo: item[campo] for campo in campos} for item in resposta["itens"]], resposta[
        "total"
    ]


def chamado_e_do_lojista(codigo, id_chamado):
    """Diz se o chamado pertence ao lojista. Chamado de outro lojista e inexistente dão False."""
    return _ler(consultas.chamado_e_do_lojista, codigo, id_chamado)


def buscar_interacoes(codigo, id_chamado, limite):
    """Mensagens do chamado DO LOJISTA, em ordem cronológica: (lista, total). Texto livre de terceiros."""
    resposta = _ler(consultas.buscar_interacoes, codigo, id_chamado, limite)
    return resposta["itens"], resposta["total"]


def buscar_contatos(codigo):
    """Contatos do lojista, em claro (a máscara é de `Ferramenta.executar`): (lista, total)."""
    resposta = _ler(consultas.buscar_contatos, codigo)
    return resposta["itens"], resposta["total"]


def buscar_endereco(cep):
    """Endereço de um CEP público (3 CEPs de exemplo, sem rede e sem banco)."""
    if cep not in ENDERECOS:
        return None
    logradouro, bairro, cidade, uf = ENDERECOS[cep]
    return {"cep": cep, "logradouro": logradouro, "bairro": bairro, "cidade": cidade, "uf": uf}
