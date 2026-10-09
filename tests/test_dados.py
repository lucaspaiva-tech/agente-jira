import pytest

import lib.dados as dados
from lib.dados import UsuarioNaoIdentificado, atualizar_parceiro, atualizar_ticket


class ClienteFalso:
    """Imita a cadeia .table().update().eq().execute() e guarda o que foi gravado."""

    def __init__(self):
        self.chamadas = []

    def table(self, nome):
        self.chamadas.append(("table", nome))
        return self

    def update(self, payload):
        self.chamadas.append(("update", payload))
        return self

    def eq(self, coluna, valor):
        self.chamadas.append(("eq", coluna, valor))
        return self

    def execute(self):
        class Resposta:
            data = [{"ok": True}]

        return Resposta()


@pytest.fixture
def cliente_falso(monkeypatch):
    falso = ClienteFalso()
    monkeypatch.setattr(dados, "cliente", lambda: falso)
    return falso


def test_atualizar_ticket_grava_o_email_de_quem_fez(hub, cliente_falso):
    hub(cabecalhos={"X-Hub-User-Email": "ana@buser.com.br"})
    atualizar_ticket(7, {"obs": "conferido"})
    esperado = {"obs": "conferido", "atualizado_por": "ana@buser.com.br"}
    assert ("update", esperado) in cliente_falso.chamadas
    assert ("eq", "id", 7) in cliente_falso.chamadas


def test_atualizar_ticket_sem_usuario_bloqueia_e_nao_toca_no_banco(hub, cliente_falso):
    hub()
    with pytest.raises(UsuarioNaoIdentificado, match="Ação bloqueada"):
        atualizar_ticket(7, {"obs": "conferido"})
    assert cliente_falso.chamadas == []


def test_o_autor_vem_da_identidade_e_nao_do_que_a_tela_mandar(hub, cliente_falso):
    # Se a tela tentar fingir o autor, o e-mail identificado sobrescreve.
    hub(cabecalhos={"X-Hub-User-Email": "ana@buser.com.br"})
    atualizar_ticket(7, {"atualizado_por": "diretor@buser.com.br"})
    gravado = next(c[1] for c in cliente_falso.chamadas if c[0] == "update")
    assert gravado["atualizado_por"] == "ana@buser.com.br"


def test_atualizar_parceiro_sem_usuario_bloqueia(hub, cliente_falso):
    hub()
    with pytest.raises(UsuarioNaoIdentificado):
        atualizar_parceiro(3, {"whatsapp": "11999999999"})
    assert cliente_falso.chamadas == []


def test_atualizar_parceiro_identificado_grava(hub, cliente_falso):
    hub(cabecalhos={"X-Hub-User-Email": "ana@buser.com.br"})
    atualizar_parceiro(3, {"whatsapp": "11999999999"})
    assert ("update", {"whatsapp": "11999999999"}) in cliente_falso.chamadas
