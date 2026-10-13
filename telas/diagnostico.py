"""Diagnóstico: confirma segredos, conexão e identidade. Útil local e no Hub."""

import streamlit as st

from lib.config import ambiente, ler_segredo
from lib.dados import contar
from lib.identidade import CABECALHO_EMAIL, usuario_atual

st.title("Diagnóstico")
st.caption("Os três itens precisam ficar verdes antes de usar o app.")

modo = ambiente()
if modo == "local":
    st.warning("Rodando em **modo local**. No Hub, este aviso não pode aparecer.")
else:
    st.info("Rodando em modo **hub**.")

# 1. Segredos
st.subheader("1. Segredos")
faltando = [n for n in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") if not ler_segredo(n)]
if faltando:
    st.error(f"Faltando: {', '.join(faltando)}.")
else:
    st.success("SUPABASE_URL e SUPABASE_SERVICE_KEY encontrados.")

# 2. Conexão
st.subheader("2. Conexão com o Supabase")
if faltando:
    st.info("Pulado: precisa dos segredos do item 1.")
else:
    try:
        st.success(
            f"Conectado. Parceiros: {contar('parceiros')} | Tickets: {contar('tickets')}"
        )
    except Exception as erro:
        st.error(f"Não consegui falar com o Supabase: {erro}")

# 3. Identidade
st.subheader("3. Quem está usando")
email, origem = usuario_atual()
if email:
    st.success(f"{email} (via {origem})")
else:
    st.error(
        f"Usuário não identificado: o cabeçalho {CABECALHO_EMAIL} não chegou. "
        "Isso é esperado no link externo (/s/...). Abra o app pelo Buser Hub."
    )

# Só os NOMES dos cabeçalhos: os valores podem conter cookies e tokens.
with st.expander("Cabeçalhos recebidos (só os nomes)"):
    st.code("\n".join(sorted(st.context.headers.keys())) or "(nenhum)")
