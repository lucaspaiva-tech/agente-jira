-- =============================================================================
-- AGENTE JIRA | Migration 002: autorização de liderança e custo BX
-- Rodar UMA vez no SQL Editor do Supabase, depois da 001.
--
-- Regra de negócio (confirmada pelo Lucas):
--   O reembolso é SEMPRE multa na carteira do parceiro. Só vira custo BX quando
--   o ticket é Alinhado E foi autorizado por liderança: TL (Team Leader) ou
--   supervisão. Ex.: "autorizado por TL Fulana", "já autorizado pela supervisão".
--
-- Como funciona:
--   - A IA (prompt v11) diz se houve autorização de liderança: decisoes_ia.autorizado_lideranca.
--   - O ticket herda esse valor (tickets.autorizado_lideranca) e a página deixa
--     corrigir ANTES de confirmar o reembolso. Depois de confirmado, não muda mais.
--   - Ao confirmar o reembolso: status que admite custo BX (Alinhado) + autorização
--     marcada = custo_bx. Qualquer outro caso fica pendente de consulta da multa.
--
-- Substitui a regra da 001 em que todo Alinhado virava custo BX (coluna gera_multa).
-- =============================================================================
begin;

-- 1. Colunas novas -------------------------------------------------------------
alter table public.decisoes_ia
  add column autorizado_lideranca boolean not null default false;

alter table public.tickets
  add column autorizado_lideranca boolean not null default false;

-- Qual status admite custo BX quando há autorização de liderança. Hoje: só Alinhado.
alter table public.status_ia_regras
  add column custo_bx_se_autorizado boolean not null default false;
update public.status_ia_regras set custo_bx_se_autorizado = true where status = 'Alinhado';

-- 2. Trigger do ticket (substitui a versão da 001) ----------------------------
create or replace function public.ticket_antes_de_gravar()
returns trigger language plpgsql as $$
declare
  -- A importação do histórico liga app.importando: restaura o que veio da planilha
  -- sem validar transição nem aplicar regra de multa.
  importando boolean := coalesce(current_setting('app.importando', true), '') = 'sim';
begin
  new.atualizado_em := now();

  -- 1. Liga ao parceiro pelo nome da empresa (nome exato, sem espaço nas pontas).
  if new.empresa is not null and (tg_op = 'INSERT' or new.empresa is distinct from old.empresa) then
    select pn.parceiro_id into new.parceiro_id
    from public.parceiro_nomes pn
    where pn.nome = btrim(new.empresa);
  end if;

  if tg_op = 'INSERT' or importando then
    return new;
  end if;

  -- 2. Transição de estado.
  if new.estado is distinct from old.estado then
    if not exists (select 1 from public.transicoes_estado
                   where de = old.estado and para = new.estado) then
      raise exception 'Transição de estado inválida: % -> % (ticket %)',
        old.estado, new.estado, old.jira_key;
    end if;

    -- Carimbos de tempo: quem grava não precisa lembrar, e ninguém esquece.
    if new.estado = 'enviado_parceiro' then new.enviado_parceiro_em := now(); end if;
    if new.estado = 'decidido'         then new.decidido_em := now(); end if;
    if new.estado = 'resolvido'        then new.resolvido_em := now(); end if;
    if old.estado = 'enviado_parceiro' and new.estado = 'pendente' then
      new.enviado_parceiro_em := null;   -- reverter envio zera o SLA
    end if;
    if old.estado = 'resolvido' then new.resolvido_em := null; end if;
  end if;

  -- 3. Autorização de liderança só muda ANTES de confirmar o reembolso: depois disso
  -- ela já decidiu entre custo BX e multa do parceiro.
  if new.autorizado_lideranca is distinct from old.autorizado_lideranca
     and old.reembolso_confirmado_em is not null then
    raise exception 'Reembolso já confirmado (ticket %): a autorização de liderança não pode mais mudar.',
      old.jira_key;
  end if;

  -- 4a. Custo BX: reembolso confirmado agora, status que admite custo BX e autorização marcada.
  if new.reembolso_confirmado_em is not null and old.reembolso_confirmado_em is null
     and new.multa_status is null
     and new.autorizado_lideranca
     and exists (select 1
                 from public.decisoes_ia d
                 join public.status_ia_regras r on r.status = d.status_ia
                 where d.id = new.decisao_id and r.custo_bx_se_autorizado) then
    new.multa_status := 'custo_bx';
  end if;

  -- 4b. Ao ENTRAR em 'aguardando', carimba o início da espera. Tentar de novo a
  -- cada hora não reinicia o prazo (senão ele nunca esgotaria).
  if new.multa_status = 'aguardando' and old.multa_status is distinct from 'aguardando' then
    new.multa_aguardando_desde := now();
  end if;

  return new;
