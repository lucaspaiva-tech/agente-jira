"""Visão geral: o que precisa de você agora, os números da fila e as pendências dos parceiros."""

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from lib.dados import listar_fila, listar_parceiros
from lib.dominio import (
    empresas_sem_parceiro_com_tickets,
    fila_de_urgencia,
    formatar_data_hora,
    resumo_da_fila,
    rotulo_estado_fila,
    texto_sla,
)

# Clique numa linha da tabela de urgentes: abre o Detalhe antes de ler o banco de novo.
if st.session_state.pop("abrir_detalhe", False):
    st.switch_page("telas/detalhe.py")

try:
    tickets = listar_fila()
    parceiros = listar_parceiros()
except Exception:
    st.title("Visão geral")
    st.error("Não consegui ler os dados agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()

resumo = resumo_da_fila(tickets)
urgentes = fila_de_urgencia(tickets)


def cartao_destaque(numero: int, detalhe: str) -> str:
    """Cartão grande em degradê rosa (paleta Buser). HTML próprio, com estilo só dentro dele."""
    return f"""
    <div style="position:relative; overflow:hidden; border-radius:0.75rem; padding:1.75rem 2rem;
                background:linear-gradient(110deg, #e6006a 0%, #f11075 55%, #fff7fa 100%);
                color:#ffffff; font-family:Inter, sans-serif;">
      <div style="position:absolute; right:3rem; top:1.25rem; width:4.5rem; height:4.5rem;
                  border-radius:50%; background:rgba(255,255,255,0.35);"></div>
      <div style="position:absolute; right:5.5rem; top:3.5rem; width:3rem; height:3rem;
                  border-radius:50%; background:rgba(255,255,255,0.25);"></div>
      <div style="font-size:1rem; font-weight:500;">Precisa de você</div>
      <div style="font-size:2.75rem; font-weight:700; line-height:1.2;">{numero} tickets</div>
      <div style="font-size:0.9rem; margin-top:0.25rem;">{detalhe}</div>
    </div>
    """


principal, lateral = st.columns([5, 2], gap="medium")

with principal:
    st.title("Visão geral")
    st.caption(f"{len(tickets)} tickets no total · atualizado em {formatar_data_hora(datetime.now(UTC))}")

    st.html(
        cartao_destaque(
            resumo["precisa_de_voce"],
            f"{resumo['pendentes']} pendentes · {resumo['sla_estourado']} com SLA estourado · "
            f"{resumo['respondidos']} respondidos · {resumo['falhas']} com falha",
        )
    )

    # Cartões de número: st.metric nativo, com ícone e borda.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendentes", resumo["pendentes"], icon=":material/pending_actions:", border=True)
    c2.metric("SLA estourado", resumo["sla_estourado"], icon=":material/alarm:", border=True)
    c3.metric("Respondidos", resumo["respondidos"], icon=":material/task_alt:", border=True)
    c4.metric("Com o parceiro", resumo["com_parceiro"], icon=":material/forward_to_inbox:", border=True)
    st.caption(
        "Respondidos: falta confirmar o reembolso ou resolver. "
        "SLA estourado: com o parceiro há mais de 48h sem resposta."
    )

    with st.container(border=True):
        st.markdown("#### Mais urgentes")
        if not urgentes:
            st.caption("Nada pedindo ação agora. 🎉")
        else:
            mostrar = urgentes[:10]
            st.caption(
                f"Mostrando {len(mostrar)} de {len(urgentes)}, do mais urgente pro menos. Clique numa linha pra abrir."
            )

            def abrir_ticket():
                """Chamada só quando a seleção MUDA: voltar pra cá não reabre o Detalhe sozinho."""
                linhas = st.session_state["tabela_urgentes"]["selection"]["rows"]
                if linhas:
                    st.session_state["ticket_id"] = mostrar[linhas[0]]["id"]
                    st.session_state["abrir_detalhe"] = True

            st.dataframe(
                pd.DataFrame(
                    {
                        "Chave Jira": [t["jira_key"] for t in mostrar],
                        "Empresa": [t.get("empresa") or "—" for t in mostrar],
                        "Estado": [rotulo_estado_fila(t) for t in mostrar],
                        # Sem "Recebido em": a ordem já é por urgência e antiguidade; a data fica na Fila.
                        "SLA": [texto_sla(t.get("situacao_sla"), t.get("sla_texto")) for t in mostrar],
                    }
                ),
                hide_index=True,
                width="stretch",
                on_select=abrir_ticket,
                selection_mode="single-row",
                column_config={"SLA": st.column_config.TextColumn(width="medium")},
                key="tabela_urgentes",
            )
            if st.button("Ver a fila completa", type="tertiary", icon=":material/arrow_forward:"):
                st.switch_page("telas/fila.py")

with lateral:
    pendentes = [p for p in parceiros if p.get("contato_pendente")]
    with st.container(border=True):
        st.markdown("#### Avisos aos parceiros")
        if pendentes:
            st.caption(f"{len(pendentes)} parceiro(s) com ticket novo na planilha, ainda sem aviso.")
            for parceiro in pendentes[:5]:
                st.markdown(f"- {parceiro['nome']}")
        else:
            st.caption("Nenhum aviso pendente.")
        if st.button("Abrir Parceiros", key="ir_avisos", type="primary" if pendentes else "secondary",
                     icon=":material/campaign:", width="stretch"):
            st.switch_page("telas/parceiros.py")

    sem_parceiro = empresas_sem_parceiro_com_tickets(
        [t.get("empresa") for t in tickets], [n for p in parceiros for n in p["nomes"]]
    )
    with st.container(border=True):
        st.markdown("#### Empresas sem parceiro")
        if sem_parceiro:
            st.caption("Tickets dessas empresas não chegam à planilha de ninguém.")
            for empresa, quantos in sem_parceiro[:6]:
                # Número na frente: a lista fica alinhada e o nome longo não quebra o número.
                st.markdown(f"**{quantos}** · {empresa}")
        else:
            st.caption("Toda empresa já tem parceiro.")
        if st.button("Ligar a um parceiro", key="ir_empresas", icon=":material/link:", width="stretch"):
            st.switch_page("telas/parceiros.py")
