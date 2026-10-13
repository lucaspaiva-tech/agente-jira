"""Agente JIRA: ponto de entrada. Rodar com: streamlit run app.py"""

import streamlit as st

from lib.config import ambiente
from lib.identidade import usuario_atual

st.set_page_config(page_title="Agente JIRA", page_icon="🎫", layout="wide")

# Páginas que mostram dados de passageiro, agrupadas em seções do menu. Cada tela nova
# entra AQUI (nunca direto em "paginas"), para ficar protegida pela trava de identidade
# abaixo. A primeira página da primeira seção é a que abre por padrão.
PAGINAS_COM_DADOS: dict[str, list] = {
    "Tratamento": [
        st.Page("telas/visao_geral.py", title="Visão geral", icon=":material/dashboard:"),
        st.Page("telas/fila.py", title="Fila", icon=":material/view_list:"),
        st.Page("telas/detalhe.py", title="Detalhe", icon=":material/description:"),
    ],
    "Cadastro": [
        st.Page("telas/parceiros.py", title="Parceiros", icon=":material/handshake:"),
    ],
}

# O Diagnóstico não exibe dado de passageiro: fica sempre disponível.
SISTEMA = {"Sistema": [st.Page("telas/diagnostico.py", title="Diagnóstico", icon=":material/settings_ethernet:")]}

st.logo("assets/logo.svg", size="large")

email, _ = usuario_atual()

# Trava de acesso: no Hub, sem e-mail identificado (ex.: link externo /s/...),
# só o Diagnóstico é registrado. Como o st.navigation só abre as páginas
# registradas, nenhuma tela com dados fica acessível, nem pela URL.
if ambiente() == "hub" and not email:
    st.error("🔒 Acesso negado: não foi possível identificar o usuário. Abra o app pelo Buser Hub.")
    paginas = SISTEMA
else:
    paginas = {**PAGINAS_COM_DADOS, **SISTEMA}

if ambiente() == "local":
    st.sidebar.warning("Modo local")

st.navigation(paginas).run()
