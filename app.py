"""Agente JIRA: ponto de entrada. Rodar com: streamlit run app.py"""

import streamlit as st

from lib.config import ambiente
from lib.identidade import usuario_atual

st.set_page_config(page_title="Agente JIRA", page_icon="🎫", layout="wide")

# Páginas que mostram dados de passageiro. Cada tela nova entra AQUI (nunca
# direto em "paginas"), para ficar protegida pela trava de identidade abaixo.
PAGINAS_COM_DADOS: list = [
    # st.Page("pages/fila.py", title="Fila", icon="📋"),
]

# O Diagnóstico não exibe dado de passageiro: fica sempre disponível.
DIAGNOSTICO = st.Page("pages/diagnostico.py", title="Diagnóstico", icon="🔌")

email, _ = usuario_atual()

# Trava de acesso: no Hub, sem e-mail identificado (ex.: link externo /s/...),
# só o Diagnóstico é registrado. Como o st.navigation só abre as páginas
# registradas, nenhuma tela com dados fica acessível, nem pela URL.
if ambiente() == "hub" and not email:
    st.error("🔒 Acesso negado: não foi possível identificar o usuário. Abra o app pelo Buser Hub.")
    paginas = [DIAGNOSTICO]
else:
    paginas = PAGINAS_COM_DADOS + [DIAGNOSTICO]

if ambiente() == "local":
    st.sidebar.warning("Modo local")

st.navigation(paginas).run()
