from lib import tabela


def test_cabecalho_so_com_as_colunas_pedidas():
    html = tabela.cabecalho(["chave", "empresa", "sla"])
    assert "Chave Jira" in html and "Empresa" in html and "SLA" in html
    assert "Recebido em" not in html and "Status da IA" not in html
    # Mesma grade das linhas: uma fração por coluna, na proporção definida.
    assert "grid-template-columns:1.4fr 1.9fr 1.8fr" in html


def test_proporcoes_seguem_a_ordem_pedida():
    assert tabela.proporcoes(["sla", "chave"]) == [1.8, 1.4]
