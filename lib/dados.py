"""Leitura e escrita no Supabase. Toda escrita do app passa por aqui.

As páginas chamam estas funções; nunca chamam cliente().table(...) direto.
Assim a regra do atualizado_por (autor do histórico) fica num lugar só.
"""

from datetime import UTC, datetime

from lib.identidade import usuario_atual
from lib.supabase_client import cliente

# O Supabase devolve no máximo 1000 linhas por consulta: a leitura vem em páginas desse tamanho.
TAMANHO_PAGINA = 1000

COLUNAS_FILA = "id, jira_key, empresa, reserva, status_ia, estado, sla_texto, situacao_sla, recebido_em, erro"


class UsuarioNaoIdentificado(PermissionError):
    """Sem saber quem é o usuário, nenhuma escrita é permitida."""


def contar(tabela: str) -> int:
    # count="exact" devolve o total de linhas; limit(1) evita trazer os dados.
    resposta = cliente().table(tabela).select("id", count="exact").limit(1).execute()
    return resposta.count or 0


def listar_fila() -> list[dict]:
    """Tickets da v_fila (sem dado de passageiro), do mais recente pro mais antigo."""
    tickets = []
    while True:
        inicio = len(tickets)
        pagina = (
            cliente()
            .table("v_fila")
            .select(COLUNAS_FILA)
            .order("recebido_em", desc=True)
            .range(inicio, inicio + TAMANHO_PAGINA - 1)
            .execute()
            .data
        )
        tickets.extend(pagina)
        if len(pagina) < TAMANHO_PAGINA:
            return tickets


def _primeira(resposta) -> dict | None:
    return resposta.data[0] if resposta.data else None


def ler_ticket(ticket_id: int) -> dict | None:
    """Um ticket da v_fila, com todas as colunas (sem dado de passageiro)."""
    return _primeira(cliente().table("v_fila").select("*").eq("id", ticket_id).execute())


def ler_reserva(ticket_id: int) -> dict | None:
    """Passageiro e valores. Dado pessoal: só a tela de detalhe usa."""
    return _primeira(cliente().table("reservas_oficiais").select("*").eq("ticket_id", ticket_id).execute())


def ler_decisao(decisao_id: int | None) -> dict | None:
    """A decisão da IA em vigor (tickets.decisao_id). Ticket sem decisão nem consulta o banco."""
    if decisao_id is None:
        return None
    return _primeira(cliente().table("decisoes_ia").select("*").eq("id", decisao_id).execute())


def listar_eventos(ticket_id: int) -> list[dict]:
    """Linha do tempo do ticket, da mais recente pra mais antiga."""
    return (
        cliente()
        .table("eventos")
        .select("id, campo, de, para, autor, criado_em")
        .eq("ticket_id", ticket_id)
        .order("criado_em", desc=True)
        .order("id", desc=True)
        .execute()
        .data
    )


def atualizar_ticket(ticket_id: int, campos: dict) -> dict | None:
    """Grava os campos no ticket e registra quem fez.

    O trigger do banco transforma cada mudança num evento com este autor.
    Por isso a escrita é bloqueada se o usuário não for identificado.
    """
    email, _ = usuario_atual()
    if not email:
        raise UsuarioNaoIdentificado("Não foi possível identificar o usuário. Ação bloqueada.")

    payload = {**campos, "atualizado_por": email}
    resposta = cliente().table("tickets").update(payload).eq("id", ticket_id).execute()
    return resposta.data[0] if resposta.data else None


def listar_parceiros() -> list[dict]:
    """Parceiros por nome, cada um com 'nomes': os nomes de empresa ligados a ele."""
    parceiros = (
        cliente()
        .table("parceiros")
        .select("id, nome, whatsapp, email, planilha_id, contato_pendente")
        .order("nome")
        .execute()
        .data
    )
    nomes = cliente().table("parceiro_nomes").select("nome, parceiro_id").order("nome").execute().data
    for parceiro in parceiros:
        parceiro["nomes"] = [n["nome"] for n in nomes if n["parceiro_id"] == parceiro["id"]]
    return parceiros


def adicionar_nome_parceiro(nome: str, parceiro_id: int) -> dict | None:
    """Liga um nome de empresa a um parceiro. O banco liga os tickets e recusa nome repetido."""
    email, _ = usuario_atual()
    if not email:
        raise UsuarioNaoIdentificado("Não foi possível identificar o usuário. Ação bloqueada.")

    payload = {"nome": nome.strip(), "parceiro_id": parceiro_id}
    resposta = cliente().table("parceiro_nomes").insert(payload).execute()
    return resposta.data[0] if resposta.data else None


def atualizar_parceiro(parceiro_id: int, campos: dict) -> dict | None:
    """Mesma regra de identificação, para a tabela parceiros."""
    email, _ = usuario_atual()
    if not email:
        raise UsuarioNaoIdentificado("Não foi possível identificar o usuário. Ação bloqueada.")

    resposta = cliente().table("parceiros").update(campos).eq("id", parceiro_id).execute()
    return resposta.data[0] if resposta.data else None


# -----------------------------------------------------------------------------
# Ações humanas no ticket. Quem pode fazer o quê: dominio.acoes_disponiveis.
# Nenhuma grava data de estado (enviado_parceiro_em, decidido_em, resolvido_em):
# o banco carimba. Transição inválida o banco recusa.
# -----------------------------------------------------------------------------
def enviar_ao_parceiro(ticket_id: int) -> dict | None:
    """Pede o envio: o n8n escreve na planilha e muda pra enviado_parceiro."""
    return atualizar_ticket(ticket_id, {"estado": "enviando"})


def reverter_envio(ticket_id: int) -> dict | None:
    """Volta pra pendente. A linha já copiada na planilha do parceiro não é removida."""
    return atualizar_ticket(ticket_id, {"estado": "pendente"})


def registrar_decisao(ticket_id: int, aprovado: str, motivo: str) -> dict | None:
    """Decisão manual: 'Sim' ou 'Não' e o motivo. Validar antes com dominio.validar_decisao."""
    campos = {"aprovado": aprovado, "motivo_parceiro": motivo.strip(), "estado": "decidido"}
    return atualizar_ticket(ticket_id, campos)


def corrigir_autorizacao(ticket_id: int, autorizado: bool) -> dict | None:
    """Autorização de liderança (TL ou supervisão). Depois do reembolso confirmado o banco recusa."""
    return atualizar_ticket(ticket_id, {"autorizado_lideranca": autorizado})


def confirmar_reembolso(ticket_id: int) -> dict | None:
    """Carimba a confirmação. O banco decide: custo BX ou multa do parceiro."""
    return atualizar_ticket(ticket_id, {"reembolso_confirmado_em": datetime.now(UTC).isoformat()})


def resolver(ticket_id: int) -> dict | None:
    return atualizar_ticket(ticket_id, {"estado": "resolvido"})


def reabrir(ticket_id: int) -> dict | None:
    return atualizar_ticket(ticket_id, {"estado": "decidido"})


def editar_obs(ticket_id: int, texto: str | None) -> dict | None:
    """OBS em branco vira vazio de verdade (null), não um texto de espaços."""
    return atualizar_ticket(ticket_id, {"obs": (texto or "").strip() or None})


def marcar_acionar_operador(ticket_id: int, acionar: bool) -> dict | None:
    return atualizar_ticket(ticket_id, {"acionar_operador": acionar})
