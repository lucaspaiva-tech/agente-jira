"""Fila: lista os tickets do Marketplace com filtros. Clicar numa linha abre o ticket no Detalhe."""

import pandas as pd
import streamlit as st

from lib.dados import listar_fila
from lib.dominio import (
    ESTADOS,
    ESTADOS_PADRAO_FILA,
    contar_por_estado,
    cor_sla,
    filtrar_fila,
    formatar_data_hora,
    rotulo_estado,
    rotulo_estado_fila,
    texto_sla,
)

# Cor do texto do SLA, pela paleta do DESIGN.md (sucesso, erro e tinta-suave).
COR_TEXTO_SLA = {"sucesso": "#40b552", "erro": "#dc2e36", "neutro": "#757575"}

# Clique numa linha (ver abrir_ticket lá embaixo): abre o Detalhe antes de ler o banco de novo.
if st.session_state.pop("abrir_detalhe", False):
    st.switch_page("pages/detalhe.py")

st.title("Fila")

try:
    tickets = listar_fila()
except Exception:
    st.error("Não consegui ler os tickets agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()

# Contadores por estado (toda a fila, antes dos filtros)
contagem = contar_por_estado(tickets)
for coluna, estado in zip(st.columns(len(ESTADOS)), ESTADOS, strict=True):
    coluna.metric(rotulo_estado(estado), contagem[estado], border=True)

# Filtros
c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
estados = c1.multiselect("Estado", ESTADOS, default=ESTADOS_PADRAO_FILA, format_func=rotulo_estado, placeholder="Todos")
empresas = c2.multiselect("Empresa", sorted({t["empresa"] for t in tickets if t.get("empresa")}), placeholder="Todas")
status_ia = c3.multiselect(
    "Status da IA", sorted({t["status_ia"] for t in tickets if t.get("status_ia")}), placeholder="Todos"
)
busca = c4.text_input("Buscar", placeholder="Chave Jira ou reserva")

filtrados = filtrar_fila(tickets, estados, empresas, status_ia, busca)
st.caption(f"{len(filtrados)} de {len(tickets)} tickets")

if not filtrados:
    st.info("Nenhum ticket com esses filtros.")
    st.stop()

tabela = pd.DataFrame(
    {
        "Chave Jira": [t["jira_key"] for t in filtrados],
        "Empresa": [t.get("empresa") or "—" for t in filtrados],
        "Reserva": [t.get("reserva") or "—" for t in filtrados],
        "Status da IA": [t.get("status_ia") or "—" for t in filtrados],
        "Estado": [rotulo_estado_fila(t) for t in filtrados],
        "SLA": [texto_sla(t.get("situacao_sla"), t.get("sla_texto")) for t in filtrados],
        "Recebido em": [formatar_data_hora(t.get("recebido_em")) for t in filtrados],
    }
)
cores = [f"color: {COR_TEXTO_SLA[cor_sla(t.get('situacao_sla'))]}" for t in filtrados]
estilo = tabela.style.apply(lambda _: cores, subset=["SLA"])

st.caption("Clique numa linha pra abrir o ticket. ⚠️ no estado indica falha: o motivo aparece no detalhe.")


def abrir_ticket():
    """Chamada pelo Streamlit só quando a seleção MUDA: voltar pra Fila não reabre o Detalhe sozinho."""
    linhas = st.session_state["tabela_fila"]["selection"]["rows"]
    if linhas:
        # session_state guarda o id entre páginas: o Detalhe lê daqui.
        st.session_state["ticket_id"] = filtrados[linhas[0]]["id"]
        st.session_state["abrir_detalhe"] = True


st.dataframe(
    estilo,
    hide_index=True,
    width="stretch",
    on_select=abrir_ticket,
    selection_mode="single-row",
    # SLA mais largo: "🔴 Estourado · 2d 12h" não pode ser cortado, é a informação de urgência.
    column_config={"SLA": st.column_config.TextColumn(width="medium")},
    key="tabela_fila",
)
