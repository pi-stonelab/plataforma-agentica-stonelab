"""Marcadores de pendência entre frentes: um formato só, que dá para buscar por nome e não chega ao modelo.

Os exemplos são montados por partes (`A_FAZER`, `DECIDIR`) para este arquivo não virar pendência na
listagem do repositório.
"""

from ferramentas import catalogo, pendencias

A_FAZER, DECIDIR = "[A FAZER" + " (", "[DECIDIR" + " ("


def test_todo_marcador_novo_do_repositorio_segue_o_formato():
    _, fora_do_formato, _ = pendencias.ler()
    assert fora_do_formato == []


def test_marcador_quebrado_em_comentario_e_com_duas_pessoas(tmp_path):
    (tmp_path / "exemplo.py").write_text(
        f"# {A_FAZER}Marcelo e Isabel, back-end, KAN-60): guardar os pedidos\n"
        "# numa tabela]\n"
        f"# {DECIDIR}Pedro): prazo de retenção]\n",
        "utf-8",
    )
    achados, fora_do_formato, _ = pendencias.ler(tmp_path)
    assert fora_do_formato == []
    primeiro, segundo = achados
    assert primeiro.pessoas == ("Marcelo", "Isabel") and primeiro.card == "KAN-60"
    assert primeiro.texto == "guardar os pedidos numa tabela" and primeiro.linha == 1
    assert (segundo.tipo, segundo.pessoas, segundo.frente) == ("DECIDIR", ("Pedro",), "")
    assert set(pendencias.por_pessoa(achados)) == {"Marcelo", "Isabel", "Pedro"}


def test_marcador_sem_o_que_fazer_e_acusado_e_exemplo_entre_crases_nao_conta(tmp_path):
    (tmp_path / "doc.md").write_text(
        f"Formato: `{A_FAZER}quem, frente, card): o que fazer]`\n{A_FAZER}Larissa) sem dois pontos]\n",
        "utf-8",
    )
    achados, fora_do_formato, _ = pendencias.ler(tmp_path)
    assert achados == [] and fora_do_formato == ["doc.md:2"]


def test_o_catalogo_tira_os_marcadores_antes_do_modelo():
    texto = f"Use assim. {A_FAZER}Marcelo, back-end): rota] Fim. {DECIDIR}Pedro e Brenno): regra]"
    assert catalogo.PADRAO_MARCADOR.sub("", texto) == "Use assim. Fim."
