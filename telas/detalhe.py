"""Detalhe: um ticket com o contexto à esquerda e a ação à direita.

Cabeçalho com navegação (Fila, Anterior, Próximo), indicador de etapas do fluxo, cartões diferentes
por tipo de conteúdo (parecer, valores, viagem, resposta, histórico) e uma coluna de ação com o
próximo passo, o reembolso e as notas internas. Confirmações em janela (st.dialog).
"""

from datetime import UTC, datetime
from html import escape

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
    COR_GRUPO,
    OPCOES_DECISAO,
    ROTULO_GRUPO,
    acao_principal,
    acoes_disponiveis,
    classificar_aprovacao,
    cor_sla,
    cor_status_ia,
    descrever_evento,
    descricao_destino_reembolso,
    descricao_multa,
    eh_automatico,
    etapas_do_ticket,
    formatar_data_hora,
    formatar_real,
    formatar_viagem,
    grupo_fila,
    itens_reembolso,
    link_jira,
    mensagem_de_erro,
    multa_confere,
    pode_editar_obs,
    pode_mudar_acionar_operador,
    proximo_passo,
    tempo_relativo,
    texto_sla,
    validar_decisao,
    vizinhos,
)

AGORA = datetime.now(UTC)
COR_ETIQUETA = {"sucesso": "green", "erro": "red", "aviso": "orange", "neutro": "gray"}
EVENTOS_VISIVEIS = 8
VALORES_SECUNDARIOS = [
    ("Valor da reserva", "valor_reserva"),
    ("Valor real", "valor_real"),
    ("Comissão", "comissao"),
    ("Taxa de serviço", "taxa_servico"),
    ("Seguro", "seguro"),
    ("Marcação de assento", "marcacao_assento"),
    ("Cupom", "cupom"),
]
# Ícone e cor de cada linha da lista de status do reembolso.
ITEM_REEMBOLSO = {
    "feito": ("green", ":material/check_circle:"),
    "esperando": ("orange", ":material/schedule:"),
    "pendente": ("gray", ":material/radio_button_unchecked:"),
    "alerta": ("red", ":material/error:"),
    "nao_se_aplica": ("gray", ":material/block:"),
}
# Rótulo e ícone de cada ação (a regra de quando aparece é de dominio.acoes_disponiveis).
ROTULO_ACAO = {
    "enviar_ao_parceiro": ("Enviar ao parceiro", ":material/send:"),
    "registrar_decisao": ("Registrar decisão", ":material/gavel:"),
    "confirmar_reembolso": ("Confirmar reembolso", ":material/payments:"),
    "resolver": ("Resolver", ":material/task_alt:"),
    "reverter_envio": ("Reverter envio", ":material/undo:"),
    "reabrir": ("Reabrir", ":material/replay:"),
}


def ou_traco(valor) -> str:
    return "—" if valor is None or str(valor).strip() == "" else str(valor)


def ir_pra_fila(rotulo="Fila"):
    if st.button(rotulo, icon=":material/arrow_back:", type="tertiary"):
        st.switch_page("telas/fila.py")


# Leitura ------------------------------------------------------------------------------------
ticket_id = st.session_state.get("ticket_id")
if ticket_id is None:
    st.title("Detalhe")
    st.info("Escolha um ticket na Fila pra ver o detalhe.", icon=":material/touch_app:")
    ir_pra_fila("Ir pra Fila")
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
    ir_pra_fila("Ir pra Fila")
    st.stop()

acoes = acoes_disponiveis(ticket)
principal = acao_principal(acoes)
repassado = reserva.get("valor_repassado") if reserva else None


# Gravação -----------------------------------------------------------------------------------
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


def ao_mudar_chave(acao, chave: str, sucesso: str):
    """Chave de liga e desliga: grava quando muda. Se o banco recusar, a chave volta ao valor salvo."""
    try:
        acao(ticket["id"], st.session_state[chave])
        st.session_state["aviso_acao"] = sucesso
    except Exception as erro:
        st.session_state["erro_acao"] = mensagem_de_erro(erro)
        del st.session_state[chave]


