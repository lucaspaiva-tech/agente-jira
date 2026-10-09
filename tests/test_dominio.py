from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from lib import dominio as d


# ---------------------------------------------------------------- aprovação e reembolso
@pytest.mark.parametrize("valor", ["Sim", "sim", " SIM ", "Aprovado", "Aprovado por falta de retorno em 48 horas"])
def test_aprovado(valor):
    assert d.classificar_aprovacao(valor) == "aprovado"


@pytest.mark.parametrize("valor", ["Não", "não", "Nao", " NAO "])
def test_reprovado(valor):
    assert d.classificar_aprovacao(valor) == "reprovado"


@pytest.mark.parametrize("valor", [None, "", "  ", "talvez", "reprovado"])
def test_indefinido(valor):
    # "reprovado" NÃO é "Não": só as duas grafias exatas reprovam, como na planilha antiga.
    assert d.classificar_aprovacao(valor) == "indefinido"


def test_situacao_do_reembolso():
    assert d.situacao_reembolso("Não", None) == "nao_cabe"
    assert d.situacao_reembolso("Sim", None) == "aguardando"
    assert d.situacao_reembolso("Sim", "2026-10-10T10:00:00Z") == "confirmado"
    assert d.situacao_reembolso(None, None) == "indefinido"
    # reprovado nunca vira confirmado, mesmo com data
    assert d.situacao_reembolso("Não", "2026-10-10T10:00:00Z") == "nao_cabe"


# ---------------------------------------------------------------- ações disponíveis
def ticket(**campos):
    base = {"estado": "pendente", "acionar_operador": True, "parceiro_id": 1,
            "aprovado": None, "reembolso_confirmado_em": None}
    base.update(campos)
    return base


def test_pendente_com_operador_e_parceiro_pode_enviar_e_decidir():
    assert d.acoes_disponiveis(ticket()) == ["enviar_ao_parceiro", "registrar_decisao"]


def test_nao_envia_sem_acionar_operador_ou_sem_parceiro():
    assert "enviar_ao_parceiro" not in d.acoes_disponiveis(ticket(acionar_operador=False))
    assert "enviar_ao_parceiro" not in d.acoes_disponiveis(ticket(acionar_operador=None))
    assert "enviar_ao_parceiro" not in d.acoes_disponiveis(ticket(parceiro_id=None))


def test_enviado_pode_reverter_e_decidir():
    assert d.acoes_disponiveis(ticket(estado="enviado_parceiro")) == ["reverter_envio", "registrar_decisao"]


def test_decidido_aprovado_pode_confirmar_reembolso_e_resolver():
    assert d.acoes_disponiveis(ticket(estado="decidido", aprovado="Sim")) == ["confirmar_reembolso", "resolver"]


def test_decidido_reprovado_so_pode_resolver():
    assert d.acoes_disponiveis(ticket(estado="decidido", aprovado="Não")) == ["resolver"]


def test_reembolso_ja_confirmado_nao_confirma_de_novo():
    t = ticket(estado="decidido", aprovado="Sim", reembolso_confirmado_em="2026-10-10T10:00:00Z")
    assert d.acoes_disponiveis(t) == ["resolver"]


def test_alinhado_pode_corrigir_a_autorizacao_ate_confirmar_o_reembolso():
    alinhado = ticket(estado="decidido", aprovado="Sim", acionar_operador=False, pede_autorizacao=True)
    assert d.acoes_disponiveis(alinhado) == ["corrigir_autorizacao", "confirmar_reembolso", "resolver"]
    confirmado = dict(alinhado, reembolso_confirmado_em="2026-10-10T10:00:00Z")
    assert "corrigir_autorizacao" not in d.acoes_disponiveis(confirmado)
    assert "corrigir_autorizacao" not in d.acoes_disponiveis(dict(alinhado, estado="resolvido"))


def test_sem_pede_autorizacao_nao_oferece_corrigir():
    for valor in (False, None):
        assert "corrigir_autorizacao" not in d.acoes_disponiveis(ticket(estado="decidido", aprovado="Sim", pede_autorizacao=valor))


def test_texto_do_destino_do_reembolso():
    assert d.descricao_destino_reembolso("custo_bx") == "Custo BX (autorizado por liderança)"
    assert d.descricao_destino_reembolso("multa_parceiro") == "Multa na carteira do parceiro"
    assert d.descricao_destino_reembolso(None) == ""


def test_resolvido_so_reabre_e_estados_do_n8n_nao_tem_acao():
    assert d.acoes_disponiveis(ticket(estado="resolvido")) == ["reabrir"]
    for estado in ("processando", "falha", "enviando"):
        assert d.acoes_disponiveis(ticket(estado=estado)) == []


