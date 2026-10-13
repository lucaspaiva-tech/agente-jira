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


# ---------------------------------------------------------------- fila: filtros e contadores
FILA = [
    {"jira_key": "TESTE-3", "estado": "enviado_parceiro", "empresa": "Viação A", "reserva": "TST003", "status_ia": "Alinhado"},
    {"jira_key": "TESTE-4", "estado": "enviado_parceiro", "empresa": "Viação B", "reserva": "TST004", "status_ia": "Divergente"},
    {"jira_key": "TESTE-5", "estado": "decidido", "empresa": "Viação A", "reserva": "TST005", "status_ia": "Alinhado"},
    {"jira_key": "TESTE-50", "estado": "resolvido", "empresa": "Viação A", "reserva": "XYZ999", "status_ia": "Alinhado"},
    {"jira_key": "TESTE-9", "estado": "falha", "empresa": None, "reserva": None, "status_ia": None},
]


def chaves(tickets):
    return [t["jira_key"] for t in tickets]


def test_filtro_vazio_nao_restringe_nada():
    assert chaves(d.filtrar_fila(FILA)) == chaves(FILA)


def test_filtra_por_estado():
    assert chaves(d.filtrar_fila(FILA, estados=["enviado_parceiro"])) == ["TESTE-3", "TESTE-4"]


def test_filtra_por_empresa_e_status_da_ia():
    assert chaves(d.filtrar_fila(FILA, empresas=["Viação B"])) == ["TESTE-4"]
    assert chaves(d.filtrar_fila(FILA, status_ia=["Alinhado"])) == ["TESTE-3", "TESTE-5", "TESTE-50"]


def test_busca_pela_reserva_sem_ligar_pra_maiuscula():
    assert chaves(d.filtrar_fila(FILA, busca=" tst005 ")) == ["TESTE-5"]


def test_busca_pela_chave_jira():
    # "teste-5" também está dentro de "TESTE-50": a busca é por trecho, as duas aparecem.
    assert chaves(d.filtrar_fila(FILA, busca="teste-5")) == ["TESTE-5", "TESTE-50"]
    assert chaves(d.filtrar_fila(FILA, busca="TESTE-9")) == ["TESTE-9"]


def test_filtros_e_busca_valem_juntos():
    resultado = d.filtrar_fila(FILA, estados=["decidido", "enviado_parceiro"], empresas=["Viação A"], busca="tst")
    assert chaves(resultado) == ["TESTE-3", "TESTE-5"]


def test_contar_por_estado_segue_a_ordem_do_fluxo_e_mostra_zero():
    contagem = d.contar_por_estado(FILA)
    assert list(contagem) == list(d.ESTADOS)
    assert contagem["enviado_parceiro"] == 2
    assert contagem["pendente"] == 0
    assert sum(contagem.values()) == len(FILA)


def test_estados_padrao_da_fila_escondem_so_resolvido():
    assert "resolvido" not in d.ESTADOS_PADRAO_FILA
    assert set(d.ESTADOS_PADRAO_FILA) | {"resolvido"} == set(d.ESTADOS)


# ---------------------------------------------------------------- detalhe: link do Jira e linha do tempo
def test_link_jira():
    assert d.link_jira("https://buser.atlassian.net", "MKTPL-1") == "https://buser.atlassian.net/browse/MKTPL-1"
    # barra no fim da base não duplica
    assert d.link_jira("https://buser.atlassian.net/", "MKTPL-1") == "https://buser.atlassian.net/browse/MKTPL-1"


def test_link_jira_sem_base_ou_sem_chave_nao_monta_link():
    assert d.link_jira(None, "MKTPL-1") is None
    assert d.link_jira("  ", "MKTPL-1") is None
    assert d.link_jira("https://buser.atlassian.net", None) is None


def test_evento_de_criacao():
    assert d.descrever_evento({"campo": "criado", "de": None, "para": "pendente"}) == "Ticket criado em Pendente"