@st.dialog("Registrar decisão")
def janela_decisao():
    st.caption("A decisão manual fecha o ticket como respondido.")
    aprovado = st.radio("Podemos reembolsar?", OPCOES_DECISAO, index=None, horizontal=True)
    motivo = st.text_area("Motivo", placeholder="Ex.: viagem cancelada pela empresa")
    if st.button("Registrar", type="primary", width="stretch"):
        if problema := validar_decisao(aprovado, motivo):
            st.warning(problema)
        else:
            executar(registrar_decisao, aprovado, motivo, sucesso="Decisão registrada.")


@st.dialog("Reverter envio")
def janela_reverter():
    st.warning(
        "O ticket volta pra pendente e o SLA zera. A linha já copiada na planilha do parceiro "
        "**não é removida**: se precisar, apague lá à mão.",
        icon=":material/warning:",
    )
    if st.button("Reverter", type="primary", width="stretch"):
        executar(reverter_envio, sucesso="Envio revertido: o ticket voltou pra pendente.")


@st.dialog("Confirmar reembolso")
def janela_reembolso():
    st.markdown(f"O reembolso vai para: **{descricao_destino_reembolso(ticket.get('destino_reembolso'))}**.")
    if ticket.get("pede_autorizacao"):
        st.caption("Depois de confirmar, a autorização de liderança não pode mais ser mudada.")
    if st.button("Confirmar", type="primary", width="stretch"):
        executar(confirmar_reembolso, sucesso="Reembolso confirmado.")


def fazer(acao: str):
    """O que cada botão de ação faz: confirmações abrem janela, o resto grava direto."""
    if acao == "enviar_ao_parceiro":
        executar(enviar_ao_parceiro, sucesso="Envio pedido. O n8n vai escrever a linha na planilha do parceiro.")
    elif acao == "registrar_decisao":
        janela_decisao()
    elif acao == "confirmar_reembolso":
        janela_reembolso()
    elif acao == "reverter_envio":
        janela_reverter()
    elif acao == "resolver":
        executar(resolver, sucesso="Ticket resolvido.")
    elif acao == "reabrir":
        executar(reabrir, sucesso="Ticket reaberto.")


# Blocos de HTML isolados (DESIGN.md): estilo só dentro deles, texto sempre escapado ------------
def indicador_de_etapas(etapas) -> str:
    cor = {"concluida": "#40b552", "atual": "#e6006a", "falha": "#dc2e36", "pendente": "#e0e0e0",
           "pulada": "#e0e0e0"}
    marca = {"concluida": "✓", "atual": "", "falha": "✕", "pendente": "", "pulada": "–"}
    partes = []
    for i, etapa in enumerate(etapas):
        situacao = etapa["estado"]
        cheia = situacao in ("concluida", "falha")
        bolinha = (
            f"background:{cor[situacao]}; color:#fff;" if cheia
            else f"background:#fff; border:2px solid {cor[situacao]}; color:#757575;"
        )
        if situacao == "atual":
            bolinha += " box-shadow:0 0 0 4px #fff7fa;"
        quando = formatar_data_hora(etapa["quando"]) if etapa["quando"] else (
            "não passou" if situacao == "pulada" else "")
        peso = "600" if situacao in ("atual", "falha") else "500"
        texto = "#454545" if situacao != "pendente" else "#757575"
        partes.append(f"""
          <div style="flex:1; text-align:center; position:relative;">
            <div style="width:1.75rem; height:1.75rem; margin:0 auto; border-radius:50%; {bolinha}
                        display:flex; align-items:center; justify-content:center; font-size:0.85rem;
                        font-weight:700; position:relative; z-index:1;">{marca[situacao]}</div>
            <div style="margin-top:0.4rem; font-size:0.85rem; font-weight:{peso}; color:{texto};">
              {escape(etapa["nome"])}</div>
            <div style="font-size:0.75rem; color:#757575; min-height:1rem;">{escape(quando)}</div>
          </div>""")
        if i < len(etapas) - 1:
            # A linha só fica verde entre duas etapas concluídas (não promete o que não aconteceu).
            ligada = situacao in ("concluida", "pulada") and etapas[i + 1]["estado"] in ("concluida", "pulada")
            partes.append(f"""<div style="flex:0.6; height:2px; margin-top:0.85rem;
                              background:{'#40b552' if ligada else '#e0e0e0'};"></div>""")
    return f"""<div style="display:flex; align-items:flex-start; font-family:Inter, sans-serif;
               padding:0.5rem 0;">{''.join(partes)}</div>"""