# ---------------------------------------------------------------- multa
def test_multa_confere_com_tolerancia_de_um_centavo():
    assert d.multa_confere(289.00, 289.00)
    assert d.multa_confere(289.004, 289.00)
    assert not d.multa_confere(289.02, 289.00)
    assert not d.multa_confere(None, 289.00)
    assert not d.multa_confere(289.00, None)


def test_descricao_da_multa():
    assert d.descricao_multa("encontrada", 289.0, 289.0) == ("R$ 289,00", "sucesso")
    assert d.descricao_multa("encontrada", 100.0, 289.0) == ("R$ 100,00", "erro")
    assert d.descricao_multa("aguardando", None, 289.0) == ("⏳ Aguardando registro no banco", "aviso")
    assert d.descricao_multa("nao_encontrada", None, 289.0)[1] == "aviso"
    assert d.descricao_multa("custo_bx", None, 289.0) == ("Custo assumido por BX", "neutro")
    assert d.descricao_multa("erro", None, 289.0) == ("Erro na consulta", "erro")
    assert d.descricao_multa(None, None, 289.0) == ("", "neutro")


def test_cor_do_sla():
    assert d.cor_sla("estourado") == "erro"
    assert d.cor_sla("no_prazo") == "sucesso"
    assert d.cor_sla("nao_enviado") == "neutro"
    assert d.cor_sla("qualquer coisa") == "neutro"


# ---------------------------------------------------------------- formatação
def test_formatar_real():
    assert d.formatar_real(1234.5) == "R$ 1.234,50"
    assert d.formatar_real(0) == "R$ 0,00"
    assert d.formatar_real(-10) == "-R$ 10,00"
    assert d.formatar_real(None) == "—"


def test_formatar_data_hora_converte_para_sao_paulo():
    assert d.formatar_data_hora(datetime(2026, 10, 10, 15, 30, tzinfo=UTC)) == "10/10/2026 12:30"
    assert d.formatar_data_hora("2026-10-10T15:30:00Z") == "10/10/2026 12:30"
    assert d.formatar_data_hora("2026-10-10T15:30:00+00:00") == "10/10/2026 12:30"
    assert d.formatar_data_hora(None) == "—"
    assert d.formatar_data_hora("") == "—"


# ---------------------------------------------------------------- contato
@pytest.mark.parametrize("bruto, esperado", [
    ("(11) 99999-9999", "5511999999999"),
    ("11 3333-4444", "551133334444"),
    ("+55 11 99999-9999", "5511999999999"),
    ("5511999999999", "5511999999999"),
    ("", None),
    (None, None),
    ("sem numero", None),
])
def test_limpar_telefone(bruto, esperado):
    assert d.limpar_telefone(bruto) == esperado


def mensagem_do_link(url):
    return unquote(parse_qs(urlparse(url).query)["text"][0]) if "text=" in url else unquote(parse_qs(urlparse(url).query)["body"][0])


def test_whatsapp_individual_leva_a_mensagem_com_o_link_da_planilha():
    c = d.link_contato("(11) 99999-9999", "a@b.com", "ABC123")
    assert c["tipo"] == "whatsapp"
    assert c["url"].startswith("https://wa.me/5511999999999?text=")
    assert "https://docs.google.com/spreadsheets/d/ABC123/edit" in mensagem_do_link(c["url"])


def test_grupo_abre_o_whatsapp_sem_destinatario():
    c = d.link_contato(" Grupo ", None, "ABC123")
    assert c["tipo"] == "whatsapp_grupo"
    assert c["url"].startswith("https://wa.me/?text=")


def test_sem_whatsapp_cai_no_email_do_gmail():
    c = d.link_contato(None, "parceiro@empresa.com", "ABC123")
    assert c["tipo"] == "email"
    q = parse_qs(urlparse(c["url"]).query)
    assert q["to"] == ["parceiro@empresa.com"]
    assert q["su"] == [d.ASSUNTO_EMAIL_PARCEIRO]
    assert "Planilha: https://docs.google.com/spreadsheets/d/ABC123/edit" in q["body"][0]


def test_whatsapp_tem_prioridade_sobre_email():
    assert d.link_contato("11999999999", "a@b.com", "X")["tipo"] == "whatsapp"


def test_sem_nenhum_contato():
    assert d.link_contato(None, "  ", "X") == {"tipo": "sem_contato", "rotulo": "Sem contato cadastrado", "url": None}
    assert d.link_contato("sem numero", None, "X")["tipo"] == "sem_contato"


def test_empresas_sem_parceiro():
    assert d.empresas_sem_parceiro(["A", "B ", None, "", "C"], ["A", "C "]) == ["B"]
