"""Conexão com o Supabase. As páginas nunca criam cliente próprio: usam este."""

import streamlit as st

from lib.config import ler_segredo
from supabase import Client, create_client


# st.cache_resource: cria o cliente UMA vez e reaproveita entre recarregamentos
# e usuários. Sem isso, cada clique na página abriria uma conexão nova.
@st.cache_resource
def cliente() -> Client:
    url = ler_segredo("SUPABASE_URL")
    chave = ler_segredo("SUPABASE_SERVICE_KEY")
    if not url or not chave:
        raise RuntimeError("SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados.")
    # A chave service_role ignora o RLS: por isso ela só existe no servidor
    # (sua máquina, Hub e n8n), nunca no navegador.
    return create_client(url, chave)
