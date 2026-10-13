"""Regras de negócio que SÓ a página usa. Funções puras: sem Streamlit e sem banco.

O que o n8n e a página compartilham mora no banco, num lugar só: decisão automática da IA
(`status_ia_regras`), transições de estado e carimbos de tempo, ligação ao parceiro, SLA de
48h, espera da multa. Aqui ficam só as regras de apresentação e de permissão de ação.
"""

import re
from collections import Counter
from datetime import UTC, date, datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
TOLERANCIA_MULTA = 0.01  # diferença aceitável (em reais) entre a multa e o valor repassado

ASSUNTO_EMAIL_PARCEIRO = "Novas solicitações de reembolso disponíveis"
MENSAGEM_CONTATO_PARCEIRO = (
    "Temos novas solicitações de reembolso disponíveis na planilha.\n\n"
    "É simples: quando chegar uma linha nova na planilha, só precisa preencher 2 colunas: "
    '"Podemos Reembolsar?" (Sim ou Não) e o motivo da resposta. '
    "Assim que preencher, já está registrado do nosso lado, sem precisar mandar mensagem "
    "confirmando.\n\n"
    "Qualquer dúvida, pode chamar!"
)

TEXTO_MULTA = {
    "aguardando": ("⏳ Aguardando registro no banco", "aviso"),
    "nao_encontrada": ("⚠️ Multa não encontrada (prazo esgotado)", "aviso"),
    "custo_bx": ("Custo assumido por BX", "neutro"),
    "erro": ("Erro na consulta", "erro"),
}


# -----------------------------------------------------------------------------
# Aprovação e reembolso
# -----------------------------------------------------------------------------
def classificar_aprovacao(valor) -> str:
    """'aprovado', 'reprovado' ou 'indefinido'.

    A resposta do parceiro é texto livre. Conta como aprovado "Sim" ou qualquer texto que
    contenha "aprovado" (ex.: "Aprovado por falta de retorno em 48 horas"). Reprovado só
    "Não"/"Nao". Qualquer outra coisa (vazio, texto estranho) é indefinido.
    """
    v = str(valor or "").strip().lower()
    if v == "sim" or "aprovado" in v:
        return "aprovado"
    if v in ("não", "nao"):
        return "reprovado"
    return "indefinido"


def situacao_reembolso(aprovado, reembolso_confirmado_em) -> str:
    """'indefinido', 'nao_cabe', 'aguardando' ou 'confirmado'. Derivado, nunca gravado."""
    classe = classificar_aprovacao(aprovado)
    if classe == "reprovado":
        return "nao_cabe"
    if classe == "indefinido":
        return "indefinido"
    return "confirmado" if reembolso_confirmado_em else "aguardando"


# -----------------------------------------------------------------------------
# Fila: filtros e contadores
# -----------------------------------------------------------------------------
# Ordem do fluxo, só pra exibir. Quem valida o estado é o banco (transicoes_estado).
ESTADOS = ("processando", "falha", "pendente", "enviando", "enviado_parceiro", "decidido", "resolvido")
ESTADOS_PADRAO_FILA = tuple(e for e in ESTADOS if e != "resolvido")

ROTULO_ESTADO = {
    "processando": "Processando",
    "falha": "Falha",
    "pendente": "Pendente",
    "enviando": "Enviando",
    "enviado_parceiro": "Com o parceiro",
    "decidido": "Respondido",
    "resolvido": "Resolvido",
}


def rotulo_estado(estado) -> str:
    """Nome do estado pra pessoa ler. O código do banco (enviado_parceiro) não vai pra tela."""
    return ROTULO_ESTADO.get(estado, estado)


def rotulo_estado_fila(ticket) -> str:
    """Estado na tabela da fila; ticket com erro ganha o sinal ⚠️ (o texto fica no detalhe)."""
    rotulo = rotulo_estado(ticket.get("estado"))
    return f"⚠️ {rotulo}" if ticket.get("erro") else rotulo