def historico(lista) -> str:
    itens = []
    for i, evento in enumerate(lista):
        autor = ou_traco(evento.get("autor"))
        icone = "🤖" if eh_automatico(autor) else "👤"
        # A linha vertical é absoluta (não ocupa espaço); no último evento ela só não aparece.
        linha = "position:absolute; left:0.9rem; top:2rem; bottom:-0.5rem; width:2px; background:#e0e0e0;" + (
            " display:none;" if i == len(lista) - 1 else "")
        itens.append(f"""
          <div style="display:flex; gap:0.75rem; position:relative; padding-bottom:1rem;">
            <div style="{linha}"></div>
            <div style="flex:none; width:1.8rem; height:1.8rem; border-radius:50%; background:#fafafa;
                        border:1px solid #e0e0e0; display:flex; align-items:center; justify-content:center;
                        font-size:0.85rem; position:relative; z-index:1;">{icone}</div>
            <div>
              <div style="font-size:0.9rem; color:#454545; font-weight:500;">
                {escape(descrever_evento(evento))}</div>
              <div style="font-size:0.78rem; color:#757575;">
                {escape(autor)} · {escape(tempo_relativo(evento.get("criado_em"), AGORA))}
                · {escape(formatar_data_hora(evento.get("criado_em")))}</div>
            </div>
          </div>""")
    return f"<div style='font-family:Inter, sans-serif; padding-top:0.25rem;'>{''.join(itens)}</div>"


def rotulo_e_valor(coluna, rotulo: str, valor: str):
    coluna.caption(rotulo)
    coluna.markdown(valor)


# Avisos de ações anteriores -------------------------------------------------------------------
if aviso := st.session_state.pop("aviso_acao", None):
    st.toast(aviso, icon=":material/check_circle:")
if erro_acao := st.session_state.pop("erro_acao", None):
    st.error(erro_acao)

# Cabeçalho ---------------------------------------------------------------------------------------
lista = st.session_state.get("_lista_detalhe", [])
anterior, proximo = vizinhos(lista, ticket["id"])
voltar, navegar = st.columns([3, 2], vertical_alignment="center")
with voltar:
    ir_pra_fila()
with navegar.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
    if lista and ticket["id"] in lista:
        st.caption(f"{lista.index(ticket['id']) + 1} de {len(lista)}")
    if st.button("Anterior", icon=":material/chevron_left:", disabled=anterior is None):
        st.session_state["ticket_id"] = anterior
        st.rerun()
    if st.button("Próximo", icon=":material/chevron_right:", icon_position="right", disabled=proximo is None):
        st.session_state["ticket_id"] = proximo
        st.rerun()

titulo, numero_reserva, jira = st.columns([2.5, 1.5, 1], vertical_alignment="center")
titulo.title(ticket["jira_key"])
if ticket.get("reserva"):
    # Em destaque: é o número que se busca no admin da Buser (duplo clique seleciona pra copiar).
    numero_reserva.metric("Reserva", ticket["reserva"], icon=":material/confirmation_number:", border=True)
link = link_jira(ler_segredo("JIRA_BASE_URL"), ticket["jira_key"])
if link:
    jira.link_button("Abrir no Jira", link, icon=":material/open_in_new:", width="stretch")

contexto = [ticket.get("empresa") or "Empresa não identificada"]
if ticket.get("reserva"):
    contexto.append(f"Reserva {ticket['reserva']}")
