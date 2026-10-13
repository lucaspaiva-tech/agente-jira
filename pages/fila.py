"""Fila: tickets em andamento e resolvidos, numa tabela no estilo dos painéis atuais (shadcn/ui).

Cada linha tem a chave do Jira como link pro Detalhe, etiquetas coloridas de status da IA, estado
e SLA, e a tabela pagina de 10 em 10. Filtros, visão e página são lembrados ao voltar do Detalhe.
"""

import streamlit as st

from lib.dados import listar_fila
from lib.dominio import (
    COR_GRUPO,
    GRUPOS_EM_ANDAMENTO,
    ROTULO_GRUPO,
    contar_por_grupo,
    cor_sla,
    cor_status_ia,
    estados_dos_grupos,
    faixa_da_pagina,
    filtrar_fila,
    formatar_data_hora,
    grupo_fila,
    paginar,
    texto_sla,
)

POR_PAGINA = 10
# Colunas da tabela e a proporção de cada uma: as mesmas no cabeçalho (HTML) e nas linhas.
COLUNAS = [("Chave Jira", 1.4), ("Empresa", 1.9), ("Status da IA", 1.8), ("Estado", 1.6), ("SLA", 1.8),
           ("Recebido em", 1.6)]
PROPORCOES = [proporcao for _, proporcao in COLUNAS]
COR_ETIQUETA_SLA = {"sucesso": "green", "erro": "red", "aviso": "orange", "neutro": "gray"}
VISOES = ("andamento", "resolvidos")


def restaurar(chave: str, padrao):
    """Campo some do session_state ao trocar de página; a cópia em '_chave' traz o valor de volta."""
    if chave not in st.session_state:
        st.session_state[chave] = st.session_state.get(f"_{chave}", padrao)


def guardar(*chaves: str):
    for chave in chaves:
        st.session_state[f"_{chave}"] = st.session_state[chave]


def cabecalho() -> str:
    """Cabeçalho escuro (tinta, texto branco). HTML isolado, com o mesmo grid das linhas."""
    grade = " ".join(f"{p}fr" for p in PROPORCOES)
    titulos = "".join(f"<div>{nome}</div>" for nome, _ in COLUNAS)
    return f"""
    <div style="display:grid; grid-template-columns:{grade}; column-gap:1rem; align-items:center;
                background:#454545; color:#ffffff; border-radius:0.5rem; padding:0.7rem 0.75rem;
                font-family:Inter, sans-serif; font-size:0.8rem; font-weight:600;
                letter-spacing:0.03em; text-transform:uppercase;">{titulos}</div>
    """


def etiqueta(cor: str, texto: str) -> str:
    return f":{cor}-badge[{texto}]"


def linha(ticket: dict):
    chave, empresa, status, estado, sla, recebido = st.columns(PROPORCOES, vertical_alignment="center")
    # A chave é o link: um clique abre o Detalhe (sem caixa de seleção).
    if chave.button(ticket["jira_key"], key=f"abrir_{ticket['id']}", type="tertiary", icon=":material/open_in_new:"):
        st.session_state["ticket_id"] = ticket["id"]
        st.switch_page("pages/detalhe.py")
    empresa.markdown(ticket.get("empresa") or "—")
    status_ia = ticket.get("status_ia")
    status.markdown(etiqueta(cor_status_ia(status_ia), status_ia) if status_ia else etiqueta("gray", "Sem decisão"))
    grupo = grupo_fila(ticket)
    alerta = ":material/warning: " if ticket.get("erro") else ""
    estado.markdown(etiqueta(COR_GRUPO.get(grupo, "gray"), f"{alerta}{ROTULO_GRUPO.get(grupo, ticket['estado'])}"))
    texto = texto_sla(ticket.get("situacao_sla"), ticket.get("sla_texto"))
    sla.markdown(etiqueta(COR_ETIQUETA_SLA[cor_sla(ticket.get("situacao_sla"))], texto) if texto != "—" else "—")
    recebido.caption(formatar_data_hora(ticket.get("recebido_em")))


try:
    tickets = listar_fila()
