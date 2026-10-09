"""
Gera o SQL de importação (parceiros, nomes, tickets, reservas e decisões) a partir da
exportação .xlsx da planilha "JIRA - Marketplace".

Uso:
    python scripts/gerar_seed.py caminho/da/exportacao.xlsx

Saída:
    supabase/seed/seed.sql  -> colar e rodar no SQL Editor do Supabase (depois das migrations 001 e 002)

Pode rodar quantas vezes quiser (hoje com a exportação de teste, e de novo na troca com a
exportação final): o SQL faz upsert, então atualiza em vez de duplicar, e nunca mexe em
ticket criado pelo motor (origem 'motor') nem nos de teste.
"""

import json
import re
import sys
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ARQ_MAPEAMENTO = RAIZ / "scripts" / "mapeamento_parceiros.json"
ARQ_SAIDA = RAIZ / "supabase" / "seed" / "seed.sql"

TEXTO_ENVIADO = "Enviado ✅"
MULTA_TEXTOS = {
    "⏳ Aguardando registro no banco": "aguardando",
    "Erro na consulta": "erro",
    "⚠️ Multa não encontrada (prazo esgotado)": "nao_encontrada",
    "Custo assumido por BX": "custo_bx",
}
# Tem que bater com a tabela status_ia_regras da migration (um teste confere isso).
STATUS_IA_CONHECIDOS = {
    "Aprovado Viação", "Alinhado", "Reprovado", "Em Análise", "Falta informação BX",
}
VERSAO_PROMPT_IMPORTACAO = "importacao"


# -----------------------------------------------------------------------------
# Leitura tolerante: acha coluna pelo nome ignorando espaço e maiúscula
# -----------------------------------------------------------------------------
def coluna(linha, *nomes):
    for nome in nomes:
        alvo = nome.strip().lower()
        for chave, valor in linha.items():
            if str(chave).strip().lower() == alvo:
                return None if pd.isna(valor) else valor
    return None