contexto.append(f"recebido {tempo_relativo(ticket.get('recebido_em'), AGORA)}"
                f" ({formatar_data_hora(ticket.get('recebido_em'))})")
st.caption(" · ".join(contexto))

grupo = grupo_fila(ticket)
etiquetas = [f":{COR_GRUPO.get(grupo, 'gray')}-badge[{ROTULO_GRUPO.get(grupo, ticket['estado'])}]"]
if (sla := texto_sla(ticket.get("situacao_sla"), ticket.get("sla_texto"))) != "—":
    etiquetas.append(f":{COR_ETIQUETA[cor_sla(ticket.get('situacao_sla'))]}-badge[SLA {sla}]")
if ticket.get("status_ia"):
    etiquetas.append(f":{cor_status_ia(ticket['status_ia'])}-badge[:material/smart_toy: {ticket['status_ia']}]")
st.markdown(" ".join(etiquetas))

if ticket.get("erro"):
    st.error(f"Falha no processamento: {ticket['erro']}", icon=":material/error:")

with st.container(border=True):
    st.html(indicador_de_etapas(etapas_do_ticket(ticket)))

conteudo, lateral = st.columns([2, 1], gap="medium")

# Coluna principal: contexto ----------------------------------------------------------------------
with conteudo:
    with st.container(border=True):
        st.markdown("#### :material/smart_toy: Parecer da IA")
        if decisao is None:
            st.caption("A IA ainda não analisou este ticket. O parecer aparece aqui assim que sair.")
        else:
            st.markdown(f":{cor_status_ia(decisao['status_ia'])}-badge[{decisao['status_ia']}]")
            if decisao.get("resumo_motivo"):
                st.markdown(f"##### {decisao['resumo_motivo']}")
            if decisao.get("parecer"):
                st.markdown(f"> {decisao['parecer']}")
            st.caption(
                f"Prompt {decisao['prompt_versao']} · modelo {ou_traco(decisao.get('modelo'))}"
                f" · {formatar_data_hora(decisao.get('criado_em'))}"
            )

    with st.container(border=True):
        st.markdown("#### :material/payments: Valores")
        if reserva is None:
            st.caption("Ainda não há dados da reserva pra este ticket.")
        else:
            total, repasse, multa = st.columns(3)
            total.metric("Total pago", formatar_real(reserva.get("valor_total_pago")))
            repasse.metric("Repassado ao parceiro", formatar_real(repassado))
            if ticket.get("multa_status") == "encontrada":
                confere = multa_confere(ticket.get("multa_valor"), repassado)
                multa.metric("Multa", formatar_real(ticket.get("multa_valor")),
                             delta="igual ao repassado" if confere else "diferente do repassado",
                             delta_color="green" if confere else "red", delta_arrow="off")
            else:
                motivo = descricao_multa(ticket.get("multa_status"), None, None)[0].lstrip("⏳⚠️ ")
                multa.metric("Multa", "—", delta=motivo or None, delta_color="gray", delta_arrow="off")
            with st.expander("Ver composição do valor"):
                pares = st.columns(2)
                for i, (rotulo, coluna) in enumerate(VALORES_SECUNDARIOS):
                    rotulo_e_valor(pares[i % 2], rotulo, formatar_real(reserva.get(coluna)))

    with st.container(border=True):
        st.markdown("#### :material/directions_bus: Viagem")
        st.markdown(f"##### {ou_traco(ticket.get('origem_viagem'))} → {ou_traco(ticket.get('destino_viagem'))}")
        quando, passageiro, parceiro = st.columns(3)
        rotulo_e_valor(quando, "Data e hora", formatar_viagem(ticket.get("data_viagem"), ticket.get("hora_viagem")))
        rotulo_e_valor(passageiro, "Passageiro", ou_traco(reserva.get("nome_passageiro") if reserva else None))
        rotulo_e_valor(parceiro, "Parceiro", ou_traco(ticket.get("parceiro")))

    with st.container(border=True):
        st.markdown("#### :material/forum: Resposta do parceiro")
        resposta = classificar_aprovacao(ticket.get("aprovado"))
        if resposta == "indefinido" and not ticket.get("motivo_parceiro"):
            st.caption("O parceiro ainda não respondeu.")
        else:
            cor_resposta = {"aprovado": "green", "reprovado": "red"}.get(resposta, "gray")
            st.markdown(f":{cor_resposta}-badge[Podemos reembolsar? {ou_traco(ticket.get('aprovado'))}]")
            if ticket.get("motivo_parceiro"):
                st.markdown(f"> {ticket['motivo_parceiro']}")

    with st.container(border=True):
        st.markdown("#### :material/history: Histórico")
        if not eventos:
            st.caption("Sem eventos registrados.")
        else:
            st.html(historico(eventos[:EVENTOS_VISIVEIS]))
            if len(eventos) > EVENTOS_VISIVEIS:
                with st.expander(f"Ver histórico completo ({len(eventos)} eventos)"):
                    st.html(historico(eventos[EVENTOS_VISIVEIS:]))

