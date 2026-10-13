"""Detalhe: tudo de um ticket, só leitura. Abre a partir da seleção na Fila."""

import streamlit as st

from lib.config import ler_segredo
from lib.dados import ler_decisao, ler_reserva, ler_ticket, listar_eventos
from lib.dominio import (
    TEXTO_SITUACAO_REEMBOLSO,
    descrever_evento,
    descricao_destino_reembolso,
    descricao_multa,
    formatar_data_hora,
    formatar_real,
    formatar_viagem,
    link_jira,
    situacao_reembolso,
)

# Cor do domínio -> caixa nativa do Streamlit (DESIGN.md: cor semântica só carrega significado).
CAIXA_POR_COR = {"sucesso": st.success, "erro": st.error, "aviso": st.warning, "neutro": st.info}

VALORES_DA_RESERVA = [
    ("Total pago", "valor_total_pago"),
    ("Valor da reserva", "valor_reserva"),
    ("Valor real", "valor_real"),
    ("Repassado ao parceiro", "valor_repassado"),
    ("Comissão", "comissao"),
    ("Taxa de serviço", "taxa_servico"),
    ("Seguro", "seguro"),
    ("Marcação de assento", "marcacao_assento"),
    ("Cupom", "cupom"),
]


def ou_traco(valor) -> str:
    return "—" if valor is None or str(valor).strip() == "" else str(valor)


def ir_pra_fila():
    if st.button("📋 Ir pra Fila"):
        st.switch_page("pages/fila.py")


st.title("🔎 Detalhe")

ticket_id = st.session_state.get("ticket_id")
if ticket_id is None:
    st.info("Escolha um ticket na Fila pra ver o detalhe.")
    ir_pra_fila()
    st.stop()

try:
    ticket = ler_ticket(ticket_id)
    reserva = ler_reserva(ticket_id) if ticket else None
    decisao = ler_decisao(ticket.get("decisao_id")) if ticket else None
    eventos = listar_eventos(ticket_id) if ticket else []
except Exception:
    st.error("Não consegui ler este ticket agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()

if ticket is None:
    st.warning("Esse ticket não foi encontrado. Escolha outro na Fila.")
    ir_pra_fila()
    st.stop()

# Cabeçalho
st.subheader(f"{ticket['jira_key']} · {ticket.get('empresa') or 'empresa não identificada'}")
st.caption(
    f"Estado: **{ticket['estado']}** · Recebido em {formatar_data_hora(ticket.get('recebido_em'))}"
    f" · SLA {ticket.get('sla_texto') or '—'}"
)
link = link_jira(ler_segredo("JIRA_BASE_URL"), ticket["jira_key"])
if link:
    st.link_button("Abrir no Jira", link)
else:
    st.caption("Link do Jira indisponível: falta o segredo JIRA_BASE_URL.")
if ticket.get("erro"):
    st.error(f"Falha no processamento: {ticket['erro']}")

viagem, passageiro = st.columns(2)

with viagem.container(border=True):
    st.markdown("#### Viagem")
    st.markdown(f"**Reserva:** {ou_traco(ticket.get('reserva'))}")
    st.markdown(f"**Trecho:** {ou_traco(ticket.get('origem_viagem'))} → {ou_traco(ticket.get('destino_viagem'))}")
    st.markdown(f"**Data:** {formatar_viagem(ticket.get('data_viagem'), ticket.get('hora_viagem'))}")
    st.markdown(f"**Parceiro:** {ou_traco(ticket.get('parceiro'))}")

with passageiro.container(border=True):
    st.markdown("#### Passageiro e valores")
    if reserva is None:
        st.caption("Ainda não há dados da reserva pra este ticket.")
    else:
        st.markdown(f"**Passageiro:** {ou_traco(reserva.get('nome_passageiro'))}")
        for rotulo, coluna in VALORES_DA_RESERVA:
            st.markdown(f"**{rotulo}:** {formatar_real(reserva.get(coluna))}")

with st.container(border=True):
    st.markdown("#### Decisão da IA")
    if decisao is None:
        st.caption("A IA ainda não decidiu este ticket.")
    else:
        st.markdown(f"**Status:** {decisao['status_ia']}")
        st.markdown(f"**Resumo:** {ou_traco(decisao.get('resumo_motivo'))}")
        st.markdown(f"**Parecer:** {ou_traco(decisao.get('parecer'))}")
        st.caption(
            f"Prompt {decisao['prompt_versao']} · modelo {ou_traco(decisao.get('modelo'))}"
            f" · {formatar_data_hora(decisao.get('criado_em'))}"
        )

parceiro, reembolso = st.columns(2)

with parceiro.container(border=True):
    st.markdown("#### Resposta do parceiro")
    st.markdown(f"**Podemos reembolsar?** {ou_traco(ticket.get('aprovado'))}")
    st.markdown(f"**Motivo:** {ou_traco(ticket.get('motivo_parceiro'))}")
    st.markdown(f"**OBS:** {ou_traco(ticket.get('obs'))}")

with reembolso.container(border=True):
    st.markdown("#### Reembolso")
    situacao = situacao_reembolso(ticket.get("aprovado"), ticket.get("reembolso_confirmado_em"))
    st.markdown(f"**Situação:** {TEXTO_SITUACAO_REEMBOLSO[situacao]}")
    if ticket.get("reembolso_confirmado_em"):
        st.caption(f"Confirmado em {formatar_data_hora(ticket['reembolso_confirmado_em'])}")
    st.markdown(f"**Vai para:** {descricao_destino_reembolso(ticket.get('destino_reembolso'))}")
    if ticket.get("pede_autorizacao"):
        autorizado = "sim" if ticket.get("autorizado_lideranca") else "não"
        st.markdown(f"**Autorização de liderança (TL ou supervisão):** {autorizado}")

    repassado = reserva.get("valor_repassado") if reserva else None
    texto, cor = descricao_multa(ticket.get("multa_status"), ticket.get("multa_valor"), repassado)
    if texto and ticket.get("multa_status") == "encontrada":
        # Multa encontrada: verde se bate com o repassado, vermelho se não bate.
        CAIXA_POR_COR[cor](f"Multa: {texto} · repassado: {formatar_real(repassado)}")
    elif texto:
        CAIXA_POR_COR[cor](f"Multa: {texto}")
    else:
        st.caption("Multa: nenhuma registrada.")

with st.container(border=True):
    st.markdown("#### Linha do tempo")
    if not eventos:
        st.caption("Sem eventos registrados.")
    for evento in eventos:
        st.markdown(
            f"**{formatar_data_hora(evento.get('criado_em'))}** · {descrever_evento(evento)}"
            f" · _{ou_traco(evento.get('autor'))}_"
        )