except Exception:
    st.title("Fila")
    st.error("Não consegui ler os tickets agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()

contagem = contar_por_grupo(tickets)

# Topo: título e o atalho Em andamento | Resolvidos ----------------------------------------
titulo, atalho = st.columns([3, 2], vertical_alignment="bottom")
titulo.title("Fila")
titulo.caption(f"{len(tickets)} tickets no total · do mais recente pro mais antigo")
restaurar("fila_visao", "andamento")
rotulo_visao = {"andamento": f"Em andamento · {sum(contagem[g] for g in GRUPOS_EM_ANDAMENTO)}",
                "resolvidos": f"Resolvidos · {contagem['resolvido']}"}
atalho.segmented_control("Visão", VISOES, format_func=rotulo_visao.get, key="fila_visao",
                         label_visibility="collapsed", width="stretch")
visao = st.session_state["fila_visao"] or "andamento"  # desmarcar o atalho volta pra Em andamento

# Filtros -------------------------------------------------------------------------------------
for chave, padrao in (("fila_grupos", list(GRUPOS_EM_ANDAMENTO)), ("fila_empresas", []),
                      ("fila_status", []), ("fila_busca", "")):
    restaurar(chave, padrao)

if visao == "andamento":
    st.pills("Estado", GRUPOS_EM_ANDAMENTO, selection_mode="multi", key="fila_grupos",
             format_func=lambda g: f"{ROTULO_GRUPO[g]} · {contagem[g]}")
    # Nenhum estado marcado = todos em andamento (nunca mistura os resolvidos).
    estados = estados_dos_grupos(st.session_state["fila_grupos"] or GRUPOS_EM_ANDAMENTO)
else:
    estados = ["resolvido"]

c1, c2, c3 = st.columns(3)
c1.multiselect("Empresa", sorted({t["empresa"] for t in tickets if t.get("empresa")}),
               key="fila_empresas", placeholder="Todas")
c2.multiselect("Status da IA", sorted({t["status_ia"] for t in tickets if t.get("status_ia")}),
               key="fila_status", placeholder="Todos")
c3.text_input("Buscar", key="fila_busca", placeholder="Chave Jira ou reserva", icon=":material/search:")
guardar("fila_visao", "fila_grupos", "fila_empresas", "fila_status", "fila_busca")

filtrados = filtrar_fila(tickets, estados, st.session_state["fila_empresas"], st.session_state["fila_status"],
                         st.session_state["fila_busca"])

# Mudou visão ou filtro: volta pra página 1.
assinatura = (visao, tuple(estados), tuple(st.session_state["fila_empresas"]),
              tuple(st.session_state["fila_status"]), st.session_state["fila_busca"])
if st.session_state.get("_fila_assinatura") != assinatura:
    st.session_state["_fila_assinatura"] = assinatura
    st.session_state["_fila_pagina"] = 1
itens, pagina, total_paginas = paginar(filtrados, st.session_state.get("_fila_pagina", 1), POR_PAGINA)
st.session_state["_fila_pagina"] = pagina

# Tabela ---------------------------------------------------------------------------------------
with st.container(border=True):
    st.html(cabecalho())
    if not itens:
        st.caption("Nenhum ticket com esses filtros.")
    for ticket in itens:
        linha(ticket)

    # Rodapé: faixa com total à esquerda, navegação à direita.
    faixa, anterior, posicao, proxima = st.columns([4, 1.3, 1.3, 1.3], vertical_alignment="center")
    faixa.caption(faixa_da_pagina(pagina, POR_PAGINA, len(filtrados)))
    if anterior.button("Anterior", icon=":material/chevron_left:", disabled=pagina <= 1, width="stretch"):
        st.session_state["_fila_pagina"] = pagina - 1
        st.rerun()
    posicao.markdown(f"<div style='text-align:center'>Página {pagina} de {total_paginas}</div>",
                     unsafe_allow_html=True)
    if proxima.button("Próxima", icon=":material/chevron_right:", icon_position="right",
                      disabled=pagina >= total_paginas, width="stretch"):
        st.session_state["_fila_pagina"] = pagina + 1
        st.rerun()