end $$;

-- 3. Decisão da IA: o ticket herda a autorização (substitui a versão da 001) ---
create or replace function public.aplicar_decisao_ia()
returns trigger language plpgsql as $$
declare
  regra public.status_ia_regras%rowtype;
begin
  select * into regra from public.status_ia_regras where status = new.status_ia;

  update public.tickets t set
    decisao_id       = new.id,
    acionar_operador = new.acionar_operador,
    -- reembolso já confirmado: a autorização não muda mais (ver trigger do ticket)
    autorizado_lideranca = case when t.reembolso_confirmado_em is null
                                then new.autorizado_lideranca
                                else t.autorizado_lideranca end,
    atualizado_por   = new.criado_por,
    estado   = case when t.estado = 'processando'
                    then case when regra.automatica then 'decidido' else 'pendente' end
                    else t.estado end,
    aprovado = case when t.estado = 'processando' and regra.automatica
                    then regra.aprovado else t.aprovado end,
    obs      = case when t.estado = 'processando' and regra.automatica
                    then regra.obs else t.obs end
  where t.id = new.ticket_id;

  return new;
end $$;

-- 4. Histórico também registra a autorização (substitui a versão da 001) -------
create or replace function public.registrar_eventos_ticket()
returns trigger language plpgsql as $$
declare
  col    text;
  antes  jsonb;
  depois jsonb := to_jsonb(new);
  colunas text[] := array[
    'estado', 'aprovado', 'motivo_parceiro', 'obs', 'acionar_operador', 'autorizado_lideranca',
    'reembolso_confirmado_em', 'multa_status', 'multa_valor', 'parceiro_id', 'decisao_id'
  ];
begin
  if tg_op = 'INSERT' then
    insert into public.eventos (ticket_id, campo, de, para, autor)
    values (new.id, 'criado', null, new.estado, new.atualizado_por);
    return new;
  end if;

  antes := to_jsonb(old);
  foreach col in array colunas loop
    if antes -> col is distinct from depois -> col then
      insert into public.eventos (ticket_id, campo, de, para, autor)
      values (new.id, col, antes ->> col, depois ->> col, new.atualizado_por);
    end if;
  end loop;
  return new;
end $$;

-- 5. A regra antiga (todo Alinhado = custo BX) sai ------------------------------
alter table public.status_ia_regras drop column gera_multa;

-- 6. v_fila vira o modelo de leitura do ticket (fila e detalhe) ----------------
-- Mesmas colunas da 001, na mesma ordem, mais as novas no fim. Continua SEM dado
-- pessoal de passageiro (esse fica em reservas_oficiais).
create or replace view public.v_fila with (security_invoker = true) as
select
  t.id,
  t.jira_key,
  t.origem,
  t.estado,
  t.empresa,
  t.reserva,
  t.parceiro_id,
  p.nome                      as parceiro,
  d.status_ia,
  t.acionar_operador,
  t.aprovado,
  t.multa_status,
  t.multa_valor,
  t.erro,
  t.recebido_em,
  t.enviado_parceiro_em,
  t.decidido_em,
  sla.horas                   as horas_sla,
  public.formatar_sla(sla.horas) as sla_texto,
  case
    when t.enviado_parceiro_em is null            then 'nao_enviado'
    when t.estado in ('decidido', 'resolvido')    then 'respondido'
    when sla.horas < 48                           then 'no_prazo'
    else 'estourado'
  end                         as situacao_sla,
  -- novas na 002
  t.origem_viagem,
  t.destino_viagem,
  t.data_viagem,
  t.hora_viagem,
  t.motivo_parceiro,
  t.obs,
  t.reembolso_confirmado_em,
  t.resolvido_em,
  t.decisao_id,
  t.autorizado_lideranca,
  coalesce(r.custo_bx_se_autorizado, false) as pede_autorizacao,
  -- o que acontece (ou aconteceu) com o reembolso: mesma regra do trigger
  case when coalesce(r.custo_bx_se_autorizado, false) and t.autorizado_lideranca
       then 'custo_bx' else 'multa_parceiro' end as destino_reembolso
from public.tickets t
left join public.parceiros        p on p.id = t.parceiro_id
left join public.decisoes_ia      d on d.id = t.decisao_id
left join public.status_ia_regras r on r.status = d.status_ia
cross join lateral (
  select case
    when t.enviado_parceiro_em is null then null
    when t.estado in ('decidido', 'resolvido') and t.decidido_em is not null
      then floor(extract(epoch from (t.decidido_em - t.enviado_parceiro_em)) / 3600)::int
    when t.estado = 'enviado_parceiro'
      then floor(extract(epoch from (now() - t.enviado_parceiro_em)) / 3600)::int
  end as horas
) sla;

commit;
