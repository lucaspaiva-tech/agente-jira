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


# ---------------------------------------------------------------- leitura da fila
class ClienteLeituraFalso:
    """Imita .table().select().order().range().execute() sobre uma lista de linhas."""

    def __init__(self, linhas):
        self.linhas = linhas
        self.chamadas = []
        self._inicio = self._fim = None

    def table(self, nome):
        self.chamadas.append(("table", nome))
        return self

    def select(self, colunas):
        self.chamadas.append(("select", colunas))
        return self

    def eq(self, coluna, valor):
        self.chamadas.append(("eq", coluna, valor))
        return self

    def order(self, coluna, desc=False):
        self.chamadas.append(("order", coluna, desc))
        return self

    def range(self, inicio, fim):
        self.chamadas.append(("range", inicio, fim))
        self._inicio, self._fim = inicio, fim
        return self

    def execute(self):
        fatia = self.linhas if self._inicio is None else self.linhas[self._inicio : self._fim + 1]

        class Resposta:
            data = fatia

        return Resposta()


def test_listar_fila_le_a_view_do_mais_recente_pro_mais_antigo(monkeypatch):
    falso = ClienteLeituraFalso([{"id": 2}, {"id": 1}])
    monkeypatch.setattr(dados, "cliente", lambda: falso)
    assert dados.listar_fila() == [{"id": 2}, {"id": 1}]
    assert ("table", "v_fila") in falso.chamadas
    assert ("order", "recebido_em", True) in falso.chamadas


def test_listar_fila_busca_em_paginas_e_nao_perde_ticket(monkeypatch):
    # O Supabase corta a resposta num limite de linhas. Com página de 2 e 5 tickets,
    # só traz os 5 quem pede página por página até vir uma incompleta.
    falso = ClienteLeituraFalso([{"id": i} for i in range(5, 0, -1)])
    monkeypatch.setattr(dados, "cliente", lambda: falso)
    monkeypatch.setattr(dados, "TAMANHO_PAGINA", 2)
    assert [t["id"] for t in dados.listar_fila()] == [5, 4, 3, 2, 1]
    paginas = [c[1:] for c in falso.chamadas if c[0] == "range"]
    assert paginas == [(0, 1), (2, 3), (4, 5)]


def test_listar_fila_vazia(monkeypatch):
    monkeypatch.setattr(dados, "cliente", lambda: ClienteLeituraFalso([]))
    assert dados.listar_fila() == []


# ---------------------------------------------------------------- leitura do detalhe
@pytest.fixture
def leitura(monkeypatch):
    """Instala um cliente de leitura com as linhas dadas e devolve ele pra conferir as chamadas."""

    def instalar(linhas):
        falso = ClienteLeituraFalso(linhas)
        monkeypatch.setattr(dados, "cliente", lambda: falso)
        return falso

    return instalar


def test_ler_ticket_busca_na_v_fila_pelo_id(leitura):
    falso = leitura([{"id": 7, "jira_key": "TESTE-7"}])
    assert dados.ler_ticket(7) == {"id": 7, "jira_key": "TESTE-7"}
    assert ("table", "v_fila") in falso.chamadas
    assert ("eq", "id", 7) in falso.chamadas


def test_ler_ticket_inexistente_devolve_none(leitura):
    leitura([])
    assert dados.ler_ticket(999) is None


def test_ler_reserva_busca_em_reservas_oficiais_pelo_ticket(leitura):
    falso = leitura([{"ticket_id": 7, "valor_repassado": 289.0}])
    assert dados.ler_reserva(7) == {"ticket_id": 7, "valor_repassado": 289.0}
    assert ("table", "reservas_oficiais") in falso.chamadas
    assert ("eq", "ticket_id", 7) in falso.chamadas


def test_ler_reserva_sem_linha_devolve_none(leitura):
    leitura([])
    assert dados.ler_reserva(10) is None


def test_ler_decisao_busca_a_decisao_em_vigor(leitura):
    falso = leitura([{"id": 41, "status_ia": "Alinhado"}])
    assert dados.ler_decisao(41) == {"id": 41, "status_ia": "Alinhado"}
    assert ("table", "decisoes_ia") in falso.chamadas
    assert ("eq", "id", 41) in falso.chamadas


def test_ler_decisao_sem_decisao_nem_encosta_no_banco(leitura):
    falso = leitura([{"id": 41}])
    assert dados.ler_decisao(None) is None
    assert falso.chamadas == []


def test_listar_eventos_do_mais_recente_pro_mais_antigo(leitura):
    falso = leitura([{"campo": "estado"}, {"campo": "criado"}])
    assert dados.listar_eventos(7) == [{"campo": "estado"}, {"campo": "criado"}]
    assert ("table", "eventos") in falso.chamadas
    assert ("eq", "ticket_id", 7) in falso.chamadas
    assert ("order", "criado_em", True) in falso.chamadas
    # eventos do mesmo instante (um update que muda várias colunas) saem sempre na mesma ordem
    assert ("order", "id", True) in falso.chamadas
