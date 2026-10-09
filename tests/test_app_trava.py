"""Trava de acesso do app.py: no Hub, sem e-mail identificado, nenhuma tela com dados abre."""

import shutil
import types

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

RAIZ = __import__("pathlib").Path(__file__).resolve().parent.parent
MARCA_PAGINA_COMENTADA = '# st.Page("pages/fila.py", title="Fila", icon="📋"),'
TEXTO_DOS_DADOS = "DADOS DE PASSAGEIRO"


@pytest.fixture
def app_com_pagina_de_dados(tmp_path):
    """Copia o projeto e registra uma página falsa em PAGINAS_COM_DADOS."""
    destino = tmp_path / "projeto"
    shutil.copytree(
        RAIZ, destino, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "tests")
    )
    (destino / "pages" / "dados_falsos.py").write_text(
        f'import streamlit as st\nst.write("{TEXTO_DOS_DADOS}")\n', encoding="utf-8"
    )
    app = (destino / "app.py").read_text(encoding="utf-8")
    assert MARCA_PAGINA_COMENTADA in app, "a linha de exemplo de PAGINAS_COM_DADOS mudou"
    app = app.replace(MARCA_PAGINA_COMENTADA, 'st.Page("pages/dados_falsos.py", title="Dados"),')
    (destino / "app.py").write_text(app, encoding="utf-8")
    return destino / "app.py"


def rodar(app, monkeypatch, cabecalhos, segredos=None):
    monkeypatch.setattr(st, "context", types.SimpleNamespace(headers=cabecalhos))
    at = AppTest.from_file(str(app))
    at.secrets["SUPABASE_URL"] = "http://127.0.0.1:1"
    at.secrets["SUPABASE_SERVICE_KEY"] = "chave-de-teste"
    for nome, valor in (segredos or {}).items():
        at.secrets[nome] = valor
    return at.run(timeout=30)


def abriu_os_dados(at):
    return any(TEXTO_DOS_DADOS in m.value for m in at.markdown)


def acesso_negado(at):
    return any("Acesso negado" in e.value for e in at.error)


def test_no_hub_com_email_a_pagina_de_dados_abre(app_com_pagina_de_dados, monkeypatch):
    at = rodar(app_com_pagina_de_dados, monkeypatch, {"X-Hub-User-Email": "ana@buser.com.br"})
    assert abriu_os_dados(at)
    assert not acesso_negado(at)


def test_no_hub_sem_email_a_pagina_de_dados_nao_abre(app_com_pagina_de_dados, monkeypatch):
    at = rodar(app_com_pagina_de_dados, monkeypatch, {})
    assert not abriu_os_dados(at)
    assert acesso_negado(at)


def test_cabecalho_forjado_nao_destrava(app_com_pagina_de_dados, monkeypatch):
    at = rodar(app_com_pagina_de_dados, monkeypatch, {"X-Forwarded-Email": "diretor@buser.com.br"})
    assert not abriu_os_dados(at)
    assert acesso_negado(at)


def test_no_modo_local_sem_cabecalho_a_pagina_abre(app_com_pagina_de_dados, monkeypatch):
    segredos = {"AMBIENTE": "local", "USUARIO_LOCAL_EMAIL": "lucas.paiva@buser.com.br"}
    at = rodar(app_com_pagina_de_dados, monkeypatch, {}, segredos)
    assert abriu_os_dados(at)