# -----------------------------------------------------------------------------
# Visão geral: o que precisa de ação humana agora
# -----------------------------------------------------------------------------
# Ordem de urgência: SLA estourado (parceiro atrasado) e falha antes; depois o fluxo normal.
URGENCIA = {"estourado": 0, "falha": 1, "pendente": 2, "decidido": 3}


def _grupo_urgencia(ticket) -> str | None:
    if ticket.get("situacao_sla") == "estourado":
        return "estourado"
    return ticket.get("estado") if ticket.get("estado") in URGENCIA else None


def precisa_de_voce(ticket) -> bool:
    """Pendente, decidido (falta reembolso ou arquivar), falha ou parceiro com SLA estourado.
    Com o parceiro no prazo, enviando, processando e resolvido esperam outra pessoa ou sistema."""
    return _grupo_urgencia(ticket) is not None


def fila_de_urgencia(tickets) -> list[dict]:
    """Só o que precisa de você, do mais urgente pro menos; no mesmo grupo, o mais antigo primeiro."""
    return sorted(
        (t for t in tickets if precisa_de_voce(t)),
        key=lambda t: (URGENCIA[_grupo_urgencia(t)], t.get("recebido_em") or ""),
    )


def resumo_da_fila(tickets) -> dict[str, int]:
    estados = [t.get("estado") for t in tickets]
    return {
        "precisa_de_voce": sum(precisa_de_voce(t) for t in tickets),
        "pendentes": estados.count("pendente"),
        "sla_estourado": sum(t.get("situacao_sla") == "estourado" for t in tickets),
        "respondidos": estados.count("decidido"),
        "falhas": estados.count("falha"),
        "com_parceiro": estados.count("enviando") + estados.count("enviado_parceiro"),
    }


# -----------------------------------------------------------------------------
# Fila: grupos de estado, cores das etiquetas e paginação
# -----------------------------------------------------------------------------
# A Fila mostra 5 grupos em andamento; "enviando" (o n8n escrevendo na planilha, minutos) entra
# em "Com o parceiro" pra não sumir se o envio travar. Resolvidos ficam num atalho à parte.
ESTADOS_DO_GRUPO = {
    "processando": ("processando",),
    "pendente": ("pendente",),
    "com_parceiro": ("enviando", "enviado_parceiro"),
    "respondido": ("decidido",),
    "falha": ("falha",),
    "resolvido": ("resolvido",),
}
GRUPOS_EM_ANDAMENTO = ("processando", "pendente", "com_parceiro", "respondido", "falha")
ROTULO_GRUPO = {
    "processando": "Processando",
    "pendente": "Pendente",
    "com_parceiro": "Com o parceiro",
    "respondido": "Respondido",
    "falha": "Falha",
    "resolvido": "Resolvido",
}
# Cor da etiqueta (nomes de cor do Streamlit). Única dentro da coluna; o texto vem sempre junto.
COR_GRUPO = {
    "processando": "blue",
    "pendente": "orange",
    "com_parceiro": "violet",
    "respondido": "green",
    "falha": "red",
    "resolvido": "gray",
}
COR_STATUS_IA = {
    "Aprovado Viação": "green",
    "Alinhado": "blue",
    "Em Análise": "gray",
    "Falta informação BX": "violet",
    "Reprovado": "red",
}
_GRUPO_DO_ESTADO = {estado: grupo for grupo, estados in ESTADOS_DO_GRUPO.items() for estado in estados}


def grupo_fila(ticket) -> str | None:
    return _GRUPO_DO_ESTADO.get(ticket.get("estado"))


def estados_dos_grupos(grupos) -> list[str]:
    """Grupos escolhidos na tela -> estados do banco, pro filtrar_fila."""
    return [estado for grupo in grupos for estado in ESTADOS_DO_GRUPO[grupo]]


def contar_por_grupo(tickets) -> dict[str, int]:
    contagem = dict.fromkeys(ESTADOS_DO_GRUPO, 0)
    for t in tickets:
        if (grupo := grupo_fila(t)) is not None:
            contagem[grupo] += 1
    return contagem


def cor_status_ia(status) -> str:
    return COR_STATUS_IA.get(status, "gray")


