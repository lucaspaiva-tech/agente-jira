"""Fila: lista os tickets do Marketplace com filtros. Clicar numa linha guarda o ticket pro Detalhe."""

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
)

# Cor do texto do SLA, pela paleta do DESIGN.md (sucesso, erro e tinta-suave).
COR_TEXTO_SLA = {"sucesso": "#40b552", "erro": "#dc2e36", "neutro": "#757575"}

st.title("📋 Fila")

try:
    tickets = listar_fila()
except Exception:
    st.error("Não consegui ler os tickets agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()

# Contadores por estado (toda a fila, antes dos filtros)
contagem = contar_por_estado(tickets)
for coluna, estado in zip(st.columns(len(ESTADOS)), ESTADOS, strict=True):
    coluna.metric(estado, contagem[estado])

# Filtros
c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
estados = c1.multiselect("Estado", ESTADOS, default=ESTADOS_PADRAO_FILA)
empresas = c2.multiselect("Empresa", sorted({t["empresa"] for t in tickets if t.get("empresa")}))
status_ia = c3.multiselect("Status da IA", sorted({t["status_ia"] for t in tickets if t.get("status_ia")}))
busca = c4.text_input("Buscar", placeholder="Chave Jira ou reserva")

filtrados = filtrar_fila(tickets, estados, empresas, status_ia, busca)
st.caption(f"{len(filtrados)} de {len(tickets)} tickets")

if not filtrados:
    st.info("Nenhum ticket com esses filtros.")
    st.stop()

tabela = pd.DataFrame(
    {
        "Chave Jira": [t["jira_key"] for t in filtrados],
        "Empresa": [t.get("empresa") for t in filtrados],
        "Reserva": [t.get("reserva") for t in filtrados],
        "Status da IA": [t.get("status_ia") for t in filtrados],
        "Estado": [t["estado"] for t in filtrados],
        "SLA": [t.get("sla_texto") or "—" for t in filtrados],
        "Recebido em": [formatar_data_hora(t.get("recebido_em")) for t in filtrados],
        "Erro": [t.get("erro") for t in filtrados],
    }
)
cores = [f"color: {COR_TEXTO_SLA[cor_sla(t.get('situacao_sla'))]}" for t in filtrados]
estilo = tabela.style.apply(lambda _: cores, subset=["SLA"])

# on_select="rerun" faz o clique numa linha recarregar a página já sabendo qual linha foi escolhida.
evento = st.dataframe(
    estilo,
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    key="tabela_fila",
)

if evento.selection.rows:
    escolhido = filtrados[evento.selection.rows[0]]
    # session_state guarda o id entre páginas: o Detalhe lê daqui.
    st.session_state["ticket_id"] = escolhido["id"]
    st.success(f"Ticket {escolhido['jira_key']} selecionado. Abra o Detalhe pra ver tudo.")
