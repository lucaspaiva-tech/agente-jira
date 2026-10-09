"""Leitura de configuração: funciona igual na sua máquina e no Buser Hub."""

import os

import streamlit as st


def ler_segredo(nome: str) -> str | None:
    """Procura o segredo no st.secrets e, se não achar, em variável de ambiente.

    Local: vem de .streamlit/secrets.toml (fora do Git).
    Hub: vem do que o TI cadastrar, por qualquer um dos dois caminhos.
    """
    try:
        if nome in st.secrets:
            return str(st.secrets[nome])
    except Exception:
        pass  # st.secrets dá erro quando não existe nenhum arquivo de segredos
    return os.environ.get(nome)


def ambiente() -> str:
    """'local' só quando o segredo AMBIENTE=local existir. Qualquer outro caso é 'hub'."""
    return "local" if ler_segredo("AMBIENTE") == "local" else "hub"