def texto(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def numero(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).replace("R$", "").strip()
    if not s or s == "—":
        return None
    s = s.replace(".", "").replace(",", ".") if "," in s else s
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def timestamp_sp(v):
    """Datas da planilha estão no horário de São Paulo: grava com -03."""
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d %H:%M:%S") + "-03"
    s = str(v).strip().replace(",", "")
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S") + "-03"
        except ValueError:
            pass
    return None


def data(v):
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    try:
        return datetime.strptime(str(v).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def hora(v):
    if v is None:
        return None
    if isinstance(v, (datetime, pd.Timestamp, time)):
        return v.strftime("%H:%M:%S")
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", str(v).strip())
    return f"{int(m[1]):02d}:{m[2]}:{m[3] or '00'}" if m else None


def sql(v, tipo=None):
    """Converte valor Python em literal SQL. Com 'tipo', força o cast (necessário em VALUES)."""
    if v is None:
        literal = "null"
    elif isinstance(v, bool):
        literal = "true" if v else "false"
    elif isinstance(v, (int, float)):
        literal = repr(v)
    elif isinstance(v, list):
        return "array[" + ", ".join(sql(x) for x in v) + "]::text[]"
    else:
        literal = "'" + str(v).replace("'", "''") + "'"
    return f"{literal}::{tipo}" if tipo else literal


# -----------------------------------------------------------------------------
# Parceiros: agrupa os nomes do mapeamento por planilha
# -----------------------------------------------------------------------------
def montar_parceiros(contatos_por_nome):
    mapeamento = json.loads(ARQ_MAPEAMENTO.read_text(encoding="utf-8"))
    grupos = {}  # planilha_id -> lista de nomes (ordem preservada)
    for nome, planilha_id in mapeamento.items():
        grupos.setdefault(planilha_id, []).append(nome)

    parceiros = []
    for planilha_id, nomes in grupos.items():
        contato = next((contatos_por_nome[n] for n in nomes if n in contatos_por_nome), {})
        parceiros.append({
            "nome": nomes[0],
            "nomes": nomes,
            "planilha_id": planilha_id,
            "whatsapp": contato.get("whatsapp"),
            "email": contato.get("email"),
        })
    return parceiros, set(mapeamento.keys())


def ler_contatos(xlsx):
    if "Planilhas" not in xlsx.sheet_names:
        return {}
    contatos = {}
    for linha in xlsx.parse("Planilhas").to_dict("records"):
        nome = texto(coluna(linha, "Empresa"))
        if nome:
            contatos[nome] = {
                "whatsapp": texto(coluna(linha, "WhatsApp")),
                "email": texto(coluna(linha, "Email")),
            }
    return contatos


# -----------------------------------------------------------------------------
# Tickets: Central + Resolvidos
# -----------------------------------------------------------------------------
def converter_ticket(linha, veio_de_resolvidos, nomes_mapeados=None):
    """Devolve (ticket, reserva, decisao, avisos) ou None se a linha não tem ID de ticket.

    nomes_mapeados: nomes de empresa que têm parceiro. Quando informado, um ticket
    "Enviado" cuja empresa não tem parceiro (ou sem acionar operador) volta pra
    'pendente', porque o banco recusa envio nessas condições.
    """
    jira_key = texto(coluna(linha, "ID Ticket"))
    if not jira_key:
        return None
    avisos = []

    enviado = texto(coluna(linha, "Enviar Parceiro")) == TEXTO_ENVIADO
    aprovado = texto(coluna(linha, "Aprovado?"))
    resolvido_flag = coluna(linha, "Resolvido") in (True, "TRUE", "true")
    empresa = texto(coluna(linha, "Empresa"))

    acionar = (texto(coluna(linha, "Acionar operador?")) or "").lower()
    # Três estados de propósito: sim, não, ou desconhecido (vazio na planilha).
    acionar_operador = True if acionar == "sim" else (False if acionar in ("não", "nao") else None)

    if veio_de_resolvidos or resolvido_flag:
        estado = "resolvido"
    elif aprovado:
        estado = "decidido"
    elif enviado:
        estado = "enviado_parceiro"
    else:
        estado = "pendente"

    if estado == "enviado_parceiro":
        sem_parceiro = nomes_mapeados is not None and empresa not in nomes_mapeados
        if sem_parceiro or acionar_operador is not True:
            estado = "pendente"
            avisos.append(f"{jira_key}: estava 'Enviado' mas sem parceiro ou sem acionar operador; importado como pendente")

    multa_bruta = coluna(linha, "Multa Parceiro")
    multa_valor = numero(multa_bruta)
    multa_status = "encontrada" if multa_valor is not None else MULTA_TEXTOS.get(texto(multa_bruta))

    recebido_em = timestamp_sp(coluna(linha, "Data/Hora JIRA"))
    # A planilha guarda que o reembolso foi confirmado ("Reembolso" = Sim), mas não quando.
    # Aproximação: a data de chegada do ticket. Sem isso, a página ofereceria confirmar de novo.
    reembolso_confirmado = (texto(coluna(linha, "Reembolso")) or "").lower() == "sim"
    status_ia = texto(coluna(linha, "Status JIRA"))
    # Histórico: Alinhado que a planilha fechou como custo BX foi autorizado por liderança.
    autorizado_lideranca = status_ia == "Alinhado" and multa_status == "custo_bx"

    ticket = {
        "jira_key": jira_key,
        "origem": "importacao",
        "estado": estado,
        "reserva": texto(coluna(linha, "Reserva")),
        "empresa": empresa,
        "origem_viagem": texto(coluna(linha, "Origem")),
        "destino_viagem": texto(coluna(linha, "Destino")),
        "data_viagem": data(coluna(linha, "Data viagem")),
        "hora_viagem": hora(coluna(linha, "Horário")),
        "acionar_operador": acionar_operador,
        "aprovado": aprovado,
        "motivo_parceiro": None,
        "obs": texto(coluna(linha, "OBS")),
        "reembolso_confirmado_em": recebido_em if reembolso_confirmado else None,
        "autorizado_lideranca": autorizado_lideranca,
        "multa_valor": multa_valor,
        "multa_status": multa_status,
        "multa_aguardando_desde": None,
        "erro": None,
        "recebido_em": recebido_em,
        "enviado_parceiro_em": timestamp_sp(coluna(linha, "Data")) if enviado else None,
        "decidido_em": None,
        "resolvido_em": None,
        "atualizado_por": "importacao",
    }
    reserva = {
        "jira_key": jira_key,
        "nome_passageiro": texto(coluna(linha, "Passageiro(os)")),
        "valor_total_pago": numero(coluna(linha, "Valor total Pago")),
        "valor_reserva": numero(coluna(linha, "Valor reserva")),
        "valor_real": numero(coluna(linha, "Valor Real")),
        "valor_repassado": numero(coluna(linha, "Valor Repassado")),
        "comissao": numero(coluna(linha, "Comissão")),
        "taxa_servico": numero(coluna(linha, "Taxa de Serviço")),
        "seguro": numero(coluna(linha, "Seguro")),
        "marcacao_assento": numero(coluna(linha, "Marcação de assento")),
        "cupom": numero(coluna(linha, "Cupom")),
    }

    decisao = None
    if status_ia in STATUS_IA_CONHECIDOS:
        decisao = {
            "jira_key": jira_key,
            "status_ia": status_ia,
            "resumo_motivo": texto(coluna(linha, "Motivo (Passageiro)")),
            "parecer": texto(coluna(linha, "Parecer da Solicitação")),
            "acionar_operador": bool(acionar_operador),
            "autorizado_lideranca": autorizado_lideranca,
        }
    elif status_ia:
        avisos.append(f"{jira_key}: status '{status_ia}' não existe em status_ia_regras; decisão não importada")

    return ticket, reserva, decisao, avisos


def ler_tickets(xlsx, nomes_mapeados=None):
    por_chave = {}  # Resolvidos sobrescreve Central
    for aba, de_resolvidos in (("Central", False), ("Resolvidos", True)):
        if aba not in xlsx.sheet_names:
            continue
        for linha in xlsx.parse(aba).to_dict("records"):
            convertido = converter_ticket(linha, de_resolvidos, nomes_mapeados)
            if convertido:
                por_chave[convertido[0]["jira_key"]] = convertido
    return list(por_chave.values())


# -----------------------------------------------------------------------------
# Geração do SQL
# -----------------------------------------------------------------------------
TIPOS_TICKET = {
    "data_viagem": "date", "hora_viagem": "time", "acionar_operador": "boolean",
    "multa_valor": "numeric", "reembolso_confirmado_em": "timestamptz",
    "multa_aguardando_desde": "timestamptz", "recebido_em": "timestamptz",
    "enviado_parceiro_em": "timestamptz", "decidido_em": "timestamptz",
    "resolvido_em": "timestamptz",
}


def lotes(itens, tamanho=200):
    for i in range(0, len(itens), tamanho):
        yield itens[i:i + tamanho]


def gerar_sql(parceiros, convertidos):
    out = [
        "-- Gerado por scripts/gerar_seed.py em " + datetime.now().strftime("%d/%m/%Y %H:%M"),
        "-- Contém nome de passageiro: NÃO versionar (está no .gitignore).",
        "begin;",
        "-- Liga a importação: permite restaurar qualquer estado de ticket importado.",
        "set local app.importando = 'sim';",
        "",
        "insert into public.prompts (versao, conteudo, ativo, notas) values",
        f"  ({sql(VERSAO_PROMPT_IMPORTACAO)}, 'Decisão importada da planilha antiga (sem prompt registrado)',",
        "   false, 'Criada pela importação do histórico')",
        "on conflict (versao) do nothing;",
        "",
    ]

    # PARCEIROS (upsert pela planilha). Contato só é sobrescrito se a exportação trouxer valor.
    out.append("insert into public.parceiros (nome, planilha_id, whatsapp, email) values")
    out.append(",\n".join(
        f"  ({sql(p['nome'])}, {sql(p['planilha_id'])}, {sql(p['whatsapp'])}, {sql(p['email'])})"
        for p in parceiros
    ))
    out.append("on conflict (planilha_id) do update set")
    out.append("  whatsapp = coalesce(excluded.whatsapp, public.parceiros.whatsapp),")
    out.append("  email = coalesce(excluded.email, public.parceiros.email);")
    out.append("")

    # NOMES (nome de empresa -> parceiro, resolvido pela planilha)
    pares = [(n, p["planilha_id"]) for p in parceiros for n in p["nomes"]]
    out.append("insert into public.parceiro_nomes (nome, parceiro_id)")
    out.append("select v.nome, p.id from (values")
    out.append(",\n".join(f"  ({sql(n, 'text')}, {sql(pl, 'text')})" for n, pl in pares))
    out.append(") as v(nome, planilha_id)")
    out.append("join public.parceiros p on p.planilha_id = v.planilha_id")
    out.append("on conflict (nome) do update set parceiro_id = excluded.parceiro_id;")
    out.append("")

    if convertidos:
        tickets = [c[0] for c in convertidos]
        colunas = list(tickets[0].keys())
        atualizaveis = [c for c in colunas if c not in ("jira_key", "origem")]
        for lote in lotes(tickets):
            out.append(f"insert into public.tickets ({', '.join(colunas)}) values")
            out.append(",\n".join("  (" + ", ".join(sql(t[c]) for c in colunas) + ")" for t in lote))
            out.append("on conflict (jira_key) do update set")
            out.append(",\n".join(f"  {c} = excluded.{c}" for c in atualizaveis))
            out.append("where public.tickets.origem = 'importacao';")
            out.append("")

        # RESERVAS OFICIAIS (dado do passageiro, isolado)
        reservas = [c[1] for c in convertidos]
        cols_res = [c for c in reservas[0] if c != "jira_key"]
        for lote in lotes(reservas):
            out.append(f"insert into public.reservas_oficiais (ticket_id, {', '.join(cols_res)})")
            out.append(f"select t.id, {', '.join('v.' + c for c in cols_res)} from (values")
            out.append(",\n".join(
                "  (" + ", ".join(
                    [sql(r["jira_key"], "text"), sql(r["nome_passageiro"], "text")]
                    + [sql(r[c], "numeric") for c in cols_res if c != "nome_passageiro"]
                ) + ")" for r in lote
            ))
            out.append(f") as v(jira_key, {', '.join(cols_res)})")
            out.append("join public.tickets t on t.jira_key = v.jira_key and t.origem = 'importacao'")
            out.append("on conflict (ticket_id) do update set")
            out.append(",\n".join(f"  {c} = excluded.{c}" for c in cols_res))
            out.append(";")
            out.append("")

        # DECISÕES DA IA (uma por ticket importado; não repete se já existir)
        decisoes = [c[2] for c in convertidos if c[2]]
        for lote in lotes(decisoes):
            out.append("insert into public.decisoes_ia")
            out.append("  (ticket_id, prompt_versao, status_ia, resumo_motivo, parecer, acionar_operador, autorizado_lideranca, criado_por)")
            out.append(f"select t.id, {sql(VERSAO_PROMPT_IMPORTACAO)}, v.status_ia, v.resumo_motivo, v.parecer,")
            out.append("       v.acionar_operador, v.autorizado_lideranca, 'importacao' from (values")
            out.append(",\n".join(
                "  (" + ", ".join([
                    sql(d["jira_key"], "text"), sql(d["status_ia"], "text"),
                    sql(d["resumo_motivo"], "text"), sql(d["parecer"], "text"),
                    sql(d["acionar_operador"], "boolean"), sql(d["autorizado_lideranca"], "boolean"),
                ]) + ")" for d in lote
            ))
            out.append(") as v(jira_key, status_ia, resumo_motivo, parecer, acionar_operador, autorizado_lideranca)")
            out.append("join public.tickets t on t.jira_key = v.jira_key and t.origem = 'importacao'")
            out.append("where not exists (select 1 from public.decisoes_ia d")
            out.append(f"  where d.ticket_id = t.id and d.prompt_versao = {sql(VERSAO_PROMPT_IMPORTACAO)});")
            out.append("")

    out.append("commit;")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/gerar_seed.py caminho/da/exportacao.xlsx")

    xlsx = pd.ExcelFile(sys.argv[1])
    parceiros, nomes_mapeados = montar_parceiros(ler_contatos(xlsx))
    convertidos = ler_tickets(xlsx, nomes_mapeados)

    ARQ_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQ_SAIDA.write_text(gerar_sql(parceiros, convertidos), encoding="utf-8")

    # Relatório pra conferir antes de rodar no Supabase
    tickets = [c[0] for c in convertidos]
    sem_parceiro = sorted({t["empresa"] for t in tickets if t["empresa"] and t["empresa"] not in nomes_mapeados})
    por_estado = {}
    if tickets:
        por_estado = pd.Series([t["estado"] for t in tickets]).value_counts().to_dict()
    print(f"Parceiros: {len(parceiros)} (agrupando {len(nomes_mapeados)} nomes de empresa)")
    print(f"  com contato: {sum(1 for p in parceiros if p['whatsapp'] or p['email'])}")
    print(f"Tickets: {len(tickets)} | por estado: {por_estado}")
    print(f"Decisões da IA importadas: {sum(1 for c in convertidos if c[2])}")
    avisos = [a for c in convertidos for a in c[3]]
    for aviso in avisos:
        print(f"AVISO: {aviso}")
    if sem_parceiro:
        print(f"ATENÇÃO, empresas sem planilha mapeada: {', '.join(sem_parceiro)}")
    print(f"SQL gerado em: {ARQ_SAIDA}")


if __name__ == "__main__":
    main()
