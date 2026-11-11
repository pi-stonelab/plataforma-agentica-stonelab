"""Demonstração do loop com modelo roteirizado, sem rede: python -m testes.demo_loop"""

import json

from ferramentas import catalogo
from ferramentas.governanca import Usuario

FERRAMENTAS_DO_AGENTE = ("consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso")

CASO_FELIZ = [
    "LER: ",
    "LER: financeiro",
    "LER: financeiro/calcular_multa_atraso",
    'USAR: calcular_multa_atraso {"valor_fatura": 1000, "dias_atraso": 30}',
    "FINAL: A fatura fica em R$ 1030,00 com multa e juros.",
]
CASO_BLOQUEIOS = [
    'USAR: consultar_cliente {"id_cliente": "CLI-0002"}',
    'USAR: consultar_saldo_conta {"id_cliente": "CLI-0001"}',
    "FINAL: Não tenho acesso a esses dados.",
]


def resumo(texto):
    primeira_linha = texto.splitlines()[0] if texto else ""
    return f"{primeira_linha} ({len(texto.splitlines())} linhas)"


def rodar_passos(titulo, usuario, linhas):
    print(f"\n=== {titulo} (funcionário {usuario.nivel}, área {usuario.area}) ===")
    for numero, linha in enumerate(linhas, 1):
        print(f"--- passo {numero} ---")
        if linha.startswith("FINAL: "):
            print(f"  [FINAL] {linha[7:]}")
        elif linha.startswith("LER: "):
            caminho = linha[5:].strip()
            texto = catalogo.ler(caminho, usuario, FERRAMENTAS_DO_AGENTE)
            print(f"  [AÇÃO] ler '{caminho}'")
            print(f"  [RESULTADO] {resumo(texto)}")
        else:
            nome, _, argumentos = linha[6:].partition(" ")
            resultado = catalogo.executar(
                nome, json.loads(argumentos), usuario, FERRAMENTAS_DO_AGENTE
            )
            print(f"  [AÇÃO] executar '{nome}'")
            print(f"  [RESULTADO] {resultado['status']} | erro: {resultado['tipo_erro']}")
            if resultado["dados"]:
                print(f"  [DADOS] {resultado['dados']}")


if __name__ == "__main__":
    rodar_passos("Caso feliz", Usuario("U-0001", "N2", "financeiro"), CASO_FELIZ)
    atendente_n1 = Usuario("U-0002", "N1", "atendimento", carteira=("CLI-0001",))
    rodar_passos("Cliente fora da carteira e ferramenta bloqueada", atendente_n1, CASO_BLOQUEIOS)
