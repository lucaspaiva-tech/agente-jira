import datetime as dt
import re
from pathlib import Path

import pandas as pd

from scripts import gerar_seed as g

MIGRATION = Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "001_schema.sql"
NOMES = {"Brasil Bus", "Expresso Diamante"}


def linha(**campos):
    base = {"ID Ticket": "MKTPL-1", "Empresa": "Brasil Bus", "Reserva": "ABC123"}
    base.update(campos)
    return base


def converter(**campos):
    return g.converter_ticket(linha(**campos), veio_de_resolvidos=False, nomes_mapeados=NOMES)


# ---------------------------------------------------------------- conversores
def test_numero_le_formato_brasileiro_e_ignora_traco():
    assert g.numero("R$ 1.289,50") == 1289.50
    assert g.numero("—") is None
    assert g.numero(None) is None
    assert g.numero(True) is None  # checkbox não é valor em reais


def test_timestamp_grava_com_fuso_de_sao_paulo():
    assert g.timestamp_sp(dt.datetime(2026, 7, 17, 15, 30)) == "2026-07-17 15:30:00-03"
    assert g.timestamp_sp("17/07/2026 15:30") == "2026-07-17 15:30:00-03"
    assert g.timestamp_sp("lixo") is None


def test_data_e_hora_aceitam_texto_e_objeto():
    assert g.data("17/07/2026") == "2026-07-17"
    assert g.data(pd.Timestamp("2026-07-17")) == "2026-07-17"
    assert g.hora("8:30") == "08:30:00"
    assert g.hora(dt.time(19, 0)) == "19:00:00"


def test_sql_escapa_aspas_e_aplica_cast():
    assert g.sql("D'Ávila") == "'D''Ávila'"
    assert g.sql(None) == "null"
    assert g.sql(None, "numeric") == "null::numeric"
    assert g.sql(12.5, "numeric") == "12.5::numeric"


# ---------------------------------------------------------------- tickets
def test_estados_importados():
    ticket = lambda **c: converter(**c)[0]["estado"]  # noqa: E731
    assert ticket() == "pendente"
    assert ticket(**{"Aprovado?": "Sim"}) == "decidido"
    assert ticket(**{"Enviar Parceiro": "Enviado ✅", "Acionar operador?": "Sim"}) == "enviado_parceiro"
    resolvido = g.converter_ticket(linha(**{"Aprovado?": "Sim"}), veio_de_resolvidos=True, nomes_mapeados=NOMES)
    assert resolvido[0]["estado"] == "resolvido"


def test_ticket_sem_id_e_ignorado():
    assert g.converter_ticket({"Empresa": "X"}, False, NOMES) is None


def test_enviado_sem_parceiro_ou_sem_operador_volta_pra_pendente_com_aviso():
    # o banco recusa 'enviado_parceiro' nessas condições, então a importação não pode mandar assim
    sem_parceiro = converter(**{"Empresa": "Empresa Sem Cadastro", "Enviar Parceiro": "Enviado ✅", "Acionar operador?": "Sim"})
    assert sem_parceiro[0]["estado"] == "pendente" and sem_parceiro[3]
    sem_operador = converter(**{"Enviar Parceiro": "Enviado ✅", "Acionar operador?": "Não"})
    assert sem_operador[0]["estado"] == "pendente" and sem_operador[3]


def test_multa_numerica_e_encontrada_e_texto_de_espera_e_aguardando():
    t = converter(**{"Multa Parceiro": 289.0})[0]
    assert (t["multa_valor"], t["multa_status"]) == (289.0, "encontrada")
    t = converter(**{"Multa Parceiro": "⏳ Aguardando registro no banco"})[0]
    assert (t["multa_valor"], t["multa_status"]) == (None, "aguardando")


def test_acionar_operador_tem_tres_estados():
    acionar = lambda v: converter(**{"Acionar operador?": v})[0]["acionar_operador"]  # noqa: E731
    assert acionar("Sim") is True
    assert acionar("Não") is False
    assert acionar(None) is None


def test_dado_do_passageiro_vai_so_pra_reserva_e_nao_pro_ticket():
    ticket, reserva, _, _ = converter(**{"Passageiro(os)": "Maria Teste", "Valor Repassado": 170.0})
    assert "nome_passageiro" not in ticket
    assert reserva["nome_passageiro"] == "Maria Teste" and reserva["valor_repassado"] == 170.0


def test_decisao_so_e_importada_quando_o_status_existe():
    assert converter(**{"Status JIRA": "Em Análise"})[2]["status_ia"] == "Em Análise"
    desconhecido = converter(**{"Status JIRA": "Status Inventado"})
    assert desconhecido[2] is None and desconhecido[3]
    assert converter()[2] is None  # sem status: sem decisão e sem aviso
    assert converter()[3] == []


def test_reembolso_confirmado_na_planilha_vira_data_aproximada():
    t = converter(**{"Reembolso": "Sim", "Data/Hora JIRA": "17/07/2026 15:30"})[0]
    assert t["reembolso_confirmado_em"] == "2026-07-17 15:30:00-03"
    assert converter(**{"Reembolso": "Aguardando"})[0]["reembolso_confirmado_em"] is None


def test_alinhado_fechado_como_custo_bx_vem_com_autorizacao_de_lideranca():
    alinhado_bx = converter(**{"Status JIRA": "Alinhado", "Multa Parceiro": "Custo assumido por BX"})
    assert alinhado_bx[0]["autorizado_lideranca"] is True
    assert alinhado_bx[2]["autorizado_lideranca"] is True
    alinhado_multa = converter(**{"Status JIRA": "Alinhado", "Multa Parceiro": 120.0})
    assert alinhado_multa[0]["autorizado_lideranca"] is False
    outro_status = converter(**{"Status JIRA": "Em Análise", "Multa Parceiro": "Custo assumido por BX"})
    assert outro_status[0]["autorizado_lideranca"] is False


def test_status_conhecidos_batem_com_a_tabela_do_banco():
    # Se alguém adicionar status em status_ia_regras e esquecer o gerador (ou o contrário), falha aqui.
    sql_migration = MIGRATION.read_text(encoding="utf-8")
    bloco = sql_migration.split("insert into public.status_ia_regras", 1)[1].split(";", 1)[0]
    do_banco = set(re.findall(r"\('([^']+)',\s*(?:true|false)", bloco))
    assert do_banco == g.STATUS_IA_CONHECIDOS


# ---------------------------------------------------------------- SQL gerado
def test_sql_gerado_e_idempotente_e_protege_ticket_do_motor():
    parceiros, nomes = g.montar_parceiros({})
    convertidos = [converter(**{"Status JIRA": "Em Análise", "Passageiro(os)": "Zé d'Ávila"})]
    saida = g.gerar_sql(parceiros, convertidos)
    assert "set local app.importando = 'sim'" in saida
    assert "on conflict (jira_key) do update set" in saida
    assert "where public.tickets.origem = 'importacao'" in saida     # nunca sobrescreve o motor
    assert "on conflict (nome) do update" in saida                    # nomes de parceiro
    assert "Zé d''Ávila" in saida                                     # aspas escapadas
    assert "where not exists (select 1 from public.decisoes_ia" in saida
    assert saida.strip().endswith("commit;")
    assert len(parceiros) > 0 and "Gran Express" in nomes


def test_mapeamento_agrupa_nomes_na_mesma_planilha():
    parceiros, _ = g.montar_parceiros({})
    diamante = next(p for p in parceiros if "Expresso Diamante" in p["nomes"])
    assert "Gran Express" in diamante["nomes"]
