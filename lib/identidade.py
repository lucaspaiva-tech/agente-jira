"""Descobre o e-mail de quem está usando o app."""

import streamlit as st

from lib.config import ambiente, ler_segredo

# Único cabeçalho confiável: o Hub SEMPRE sobrescreve este valor, então
# ninguém consegue se passar por outra pessoa mandando o cabeçalho na mão.
# Não aceitar nenhum outro: qualquer cabeçalho que o Hub não sobrescreve
# pode ser forjado por quem acessa.
CABECALHO_EMAIL = "X-Hub-User-Email"


def usuario_atual() -> tuple[str | None, str | None]:
    """Devolve (email, de_onde_veio). (None, None) se não der pra identificar.

    Vem None no link externo (/s/...) e quando o app roda fora do Hub.
    """
    # 1. Hub: cabeçalho injetado pelo proxy. Tem prioridade sobre o modo local.
    valor = st.context.headers.get(CABECALHO_EMAIL)
    if valor and valor.strip():
        return valor.strip().lower(), f"cabeçalho {CABECALHO_EMAIL}"

    # 2. Só na sua máquina: e-mail fixo do secrets.toml. No Hub o segredo
    # AMBIENTE=local não existe, então esse caminho nunca é usado lá.
    if ambiente() == "local":
        email_local = ler_segredo("USUARIO_LOCAL_EMAIL")
        if email_local and email_local.strip():
            return email_local.strip().lower(), "modo local (secrets.toml)"

    return None, None