def test_evento_de_mudanca_usa_o_nome_do_campo_em_portugues():
    evento = {"campo": "estado", "de": "enviado_parceiro", "para": "enviando"}
    assert d.descrever_evento(evento) == "Estado: Com o parceiro → Enviando"


def test_evento_com_lado_vazio_mostra_traco():
    assert d.descrever_evento({"campo": "obs", "de": None, "para": "conferido"}) == "OBS: — → conferido"


def test_evento_booleano_vira_sim_e_nao():
    evento = {"campo": "autorizado_lideranca", "de": "false", "para": "true"}
    assert d.descrever_evento(evento) == "Autorização de liderança: não → sim"


def test_evento_de_data_sai_no_fuso_de_sao_paulo():
    evento = {"campo": "reembolso_confirmado_em", "de": None, "para": "2026-10-10T13:00:00+00:00"}
    assert d.descrever_evento(evento) == "Reembolso confirmado em: — → 10/10/2026 10:00"


def test_evento_de_campo_desconhecido_usa_o_nome_cru():
    assert d.descrever_evento({"campo": "novo_campo", "de": "a", "para": "b"}) == "novo_campo: a → b"


# ---------------------------------------------------------------- detalhe: viagem e reembolso
def test_formatar_viagem_nao_muda_o_dia_por_fuso():
    # data_viagem é só data: não pode virar meia-noite UTC e cair no dia anterior em SP.
    assert d.formatar_viagem("2026-10-01", "19:00:00") == "01/10/2026 às 19:00"


def test_formatar_viagem_sem_hora_ou_sem_data():
    assert d.formatar_viagem("2026-10-01", None) == "01/10/2026"
    assert d.formatar_viagem(None, "19:00:00") == "—"
    assert d.formatar_viagem(None, None) == "—"


@pytest.mark.parametrize("situacao", ["indefinido", "nao_cabe", "aguardando", "confirmado"])
def test_toda_situacao_de_reembolso_tem_texto(situacao):
    assert d.TEXTO_SITUACAO_REEMBOLSO[situacao].strip()


def test_texto_do_reembolso_confirmado():
    assert d.TEXTO_SITUACAO_REEMBOLSO[d.situacao_reembolso("Sim", "2026-10-04T23:10:01+00:00")] == "Reembolso confirmado"


def test_evento_de_nova_decisao_nao_mostra_o_id_interno():
    assert d.descrever_evento({"campo": "decisao_id", "de": None, "para": "311"}) == "Nova decisão da IA"


