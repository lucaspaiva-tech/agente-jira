"""Detalhe: tudo de um ticket e as ações humanas sobre ele. Abre a partir da seleção na Fila."""

import streamlit as st

from lib.config import ler_segredo
from lib.dados import (
    confirmar_reembolso,
    corrigir_autorizacao,
    editar_obs,
    enviar_ao_parceiro,
    ler_decisao,
    ler_reserva,
    ler_ticket,
    listar_eventos,
    marcar_acionar_operador,
    reabrir,
    registrar_decisao,
    resolver,
    reverter_envio,
)
from lib.dominio import (
    OPCOES_DECISAO,
    TEXTO_SITUACAO_REEMBOLSO,
    acao_principal,
    acoes_disponiveis,
    cor_sla,
    descrever_evento,
    descricao_destino_reembolso,
    descricao_multa,
    formatar_data_hora,
    formatar_real,
    formatar_viagem,
    link_jira,
    mensagem_de_erro,
    pode_editar_obs,
    pode_mudar_acionar_operador,
    rotulo_estado,
    situacao_reembolso,
    texto_sla,
    validar_decisao,
)

# Cor do domínio -> caixa nativa do Streamlit (DESIGN.md: cor semântica só carrega significado).
CAIXA_POR_COR = {"sucesso": st.success, "erro": st.error, "aviso": st.warning, "neutro": st.info}
COR_ETIQUETA = {"sucesso": "green", "erro": "red", "aviso": "orange", "neutro": "gray"}

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
        st.switch_page("telas/fila.py")


ticket_id = st.session_state.get("ticket_id")
if ticket_id is None:
    st.title("Detalhe")
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
    st.title("Detalhe")
    st.warning("Esse ticket não foi encontrado. Escolha outro na Fila.")
    ir_pra_fila()
    st.stop()

# Cabeçalho: o título é o próprio ticket; estado e SLA viram etiquetas (cor + palavra).
st.title(f"{ticket['jira_key']} · {ticket.get('empresa') or 'empresa não identificada'}")
etiquetas = [f":gray-badge[{rotulo_estado(ticket['estado'])}]"]
if (sla := texto_sla(ticket.get("situacao_sla"), ticket.get("sla_texto"))) != "—":
    etiquetas.append(f":{COR_ETIQUETA[cor_sla(ticket.get('situacao_sla'))]}-badge[SLA {sla}]")
st.markdown(" ".join(etiquetas))
st.caption(f"Recebido em {formatar_data_hora(ticket.get('recebido_em'))}")
link = link_jira(ler_segredo("JIRA_BASE_URL"), ticket["jira_key"])
if link:
    st.link_button("Abrir no Jira", link)
else:
    st.caption("Link do Jira indisponível: falta o segredo JIRA_BASE_URL.")
if ticket.get("erro"):
    st.error(f"Falha no processamento: {ticket['erro']}")


def executar(acao, *argumentos, sucesso: str):
    """Grava pela função de lib/dados.py. Deu certo: guarda o aviso e recarrega a tela."""
    try:
        resultado = acao(ticket["id"], *argumentos)
    except Exception as erro:
        st.error(mensagem_de_erro(erro))
        return
    if resultado is None:
        st.error("Não encontrei este ticket pra gravar. Recarregue a página.")
        return
    # O aviso sobrevive ao st.rerun() porque fica no session_state; é mostrado e apagado em seguida.
    st.session_state["aviso_acao"] = sucesso
    st.rerun()


if aviso := st.session_state.pop("aviso_acao", None):
    st.success(aviso)

acoes = acoes_disponiveis(ticket)
# Só o próximo passo do fluxo fica em rosa (DESIGN.md: o rosa é ação, não decoração).
principal = acao_principal(acoes)


def tipo(acao: str) -> str:
    return "primary" if acao == principal else "secondary"


destino_atual = descricao_destino_reembolso(ticket.get("destino_reembolso"))

with st.container(border=True):
    st.markdown("#### Ações")
    if not acoes:
        st.caption("Nenhuma ação de fluxo disponível neste estado.")

    if "enviar_ao_parceiro" in acoes:
        if st.button("📤 Enviar ao parceiro", type=tipo("enviar_ao_parceiro")):
            executar(enviar_ao_parceiro, sucesso="Envio pedido. O n8n vai escrever a linha na planilha do parceiro.")

    if "reverter_envio" in acoes:
        with st.popover("↩️ Reverter envio"):
            st.warning(
                "O ticket volta pra pendente e o SLA zera. A linha já copiada na planilha do parceiro "
                "**não é removida**: se precisar, apague lá à mão."
            )
            if st.button("Confirmar reversão"):
                executar(reverter_envio, sucesso="Envio revertido: o ticket voltou pra pendente.")

    if "registrar_decisao" in acoes:
        with st.form("decisao_manual"):
            st.markdown("**Decisão manual**")
            aprovado = st.radio("Podemos reembolsar?", OPCOES_DECISAO, index=None, horizontal=True)
            motivo = st.text_input("Motivo")
            if st.form_submit_button("Registrar decisão", type=tipo("registrar_decisao")):
                if problema := validar_decisao(aprovado, motivo):
                    st.warning(problema)
                else:
                    executar(registrar_decisao, aprovado, motivo, sucesso="Decisão registrada.")

    if "corrigir_autorizacao" in acoes:
        autorizado = bool(ticket.get("autorizado_lideranca"))
        # Só aparece nos status que admitem custo BX (pede_autorizacao): aí a autorização
        # é o que separa custo BX de multa do parceiro. Quem aplica a regra é o banco.
        destino_se_mudar = descricao_destino_reembolso("multa_parceiro" if autorizado else "custo_bx")
        st.markdown(f"**Autorização de liderança (TL ou supervisão):** {'sim' if autorizado else 'não'}")
        st.caption(f"Hoje o reembolso vai para: {destino_atual}. Se mudar, vai para: {destino_se_mudar}.")
        rotulo = "Desmarcar autorização de liderança" if autorizado else "Marcar autorização de liderança"
        if st.button(rotulo):
            executar(corrigir_autorizacao, not autorizado, sucesso="Autorização de liderança corrigida.")

    if "confirmar_reembolso" in acoes:
        with st.popover("💸 Confirmar reembolso", type=tipo("confirmar_reembolso")):
            st.markdown(f"O reembolso vai para: **{destino_atual}**.")
            if ticket.get("pede_autorizacao"):
                st.caption("Depois de confirmar, a autorização de liderança não pode mais ser mudada.")
            if st.button("Confirmar", type="primary"):
                executar(confirmar_reembolso, sucesso="Reembolso confirmado.")

    if "resolver" in acoes:
        if st.button("✅ Resolver", type=tipo("resolver")):
            executar(resolver, sucesso="Ticket resolvido.")

    if "reabrir" in acoes:
        if st.button("🔄 Reabrir"):
            executar(reabrir, sucesso="Ticket reaberto.")

    if pode_mudar_acionar_operador(ticket):
        st.divider()
        acionar = bool(ticket.get("acionar_operador"))
        st.markdown(f"**Acionar operador:** {'sim' if acionar else 'não'}")
        if st.button("Desmarcar acionar operador" if acionar else "Marcar acionar operador"):
            executar(marcar_acionar_operador, not acionar, sucesso="Acionar operador atualizado.")

    if pode_editar_obs(ticket):
        st.divider()
        with st.form("obs"):
            obs = st.text_area("OBS", value=ticket.get("obs") or "")
            if st.form_submit_button("Salvar OBS"):
                executar(editar_obs, obs, sucesso="OBS salva.")

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
