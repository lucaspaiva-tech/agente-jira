"""Tabela de tickets no estilo shadcn/ui: a mesma na Fila e na Visão geral.

Cabeçalho escuro em HTML isolado e linhas em st.columns com a mesma grade. Cada tela escolhe
quais colunas mostra.
"""

import streamlit as st

from lib.dominio import (
    COR_GRUPO,
    ROTULO_GRUPO,
    cor_sla,
    cor_status_ia,
    formatar_data_hora,
    grupo_fila,
    link_markdown,
    texto_sla,
)

# Nome no cabeçalho e proporção de cada coluna: as mesmas no cabeçalho (HTML) e nas linhas.
COLUNAS = {
    "chave": ("Chave Jira", 1.4),
    "empresa": ("Empresa", 1.9),
    "status_ia": ("Status da IA", 1.8),
    "estado": ("Estado", 1.6),
    "sla": ("SLA", 1.8),
    "recebido": ("Recebido em", 1.6),
}
COR_ETIQUETA_SLA = {"sucesso": "green", "erro": "red", "aviso": "orange", "neutro": "gray"}


def proporcoes(colunas) -> list[float]:
    return [COLUNAS[c][1] for c in colunas]


def cabecalho(colunas) -> str:
    """Cabeçalho escuro (tinta, texto branco). HTML isolado, com o mesmo grid das linhas."""
    grade = " ".join(f"{p}fr" for p in proporcoes(colunas))
    titulos = "".join(f"<div>{COLUNAS[c][0]}</div>" for c in colunas)
    return f"""
    <div style="display:grid; grid-template-columns:{grade}; column-gap:1rem; align-items:center;
                background:#454545; color:#ffffff; border-radius:0.5rem; padding:0.7rem 0.75rem;
                font-family:Inter, sans-serif; font-size:0.8rem; font-weight:600;
                letter-spacing:0.03em; text-transform:uppercase;">{titulos}</div>
    """


def etiqueta(cor: str, texto: str) -> str:
    return f":{cor}-badge[{texto}]"


def linha(ticket: dict, colunas, links_planilha: dict, lista_detalhe=None):
    """Uma linha da tabela. lista_detalhe: ordem pro Anterior e Próximo, gravada ao abrir o ticket."""
    celulas = dict(zip(colunas, st.columns(proporcoes(colunas), vertical_alignment="center"), strict=True))

    if "chave" in celulas:
        # A chave é o link: um clique abre o Detalhe (sem caixa de seleção).
        if celulas["chave"].button(ticket["jira_key"], key=f"abrir_{ticket['id']}", type="tertiary",
                                   icon=":material/open_in_new:"):
            st.session_state["ticket_id"] = ticket["id"]
            if lista_detalhe is not None:
                st.session_state["_lista_detalhe"] = lista_detalhe
            st.switch_page("telas/detalhe.py")
    if "empresa" in celulas:
        # Com parceiro ligado, o nome abre a planilha dele (link externo abre em nova aba).
        empresa = ticket.get("empresa")
        url = links_planilha.get(ticket.get("parceiro_id"))
        celulas["empresa"].markdown(link_markdown(empresa, url) if empresa else "—")
    if "status_ia" in celulas:
        status_ia = ticket.get("status_ia")
        celulas["status_ia"].markdown(
            etiqueta(cor_status_ia(status_ia), status_ia) if status_ia else etiqueta("gray", "Sem decisão"))
    if "estado" in celulas:
        grupo = grupo_fila(ticket)
        alerta = ":material/warning: " if ticket.get("erro") else ""
        celulas["estado"].markdown(
            etiqueta(COR_GRUPO.get(grupo, "gray"), f"{alerta}{ROTULO_GRUPO.get(grupo, ticket['estado'])}"))
    if "sla" in celulas:
        texto = texto_sla(ticket.get("situacao_sla"), ticket.get("sla_texto"))
        celulas["sla"].markdown(
            etiqueta(COR_ETIQUETA_SLA[cor_sla(ticket.get("situacao_sla"))], texto) if texto != "—" else "—")
    if "recebido" in celulas:
        celulas["recebido"].caption(formatar_data_hora(ticket.get("recebido_em")))