# ---------------------------------------------------------------- ações: validação e mensagem de erro
class ErroDoBanco(Exception):
    """Imita o APIError do supabase-py: a mensagem do raise exception vem em .message."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def test_transicao_recusada_vira_mensagem_simples():
    erro = ErroDoBanco("Transição de estado inválida: pendente -> resolvido (ticket TESTE-1)")
    texto = d.mensagem_de_erro(erro)
    assert "mudou de situação" in texto
    assert "->" not in texto


def test_autorizacao_depois_do_reembolso_vira_mensagem_simples():
    erro = ErroDoBanco("Reembolso já confirmado (ticket TESTE-13): a autorização de liderança não pode mais mudar.")
    assert "já foi confirmado" in d.mensagem_de_erro(erro)


def test_usuario_nao_identificado_pede_pra_abrir_pelo_hub():
    assert "Buser Hub" in d.mensagem_de_erro(PermissionError("sem e-mail"))


def test_erro_desconhecido_nao_mostra_o_texto_cru():
    texto = d.mensagem_de_erro(ConnectionError("https://xyz.supabase.co recusou a chave eyJhbGci"))
    assert "Diagnóstico" in texto
    assert "supabase.co" not in texto and "eyJ" not in texto


@pytest.mark.parametrize("aprovado, motivo", [("Sim", "Ok"), ("Não", "Passageiro não embarcou")])
def test_decisao_valida(aprovado, motivo):
    assert d.validar_decisao(aprovado, motivo) is None


@pytest.mark.parametrize("aprovado, motivo", [("Sim", "   "), ("Sim", None), ("Talvez", "x"), (None, "x")])
def test_decisao_invalida_explica_o_que_falta(aprovado, motivo):
    assert d.validar_decisao(aprovado, motivo)


@pytest.mark.parametrize("estado, pode", [("processando", False), ("falha", True), ("pendente", True),
                                          ("enviando", True), ("decidido", True), ("resolvido", True)])
def test_obs_so_nao_muda_enquanto_o_n8n_processa(estado, pode):
    assert d.pode_editar_obs({"estado": estado}) is pode


@pytest.mark.parametrize("estado, pode", [("processando", False), ("enviando", False), ("enviado_parceiro", False),
                                          ("falha", True), ("pendente", True), ("decidido", True), ("resolvido", True)])
def test_acionar_operador_fica_travado_durante_o_envio(estado, pode):
    # O banco exige acionar_operador marcado em enviando e enviado_parceiro
    # (constraint tickets_envio_exige_operador_e_parceiro): a tela nem oferece.
    assert d.pode_mudar_acionar_operador({"estado": estado}) is pode


def test_envio_sem_operador_recusado_pelo_banco_vira_mensagem_simples():
    erro = ErroDoBanco('new row for relation "tickets" violates check constraint '
                       '"tickets_envio_exige_operador_e_parceiro" Failing row contains (314, TESTE-1, ...)')
    texto = d.mensagem_de_erro(erro)
    assert "acionar operador" in texto
    assert "Failing row" not in texto


# ---------------------------------------------------------------- parceiros: contato
@pytest.mark.parametrize("whatsapp, email", [
    ("11 99999-9999", None), ("+55 (11) 3333-4444", ""), ("GRUPO", None), (" grupo ", None),
    (None, "parceiro@empresa.com"), ("", " parceiro@empresa.com.br "), (None, None),
])
def test_contato_valido(whatsapp, email):
    assert d.validar_contato(whatsapp, email) is None


@pytest.mark.parametrize("whatsapp, email, trecho", [
    ("9999", None, "WhatsApp"), ("ligar pro João", None, "WhatsApp"), ("11 99999-9999 (João)", None, "WhatsApp"),
    (None, "parceiro.empresa.com", "E-mail"), (None, "a@b", "E-mail"), (None, "a b@c.com", "E-mail"),
])
def test_contato_invalido_diz_qual_campo(whatsapp, email, trecho):
    assert trecho in d.validar_contato(whatsapp, email)


def test_mudancas_de_contato_traz_so_o_que_mudou_e_limpa_espacos():
    antes = [{"id": 1, "whatsapp": "11999999999", "email": None},
             {"id": 2, "whatsapp": None, "email": "a@b.com"},
             {"id": 3, "whatsapp": None, "email": None}]
    depois = [{"id": 1, "whatsapp": "11999999999", "email": " novo@b.com "},
              {"id": 2, "whatsapp": None, "email": "a@b.com"},
              {"id": 3, "whatsapp": "  ", "email": ""}]  # só espaço/vazio continua sendo "sem contato"
    assert d.mudancas_de_contato(antes, depois) == {1: {"email": "novo@b.com"}}


def test_apagar_um_contato_vira_vazio_de_verdade():
    antes = [{"id": 1, "whatsapp": "11999999999", "email": "a@b.com"}]
    depois = [{"id": 1, "whatsapp": "", "email": "a@b.com"}]
    assert d.mudancas_de_contato(antes, depois) == {1: {"whatsapp": None}}


def test_nome_ja_usado_recusado_pelo_banco_vira_mensagem_simples():
    erro = ErroDoBanco('duplicate key value violates unique constraint "parceiro_nomes_pkey"')
    texto = d.mensagem_de_erro(erro)
    assert "já está ligado a um parceiro" in texto
    assert "duplicate" not in texto


# ---------------------------------------------------------------- rodada 1 de UX: rótulos, SLA e ação principal
def test_todo_estado_tem_rotulo_em_portugues():
    for estado in d.ESTADOS:
        assert "_" not in d.rotulo_estado(estado)
    assert d.rotulo_estado("enviado_parceiro") == "Com o parceiro"


def test_estado_desconhecido_aparece_como_veio():
    assert d.rotulo_estado("novo_estado") == "novo_estado"


def test_estado_na_fila_sinaliza_ticket_com_erro():
    assert d.rotulo_estado_fila({"estado": "falha", "erro": "Databricks fora"}) == "⚠️ Falha"
    assert d.rotulo_estado_fila({"estado": "pendente", "erro": None}) == "Pendente"


@pytest.mark.parametrize("situacao, texto, esperado", [
    ("estourado", "2d 12h", "🔴 Estourado · 2d 12h"),
    ("no_prazo", "10h", "🟢 No prazo · 10h"),
    ("respondido", "1d 2h", "Respondido em 1d 2h"),
    ("nao_enviado", None, "—"),
    (None, None, "—"),
])
def test_sla_diz_a_situacao_em_palavras_e_nao_so_na_cor(situacao, texto, esperado):
    assert d.texto_sla(situacao, texto) == esperado


@pytest.mark.parametrize("acoes, principal", [
    (["enviar_ao_parceiro", "registrar_decisao"], "enviar_ao_parceiro"),
    (["reverter_envio", "registrar_decisao"], "registrar_decisao"),
    (["corrigir_autorizacao", "confirmar_reembolso", "resolver"], "confirmar_reembolso"),
    (["resolver"], "resolver"),
    (["reabrir"], None),  # reabrir é correção, não o próximo passo do fluxo
    ([], None),
])
def test_acao_principal_e_o_proximo_passo_do_fluxo(acoes, principal):
    assert d.acao_principal(acoes) == principal


# ---------------------------------------------------------------- visão geral
def tk(chave, estado, situacao_sla="nao_enviado", recebido="2026-10-01T10:00:00+00:00"):
    return {"jira_key": chave, "estado": estado, "situacao_sla": situacao_sla, "recebido_em": recebido}


VISAO = [
    tk("P-NOVO", "pendente", recebido="2026-10-09T10:00:00+00:00"),
    tk("P-VELHO", "pendente", recebido="2026-10-02T10:00:00+00:00"),
    tk("ESTOURADO", "enviado_parceiro", "estourado"),
    tk("NO-PRAZO", "enviado_parceiro", "no_prazo"),
    tk("ENVIANDO", "enviando"),
    tk("FALHA", "falha"),
    tk("DECIDIDO", "decidido", "respondido"),
    tk("RESOLVIDO", "resolvido", "respondido"),
    tk("PROCESSANDO", "processando"),
]


def test_resumo_da_fila_conta_cada_grupo():
    resumo = d.resumo_da_fila(VISAO)
    assert resumo == {"precisa_de_voce": 5, "pendentes": 2, "sla_estourado": 1, "respondidos": 1,
                      "falhas": 1, "com_parceiro": 3}


def test_precisa_de_voce_nao_conta_o_que_espera_outro():
    # Com o parceiro no prazo, enviando (n8n), processando (IA) e resolvido não pedem ação agora.
    for chave in ("NO-PRAZO", "ENVIANDO", "PROCESSANDO", "RESOLVIDO"):
        assert not d.precisa_de_voce(next(t for t in VISAO if t["jira_key"] == chave))


def test_fila_de_urgencia_poe_estourado_e_falha_na_frente_e_o_mais_antigo_primeiro():
    assert [t["jira_key"] for t in d.fila_de_urgencia(VISAO)] == [
        "ESTOURADO", "FALHA", "P-VELHO", "P-NOVO", "DECIDIDO"]


def test_resumo_de_fila_vazia():
    assert d.resumo_da_fila([])["precisa_de_voce"] == 0
    assert d.fila_de_urgencia([]) == []


def test_empresas_sem_parceiro_com_quantos_tickets_cada_uma_trava():
    empresas = ["Nena", "Ponce", "Nena ", "Ligada", None, "Nena"]
    assert d.empresas_sem_parceiro_com_tickets(empresas, ["Ligada"]) == [("Nena", 3), ("Ponce", 1)]


# ---------------------------------------------------------------- fila no estilo shadcn: grupos, cores e páginas
def test_decidido_aparece_como_respondido():
    assert d.rotulo_estado("decidido") == "Respondido"


@pytest.mark.parametrize("estado, grupo", [
    ("processando", "processando"), ("pendente", "pendente"), ("enviando", "com_parceiro"),
    ("enviado_parceiro", "com_parceiro"), ("decidido", "respondido"), ("falha", "falha"),
    ("resolvido", "resolvido"),
])
def test_cada_estado_cai_em_um_grupo_da_fila(estado, grupo):
    assert d.grupo_fila({"estado": estado}) == grupo


def test_grupos_da_fila_em_andamento_sao_os_cinco_pedidos():
    assert [d.ROTULO_GRUPO[g] for g in d.GRUPOS_EM_ANDAMENTO] == [
        "Processando", "Pendente", "Com o parceiro", "Respondido", "Falha"]


def test_estados_dos_grupos_traduz_pro_filtro_que_ja_existe():
    assert set(d.estados_dos_grupos(["com_parceiro", "falha"])) == {"enviando", "enviado_parceiro", "falha"}
    # Enviando entra no filtro "Com o parceiro": não some da fila.
    fila = [{"estado": "enviando"}, {"estado": "pendente"}]
    assert d.filtrar_fila(fila, estados=d.estados_dos_grupos(["com_parceiro"])) == [{"estado": "enviando"}]


def test_contar_por_grupo_junta_enviando_com_o_parceiro():
    fila = [{"estado": "enviando"}, {"estado": "enviado_parceiro"}, {"estado": "decidido"}, {"estado": "resolvido"}]
    contagem = d.contar_por_grupo(fila)
    assert contagem["com_parceiro"] == 2
    assert contagem["respondido"] == 1
    assert contagem["resolvido"] == 1
    assert contagem["pendente"] == 0


def test_cada_grupo_tem_cor_propria():
    cores = [d.COR_GRUPO[g] for g in d.GRUPOS_EM_ANDAMENTO]
    assert len(set(cores)) == len(cores)


def test_todo_status_conhecido_da_ia_tem_cor_propria():
    from scripts.gerar_seed import STATUS_IA_CONHECIDOS
    cores = [d.cor_status_ia(s) for s in STATUS_IA_CONHECIDOS]
    assert len(set(cores)) == len(STATUS_IA_CONHECIDOS)


def test_status_desconhecido_ou_vazio_fica_cinza():
    assert d.cor_status_ia("Status Novo") == "gray"
    assert d.cor_status_ia(None) == "gray"


def test_paginar_de_10_em_10():
    itens = list(range(23))
    assert d.paginar(itens, 1) == (list(range(10)), 1, 3)
    assert d.paginar(itens, 3) == ([20, 21, 22], 3, 3)


def test_paginar_corrige_pagina_fora_da_faixa():
    itens = list(range(23))
    assert d.paginar(itens, 9)[1:] == (3, 3)   # filtro reduziu a lista: vai pra última
    assert d.paginar(itens, 0)[1:] == (1, 3)


def test_paginar_lista_vazia_tem_uma_pagina():
    assert d.paginar([], 1) == ([], 1, 1)


@pytest.mark.parametrize("pagina, total, esperado", [
    (1, 49, "1–10 de 49"), (5, 49, "41–49 de 49"), (1, 7, "1–7 de 7"), (1, 0, "Nenhum ticket"),
])
def test_faixa_da_pagina(pagina, total, esperado):
    assert d.faixa_da_pagina(pagina, 10, total) == esperado
