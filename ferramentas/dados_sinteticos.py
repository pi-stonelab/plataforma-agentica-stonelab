"""Fachada do mock para as ferramentas: lê o banco por `mock/consultas.py` e devolve dicts.

Sem SQL aqui e nenhuma regra de permissão (isso é da governança). Banco ou sistema simulado fora do
ar vira ConnectionError, que `Ferramenta.executar` responde como `integracao_indisponivel`, sem
repassar o texto do erro. Valores em reais saem como texto ("R$ 1.842,30") para o modelo não
converter centavos.
"""

from mock import consultas
from mock.banco import criar_engine, url_padrao
from mock.falhas import SistemaIndisponivel
from sqlalchemy.exc import InterfaceError, OperationalError
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
    """Define o banco do mock: URL ou engine. Sem chamar, usa DATABASE_URL ou o SQLite local."""
    _CONEXAO["engine"] = criar_engine(origem) if isinstance(origem, str) else origem


def _ler(consulta, *argumentos):
    """Roda uma consulta do mock; banco ou sistema fora do ar vira ConnectionError."""
    try:
        if _CONEXAO["engine"] is None:
            _CONEXAO["engine"] = criar_engine(url_padrao())
        return consulta(_CONEXAO["engine"], *argumentos)
    except FALHAS_DE_INTEGRACAO:
        raise ConnectionError("integração indisponível") from None


def reais(centavos):
    """Centavos inteiros em texto no padrão brasileiro: 184230 vira "R$ 1.842,30"."""
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


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


def buscar_endereco(cep):
    """Endereço de um CEP público (3 CEPs de exemplo, sem rede e sem banco)."""
    if cep not in ENDERECOS:
        return None
    logradouro, bairro, cidade, uf = ENDERECOS[cep]
    return {"cep": cep, "logradouro": logradouro, "bairro": bairro, "cidade": cidade, "uf": uf}
