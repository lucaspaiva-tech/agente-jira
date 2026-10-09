"""Apoio dos testes: troca o Streamlit por um falso, pra testar sem abrir o app."""

import types

import pytest


class _Contexto:
    def __init__(self, cabecalhos):
        self.headers = cabecalhos


@pytest.fixture
def hub(monkeypatch):
    """Monta o ambiente: segredos, variáveis de ambiente e cabeçalhos que o Hub mandaria.

    Uso: hub(cabecalhos={"X-Hub-User-Email": "ana@buser.com.br"}, segredos={"AMBIENTE": "local"})
    """

    def montar(cabecalhos=None, segredos=None, ambiente_so=None):
        import lib.config as config
        import lib.identidade as identidade

        falso = types.SimpleNamespace(
            secrets=dict(segredos or {}),
            context=_Contexto(dict(cabecalhos or {})),
        )
        monkeypatch.setattr(config, "st", falso)
        monkeypatch.setattr(identidade, "st", falso)
        for nome in ("AMBIENTE", "USUARIO_LOCAL_EMAIL"):
            monkeypatch.delenv(nome, raising=False)
        for nome, valor in (ambiente_so or {}).items():
            monkeypatch.setenv(nome, valor)

    return montar