# Coluna de ação ----------------------------------------------------------------------------------
with lateral:
    with st.container(border=True):
        titulo_passo, texto_passo = proximo_passo(ticket, acoes)
        st.markdown(f"#### :material/bolt: {titulo_passo}")
        st.caption(texto_passo)
        if principal:
            rotulo, icone = ROTULO_ACAO[principal]
            if st.button(rotulo, icon=icone, type="primary", width="stretch", key=f"acao_{principal}"):
                fazer(principal)
        outras = [a for a in acoes if a != principal and a in ROTULO_ACAO]
        if outras:
            with st.popover("Mais ações", icon=":material/more_horiz:", width="stretch"):
                for acao in outras:
                    rotulo, icone = ROTULO_ACAO[acao]
                    if st.button(rotulo, icon=icone, width="stretch", key=f"acao_{acao}"):
                        fazer(acao)

    with st.container(border=True):
        st.markdown("#### :material/receipt_long: Reembolso")
        for situacao, texto in itens_reembolso(ticket, repassado):
            cor, icone = ITEM_REEMBOLSO[situacao]
            st.markdown(f":{cor}[{icone}] {texto}")
        if "corrigir_autorizacao" in acoes:
            autorizado = bool(ticket.get("autorizado_lideranca"))
            chave = f"autorizacao_{ticket['id']}_{autorizado}"
            st.toggle("Autorização de liderança (TL ou supervisão)", value=autorizado, key=chave,
                      on_change=ao_mudar_chave,
                      args=(corrigir_autorizacao, chave, "Autorização de liderança corrigida."))
            # Só aparece nos status que admitem custo BX: aí a autorização decide o destino. Quem aplica é o banco.
            destino_se_mudar = descricao_destino_reembolso("multa_parceiro" if autorizado else "custo_bx")
            st.caption(f"Se {'desmarcar' if autorizado else 'marcar'}, o reembolso vai para: {destino_se_mudar}.")
        elif ticket.get("pede_autorizacao"):
            st.caption(f"Autorização de liderança: {'sim' if ticket.get('autorizado_lideranca') else 'não'}"
                       " (travada depois de confirmar o reembolso).")

    with st.container(border=True):
        st.markdown("#### :material/edit_note: Notas internas")
        if pode_editar_obs(ticket):
            with st.form("obs", border=False):
                obs = st.text_area("OBS", value=ticket.get("obs") or "", label_visibility="collapsed",
                                   placeholder="Anotação pro time (não vai pro parceiro)")
                if st.form_submit_button("Salvar nota", icon=":material/save:"):
                    executar(editar_obs, obs, sucesso="Nota salva.")
        else:
            st.caption(ou_traco(ticket.get("obs")))
        if pode_mudar_acionar_operador(ticket):
            acionar = bool(ticket.get("acionar_operador"))
            chave = f"acionar_{ticket['id']}_{acionar}"
            st.toggle("Acionar operador", value=acionar, key=chave,
                      on_change=ao_mudar_chave, args=(marcar_acionar_operador, chave, "Acionar operador atualizado."))