def paginar(itens, pagina: int, por_pagina: int = 10) -> tuple[list, int, int]:
    """(itens da página, página válida, total de páginas). Página fora da faixa vai pra ponta."""
    total_paginas = max(1, -(-len(itens) // por_pagina))
    pagina = min(max(1, pagina), total_paginas)
    inicio = (pagina - 1) * por_pagina
    return list(itens[inicio : inicio + por_pagina]), pagina, total_paginas


def faixa_da_pagina(pagina: int, por_pagina: int, total: int) -> str:
    """'1–10 de 49': o total sempre aparece (tabela sem total é anti-padrão)."""
    if total == 0:
        return "Nenhum ticket"
    inicio = (pagina - 1) * por_pagina + 1
    return f"{inicio}–{min(pagina * por_pagina, total)} de {total}"


def texto_sla(situacao_sla, sla_texto) -> str:
    """SLA em palavras, não só na cor (quem não distingue cores também precisa ler)."""
    if situacao_sla == "estourado":
        return f"🔴 Estourado · {sla_texto}"
    if situacao_sla == "no_prazo":
        return f"🟢 No prazo · {sla_texto}"
    if situacao_sla == "respondido":
        return f"Respondido em {sla_texto}"
    return "—"


def filtrar_fila(tickets, estados=None, empresas=None, status_ia=None, busca="") -> list[dict]:
    """Aplica todos os filtros juntos. Lista vazia (ou None) não restringe nada.

    A busca procura o trecho na chave Jira ou na reserva, sem ligar pra maiúscula.
    """
    termo = (busca or "").strip().lower()
    return [
        t
        for t in tickets
        if (not estados or t.get("estado") in estados)
        and (not empresas or t.get("empresa") in empresas)
        and (not status_ia or t.get("status_ia") in status_ia)
        and (not termo or termo in (t.get("jira_key") or "").lower() or termo in (t.get("reserva") or "").lower())
    ]


def contar_por_estado(tickets) -> dict[str, int]:
    contagem = dict.fromkeys(ESTADOS, 0)
    for t in tickets:
        contagem[t.get("estado")] = contagem.get(t.get("estado"), 0) + 1
    return contagem


TEXTO_SITUACAO_REEMBOLSO = {
    "indefinido": "Sem resposta do parceiro ainda",
    "nao_cabe": "Não cabe reembolso (parceiro respondeu Não)",
    "aguardando": "Aprovado, aguardando confirmar o reembolso",
    "confirmado": "Reembolso confirmado",
}


# -----------------------------------------------------------------------------
# O que o usuário pode fazer em cada ticket
# -----------------------------------------------------------------------------
def pode_enviar_ao_parceiro(ticket) -> bool:
    return (
        ticket.get("estado") == "pendente"
        and ticket.get("acionar_operador") is True
        and ticket.get("parceiro_id") is not None
    )


def pode_reverter_envio(ticket) -> bool:
    return ticket.get("estado") == "enviado_parceiro"


def pode_registrar_decisao(ticket) -> bool:
    return ticket.get("estado") in ("pendente", "enviado_parceiro")


def pode_confirmar_reembolso(ticket) -> bool:
    return (
        ticket.get("estado") == "decidido"
        and situacao_reembolso(ticket.get("aprovado"), ticket.get("reembolso_confirmado_em"))
        == "aguardando"
    )


def pode_corrigir_autorizacao(ticket) -> bool:
    """Corrigir se houve autorização de liderança (TL ou supervisão).

    Só nos status que admitem custo BX (v_fila.pede_autorizacao, hoje só Alinhado) e só
    antes de confirmar o reembolso: depois disso o banco não deixa mais mudar.
    """
    return (
        ticket.get("pede_autorizacao") is True
        and not ticket.get("reembolso_confirmado_em")
        and ticket.get("estado") in ("pendente", "enviado_parceiro", "decidido")
    )


def pode_resolver(ticket) -> bool:
    return ticket.get("estado") == "decidido"


def pode_reabrir(ticket) -> bool:
    return ticket.get("estado") == "resolvido"


ACOES = {
    "enviar_ao_parceiro": pode_enviar_ao_parceiro,
    "reverter_envio": pode_reverter_envio,
    "registrar_decisao": pode_registrar_decisao,
    "corrigir_autorizacao": pode_corrigir_autorizacao,
    "confirmar_reembolso": pode_confirmar_reembolso,
    "resolver": pode_resolver,
    "reabrir": pode_reabrir,
}


# Próximo passo do fluxo, na ordem de preferência. Reverter, corrigir e reabrir são correções.
PRIORIDADE_ACAO_PRINCIPAL = ("enviar_ao_parceiro", "confirmar_reembolso", "registrar_decisao", "resolver")


def acao_principal(acoes) -> str | None:
    """A ação que a tela destaca em rosa (DESIGN.md: o rosa é ação). None se nenhuma é o próximo passo."""
    return next((a for a in PRIORIDADE_ACAO_PRINCIPAL if a in acoes), None)


def acoes_disponiveis(ticket) -> list[str]:
    """Nomes das ações que a tela deve oferecer pra este ticket."""
    return [nome for nome, regra in ACOES.items() if regra(ticket)]


def pode_editar_obs(ticket) -> bool:
    """OBS: editável, menos enquanto o n8n processa o ticket."""
    return ticket.get("estado") != "processando"


def pode_mudar_acionar_operador(ticket) -> bool:
    """Fora do processamento e do envio: em enviando e enviado_parceiro o banco exige
    acionar_operador marcado (constraint tickets_envio_exige_operador_e_parceiro)."""
    return ticket.get("estado") not in ("processando", "enviando", "enviado_parceiro")


OPCOES_DECISAO = ("Sim", "Não")


def validar_decisao(aprovado, motivo) -> str | None:
    """None se a decisão manual pode ser gravada; senão, o que falta, em português."""
    if aprovado not in OPCOES_DECISAO:
        return "Escolha Sim ou Não."
    if not (motivo or "").strip():
        return "Escreva o motivo da decisão."
    return None


def mensagem_de_erro(erro) -> str:
    """Erro ao gravar em linguagem simples. Nunca devolve o texto cru (pode ter URL ou chave)."""
    if isinstance(erro, PermissionError):
        return "Não consegui identificar quem você é, então nada foi gravado. Abra o app pelo Buser Hub."
    texto = getattr(erro, "message", None) or ""
    if "Transição de estado inválida" in texto:
        return (
            "Esse ticket mudou de situação (talvez o n8n tenha acabado de atualizar). "
            "Nada foi gravado: recarregue a página e tente de novo."
        )
    if "tickets_envio_exige_operador_e_parceiro" in texto:
        return 'Enquanto o ticket está com o parceiro, "acionar operador" precisa ficar marcado e o parceiro definido.'
    if "parceiro_nomes_pkey" in texto:
        return "Esse nome de empresa já está ligado a um parceiro: nada foi gravado."
    if "Reembolso já confirmado" in texto:
        return "O reembolso deste ticket já foi confirmado: a autorização de liderança não muda mais."
    return "Não consegui gravar agora. Tente de novo; se continuar, abra o Diagnóstico."


# -----------------------------------------------------------------------------
# Multa
# -----------------------------------------------------------------------------
def multa_confere(multa_valor, valor_repassado, tolerancia=TOLERANCIA_MULTA) -> bool:
    if multa_valor is None or valor_repassado is None:
        return False
    return abs(float(multa_valor) - float(valor_repassado)) < tolerancia


def descricao_multa(multa_status, multa_valor, valor_repassado) -> tuple[str, str]:
    """(texto, cor) pra mostrar a multa. Cor: 'sucesso', 'erro', 'aviso' ou 'neutro'."""
    if multa_status == "encontrada":
        cor = "sucesso" if multa_confere(multa_valor, valor_repassado) else "erro"
        return formatar_real(multa_valor), cor
    return TEXTO_MULTA.get(multa_status, ("", "neutro"))


TEXTO_DESTINO_REEMBOLSO = {
    "custo_bx": "Custo BX (autorizado por liderança)",
    "multa_parceiro": "Multa na carteira do parceiro",
}


def descricao_destino_reembolso(destino) -> str:
    """Texto pra v_fila.destino_reembolso. A regra mora no banco; aqui só a frase."""
    return TEXTO_DESTINO_REEMBOLSO.get(destino, "")


COR_SLA = {
    "no_prazo": "sucesso",
    "respondido": "neutro",
    "estourado": "erro",
    "nao_enviado": "neutro",
}


def cor_sla(situacao_sla) -> str:
    return COR_SLA.get(situacao_sla, "neutro")


# -----------------------------------------------------------------------------
# Formatação
# -----------------------------------------------------------------------------
def formatar_real(valor) -> str:
    """1234.5 vira 'R$ 1.234,50'. Sem valor vira '—'."""
    if valor is None:
        return "—"
    inteiro = f"{abs(float(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if float(valor) < 0 else ''}R$ {inteiro}"


def _como_datetime(valor):
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, str) and valor.strip():
        return datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    return None


def formatar_data_hora(valor) -> str:
    """Data e hora no fuso de São Paulo: 'dd/mm/aaaa hh:mm'. Sem valor vira '—'."""
    momento = _como_datetime(valor)
    if momento is None:
        return "—"
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def formatar_viagem(data, hora) -> str:
    """'01/10/2026 às 19:00'. A data da viagem é só data: não passa por fuso."""
    if not data:
        return "—"
    texto = date.fromisoformat(str(data)[:10]).strftime("%d/%m/%Y")
    return f"{texto} às {str(hora)[:5]}" if hora else texto


def link_jira(base, chave) -> str | None:
    """Link do ticket no Jira. Sem JIRA_BASE_URL ou sem chave, não há link."""
    if not (base or "").strip() or not chave:
        return None
    return f"{base.strip().rstrip('/')}/browse/{chave}"


# -----------------------------------------------------------------------------
# Linha do tempo (tabela eventos)
# -----------------------------------------------------------------------------
NOME_CAMPO_EVENTO = {
    "estado": "Estado",
    "aprovado": "Resposta do parceiro",
    "motivo_parceiro": "Motivo do parceiro",
    "obs": "OBS",
    "acionar_operador": "Acionar operador",
    "autorizado_lideranca": "Autorização de liderança",
    "reembolso_confirmado_em": "Reembolso confirmado em",
    "multa_status": "Multa",
    "multa_valor": "Valor da multa",
    "parceiro_id": "Parceiro",
    "decisao_id": "Decisão da IA",
}


def _valor_do_evento(campo, valor) -> str:
    # O trigger grava tudo como texto: booleano chega como 'true'/'false'.
    if valor is None or valor == "":
        return "—"
    if campo in ("estado", "criado"):
        return rotulo_estado(valor)
    if valor in ("true", "false"):
        return "sim" if valor == "true" else "não"
    if campo == "reembolso_confirmado_em":
        return formatar_data_hora(valor)
    return valor


def descrever_evento(evento) -> str:
    """'Estado: pendente → enviando'. A criação vira 'Ticket criado em <estado>'."""
    campo = evento.get("campo")
    if campo == "criado":
        return f"Ticket criado em {_valor_do_evento(campo, evento.get('para'))}"
    if campo == "decisao_id":
        return "Nova decisão da IA"  # o id interno não diz nada a quem lê
    nome = NOME_CAMPO_EVENTO.get(campo, campo)
    return f"{nome}: {_valor_do_evento(campo, evento.get('de'))} → {_valor_do_evento(campo, evento.get('para'))}"


# -----------------------------------------------------------------------------
# Contato com o parceiro
# -----------------------------------------------------------------------------
def link_planilha(planilha_id) -> str:
    return f"https://docs.google.com/spreadsheets/d/{planilha_id}/edit"


def limpar_telefone(bruto) -> str | None:
    """Só dígitos, com o 55 do Brasil na frente quando faltar. None se não há número."""
    digitos = re.sub(r"\D", "", str(bruto or ""))
    if not digitos:
        return None
    if not digitos.startswith("55") and len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos


def mensagem_contato(planilha_id) -> str:
    return f"{MENSAGEM_CONTATO_PARCEIRO}\n\n📊 Planilha: {link_planilha(planilha_id)}"


def _codificar(texto: str) -> str:
    # Mesmo conjunto de caracteres preservados do encodeURIComponent do navegador.
    return quote(texto, safe="!~*'()")


def link_contato(whatsapp, email, planilha_id) -> dict:
    """Como avisar o parceiro: {'tipo', 'rotulo', 'url'}. WhatsApp tem prioridade sobre e-mail.

    'GRUPO' no WhatsApp significa contato por grupo: o link abre o WhatsApp com a mensagem
    pronta e a pessoa escolhe o grupo (não existe link que abra um grupo específico).
    """
    mensagem = _codificar(mensagem_contato(planilha_id))
    eh_grupo = str(whatsapp or "").strip().lower() == "grupo"
    telefone = None if eh_grupo else limpar_telefone(whatsapp)

    if eh_grupo:
        return {"tipo": "whatsapp_grupo", "rotulo": "📱 Abrir WhatsApp (escolher grupo)",
                "url": f"https://wa.me/?text={mensagem}"}
    if telefone:
        return {"tipo": "whatsapp", "rotulo": "📱 Abrir WhatsApp",
                "url": f"https://wa.me/{telefone}?text={mensagem}"}
    if email and str(email).strip():
        para = _codificar(str(email).strip())
        assunto = _codificar(ASSUNTO_EMAIL_PARCEIRO)
        return {"tipo": "email", "rotulo": "✉️ Enviar E-mail",
                "url": f"https://mail.google.com/mail/?view=cm&fs=1&to={para}&su={assunto}&body={mensagem}"}
    return {"tipo": "sem_contato", "rotulo": "Sem contato cadastrado", "url": None}


def _limpo(valor) -> str | None:
    """Texto sem espaço nas pontas; vazio vira None (sem contato de verdade)."""
    texto = str(valor or "").strip()
    return texto or None


def validar_contato(whatsapp, email) -> str | None:
    """None se dá pra gravar; senão, o que está errado. Vazio vale (parceiro sem contato)."""
    whatsapp, email = _limpo(whatsapp), _limpo(email)
    if whatsapp and whatsapp.lower() != "grupo":
        telefone = limpar_telefone(whatsapp)
        if not telefone or len(telefone) not in (12, 13) or re.search(r"[a-zA-Z]", whatsapp):
            return f"WhatsApp inválido ({whatsapp}): use o telefone com DDD ou a palavra GRUPO."
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return f"E-mail inválido ({email})."
    return None


def mudancas_de_contato(antes, depois) -> dict[int, dict]:
    """{parceiro_id: campos que mudaram} comparando WhatsApp e e-mail, já limpos."""
    originais = {p["id"]: p for p in antes}
    mudancas = {}
    for linha in depois:
        original = originais[linha["id"]]
        campos = {
            campo: _limpo(linha.get(campo))
            for campo in ("whatsapp", "email")
            if _limpo(linha.get(campo)) != _limpo(original.get(campo))
        }
        if campos:
            mudancas[linha["id"]] = campos
    return mudancas


def empresas_sem_parceiro_com_tickets(empresas_dos_tickets, nomes_cadastrados) -> list[tuple[str, int]]:
    """[(empresa, quantos tickets ela trava)], da que trava mais pra menos."""
    sem_parceiro = set(empresas_sem_parceiro(empresas_dos_tickets, nomes_cadastrados))
    contagem = Counter(e.strip() for e in empresas_dos_tickets if e and e.strip() in sem_parceiro)
    return sorted(contagem.items(), key=lambda item: (-item[1], item[0]))


def empresas_sem_parceiro(empresas_dos_tickets, nomes_cadastrados) -> list[str]:
    """Nomes de empresa que aparecem em tickets mas não estão em nenhum parceiro."""
    cadastrados = {n.strip() for n in nomes_cadastrados}
    pendentes = {e.strip() for e in empresas_dos_tickets if e and e.strip()}
    return sorted(pendentes - cadastrados)
