"""Parceiros: avisos pendentes, contatos e nomes de empresa ainda sem parceiro."""

import pandas as pd
import streamlit as st

from lib.dados import adicionar_nome_parceiro, atualizar_parceiro, listar_fila, listar_parceiros
from lib.dominio import (
    empresas_sem_parceiro,
    link_contato,
    link_planilha,
    mensagem_de_erro,
    mudancas_de_contato,
    validar_contato,
)

st.title("🤝 Parceiros")

try:
    parceiros = listar_parceiros()
    empresas_dos_tickets = [t.get("empresa") for t in listar_fila()]
except Exception:
    st.error("Não consegui ler os parceiros agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()


def gravar(acao, *argumentos) -> bool:
    """Grava pela função de lib/dados.py. Erro vira mensagem simples; False se não gravou."""
    try:
        acao(*argumentos)
    except Exception as erro:
        st.error(mensagem_de_erro(erro))
        return False
    return True


def concluir(aviso: str):
    # O aviso sobrevive ao st.rerun() porque fica no session_state.
    st.session_state["aviso_parceiros"] = aviso
    st.rerun()


if aviso := st.session_state.pop("aviso_parceiros", None):
    st.success(aviso)

# 1. Avisos pendentes ---------------------------------------------------------
st.subheader("Avisos pendentes")
pendentes = [p for p in parceiros if p.get("contato_pendente")]
if not pendentes:
    st.caption("Nenhum aviso pendente.")
for parceiro in pendentes:
    with st.container(border=True):
        nome, contato, enviei = st.columns([3, 2, 1])
        nome.markdown(f"**{parceiro['nome']}**")
        nome.caption("Chegou ticket novo na planilha deste parceiro.")
        link = link_contato(parceiro.get("whatsapp"), parceiro.get("email"), parceiro["planilha_id"])
        if link["url"]:
            contato.link_button(link["rotulo"], link["url"])
        else:
            contato.caption(f"{link['rotulo']}: cadastre WhatsApp ou e-mail na lista abaixo.")
        if enviei.button("Já enviei", key=f"enviei_{parceiro['id']}", type="primary"):
            if gravar(atualizar_parceiro, parceiro["id"], {"contato_pendente": False}):
                concluir(f"Aviso de {parceiro['nome']} marcado como enviado.")

# 2. Lista com edição de contato ----------------------------------------------
st.subheader("Lista")
st.caption("WhatsApp e e-mail são editáveis direto na tabela. No WhatsApp, use o telefone com DDD ou a palavra GRUPO.")
tabela = pd.DataFrame(
    {
        "id": [p["id"] for p in parceiros],
        "nome": [p["nome"] for p in parceiros],
        "nomes": [", ".join(p["nomes"]) for p in parceiros],
        "whatsapp": [p.get("whatsapp") for p in parceiros],
        "email": [p.get("email") for p in parceiros],
        "planilha": [link_planilha(p["planilha_id"]) for p in parceiros],
    }
)
# data_editor é uma tabela editável: devolve a tabela com o que a pessoa mudou.
editada = st.data_editor(
    tabela,
    hide_index=True,
    width="stretch",
    disabled=["id", "nome", "nomes", "planilha"],
    column_config={
        "id": None,  # escondida: só serve pra saber qual parceiro mudou
        "nome": "Parceiro",
        "nomes": "Nomes de empresa",
        "whatsapp": st.column_config.TextColumn("WhatsApp"),
        "email": st.column_config.TextColumn("E-mail"),
        "planilha": st.column_config.LinkColumn("Planilha", display_text="Abrir planilha"),
    },
    key="contatos",
)

if st.button("Salvar alterações", type="primary"):
    # Célula apagada pode voltar como NaN: vira None antes de comparar.
    depois = [{k: (None if pd.isna(v) else v) for k, v in linha.items()} for linha in editada.to_dict("records")]
    mudancas = mudancas_de_contato(parceiros, depois)
    linha_editada = {linha["id"]: linha for linha in depois}
    nomes = {p["id"]: p["nome"] for p in parceiros}
    problemas = [
        f"{nomes[pid]}: {problema}"
        for pid in mudancas
        if (problema := validar_contato(linha_editada[pid]["whatsapp"], linha_editada[pid]["email"]))
    ]
    if not mudancas:
        st.info("Nada mudou.")
    elif problemas:
        for problema in problemas:
            st.warning(problema)
        st.caption("Nada foi gravado. Corrija e salve de novo.")
    elif all(gravar(atualizar_parceiro, pid, campos) for pid, campos in mudancas.items()):
        concluir(f"Contato atualizado em {len(mudancas)} parceiro(s).")

# 3. Empresas sem parceiro -----------------------------------------------------
st.subheader("Empresas sem parceiro")
sem_parceiro = empresas_sem_parceiro(empresas_dos_tickets, [n for p in parceiros for n in p["nomes"]])
if sem_parceiro:
    st.caption("Empresas que aparecem nos tickets mas não estão ligadas a nenhum parceiro: " + ", ".join(sem_parceiro))
else:
    st.caption("Toda empresa dos tickets já está ligada a um parceiro.")

with st.form("adicionar_nome"):
    st.markdown("**Ligar um nome de empresa a um parceiro**")
    st.caption("Os tickets que chegaram com esse nome são ligados ao parceiro na hora.")
    nome = st.selectbox(
        "Nome da empresa",
        sem_parceiro,
        index=None,
        placeholder="Escolha da lista ou digite outro nome",
        accept_new_options=True,
    )
    escolhido = st.selectbox("Parceiro", parceiros, index=None, format_func=lambda p: p["nome"])
    if st.form_submit_button("Adicionar"):
        if not (nome or "").strip() or escolhido is None:
            st.warning("Escolha o nome da empresa e o parceiro.")
        elif gravar(adicionar_nome_parceiro, nome, escolhido["id"]):
            concluir(f"“{nome.strip()}” agora é do parceiro {escolhido['nome']}.")
