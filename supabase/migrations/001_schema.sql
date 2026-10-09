-- =============================================================================
-- AGENTE JIRA | Migration 001: schema (desenho novo)
-- Rodar UMA vez no SQL Editor do Supabase, depois do reset.sql.
--
-- Princípios:
--  1. Cada dado tem um dono. n8n escreve a decisão da IA, os dados da reserva,
--     a multa e a resposta do parceiro. A página escreve as ações humanas.
--  2. O estado do ticket só muda por transição permitida (tabela + trigger).
--  3. Regra que o n8n E a página compartilham mora AQUI no banco (tabela de
--     regras + trigger), pra existir num lugar só.
--  4. Tudo é idempotente pela chave do Jira (jira_key única).
--  5. Dado pessoal do passageiro fica isolado em reservas_oficiais.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PARCEIROS e os nomes pelos quais o banco da Buser os conhece
-- -----------------------------------------------------------------------------
create table public.parceiros (
  id               bigint generated always as identity primary key,
  nome             text not null unique,
  planilha_id      text not null unique,
  whatsapp         text,   -- telefone, ou a palavra GRUPO (contato por grupo de WhatsApp)
  email            text,
  contato_pendente boolean not null default false,  -- "chegou ticket novo, avise o parceiro"
  ativo            boolean not null default true,
  criado_em        timestamptz not null default now(),
  atualizado_em    timestamptz not null default now(),
  constraint parceiros_nome_sem_espaco_nas_pontas check (nome = btrim(nome))
);

-- Um nome de empresa aponta pra UM parceiro só. A chave primária no nome é o
-- que garante isso: o banco recusa o mesmo nome em dois parceiros.
create table public.parceiro_nomes (
  nome        text primary key,
  parceiro_id bigint not null references public.parceiros (id) on delete cascade,
  criado_em   timestamptz not null default now(),
  constraint parceiro_nomes_sem_espaco_nas_pontas check (nome = btrim(nome))
);
create index parceiro_nomes_parceiro_idx on public.parceiro_nomes (parceiro_id);

-- -----------------------------------------------------------------------------
-- REGRAS DE DECISÃO DA IA e PROMPTS
-- -----------------------------------------------------------------------------
-- Cada status que a IA pode devolver. "automatica" = o caso já nasce resolvido,
-- sem passar pelo parceiro. Mudou o prompt e surgiu status novo? Entra aqui.
create table public.status_ia_regras (
  status     text primary key,
  automatica boolean not null,
  aprovado   text,   -- valor de "Aprovado?" gravado quando a decisão é automática
  obs        text,   -- texto de OBS gravado quando a decisão é automática
  -- false = o reembolso desse caso é custo da Buser (BX), nunca multa do parceiro:
  -- ao confirmar o reembolso, a multa já fica 'custo_bx', sem consultar o banco.
  gera_multa boolean not null default true,
  constraint status_automatico_tem_aprovado check (automatica = (aprovado is not null))
);

insert into public.status_ia_regras (status, automatica, aprovado, obs, gera_multa) values
  ('Aprovado Viação',     true,  'Sim', 'Aprovado', true),
  ('Alinhado',            true,  'Sim', 'Alinhado', false),
  ('Reprovado',           true,  'Não', 'Reprovado', true),
  ('Em Análise',          false, null,  null,       true),
  ('Falta informação BX', false, null,  null,       true);

-- Versões do checklist de regras. O n8n lê a versão ativa. Só uma pode estar ativa.
create table public.prompts (
  versao     text primary key,
  conteudo   text not null,
  ativo      boolean not null default false,
  notas      text,
  criado_em  timestamptz not null default now(),
  criado_por text not null default 'desconhecido'
);
create unique index prompts_so_um_ativo_idx on public.prompts ((true)) where ativo;

-- -----------------------------------------------------------------------------
-- MÁQUINA DE ESTADOS
-- -----------------------------------------------------------------------------
create table public.transicoes_estado (
  de   text not null,
  para text not null,
  primary key (de, para)
);

insert into public.transicoes_estado (de, para) values
  ('processando',      'pendente'),          -- n8n: IA decidiu, falta ação
  ('processando',      'decidido'),          -- n8n: IA decidiu e o caso já nasce resolvido
  ('processando',      'falha'),             -- n8n: falha técnica definitiva
  ('falha',            'processando'),       -- n8n: reprocessamento
  ('pendente',         'enviando'),          -- página: pediu envio ao parceiro
  ('enviando',         'enviado_parceiro'),  -- n8n: linha escrita na planilha do parceiro
  ('enviando',         'pendente'),          -- n8n: o envio falhou (ver coluna erro)
  ('enviado_parceiro', 'pendente'),          -- página: reverteu o envio
  ('pendente',         'decidido'),          -- página: decisão manual
  ('enviado_parceiro', 'decidido'),          -- n8n ou página: o parceiro respondeu
  ('decidido',         'resolvido'),         -- página: arquivou
  ('resolvido',        'decidido');          -- página: reabriu

-- -----------------------------------------------------------------------------
-- TICKETS
-- -----------------------------------------------------------------------------
create table public.tickets (
  id                       bigint generated always as identity primary key,
  jira_key                 text not null unique,
  -- 'teste' marca tudo que nasce durante o desenvolvimento (um único projeto
  -- Supabase). Fica fora das métricas e é apagado antes da troca.
  origem                   text not null default 'motor'
                           check (origem in ('motor', 'importacao', 'teste')),
  estado                   text not null default 'processando'
                           check (estado in ('processando', 'falha', 'pendente', 'enviando',
                                             'enviado_parceiro', 'decidido', 'resolvido')),

  -- Identificação e viagem (dados oficiais do data warehouse)
  reserva                  text,
  empresa                  text,
  parceiro_id              bigint references public.parceiros (id),
  origem_viagem            text,
  destino_viagem           text,
  data_viagem              date,
  hora_viagem              time,

  -- Decisão da IA em vigor (histórico completo em decisoes_ia)
  decisao_id               bigint,   -- chave estrangeira adicionada abaixo (ciclo entre as tabelas)
  acionar_operador         boolean,  -- vem da IA, mas a página pode corrigir

  -- Operação
  aprovado                 text,     -- resposta do parceiro, decisão manual ou decisão automática
  motivo_parceiro          text,     -- coluna "Porque?" da planilha do parceiro
  obs                      text,
  reembolso_confirmado_em  timestamptz,
  multa_valor              numeric(12, 2),
  multa_status             text check (multa_status in ('aguardando', 'encontrada',
                                                        'nao_encontrada', 'custo_bx', 'erro')),
  multa_aguardando_desde   timestamptz,
  erro                     text,     -- último erro técnico (n8n), pra mostrar na tela e no alerta

  -- Linha do tempo (as de estado são carimbadas pelo trigger, não por quem grava)
  recebido_em              timestamptz,
  enviado_parceiro_em      timestamptz,
  decidido_em              timestamptz,
  resolvido_em             timestamptz,

  -- Auditoria: QUEM fez a última escrita. Toda escrita preenche.
  atualizado_por           text not null default 'desconhecido',
  criado_em                timestamptz not null default now(),
  atualizado_em            timestamptz not null default now(),

  constraint tickets_jira_key_valida check (jira_key ~ '^[A-Z][A-Z0-9]*-[0-9]+$'),
  -- Só se envia ao parceiro quando o operador deve ser acionado e há parceiro.
  constraint tickets_envio_exige_operador_e_parceiro
    check (estado not in ('enviando', 'enviado_parceiro')
           or (acionar_operador is true and parceiro_id is not null))
);

create index tickets_estado_idx   on public.tickets (estado);
create index tickets_parceiro_idx on public.tickets (parceiro_id);
create index tickets_reserva_idx  on public.tickets (reserva);
create index tickets_empresa_idx  on public.tickets (empresa);

-- Dados da reserva, incluindo o nome do passageiro (dado pessoal, isolado aqui).
create table public.reservas_oficiais (
  ticket_id         bigint primary key references public.tickets (id) on delete cascade,
  nome_passageiro   text,
  valor_total_pago  numeric(12, 2),
  valor_reserva     numeric(12, 2),
  valor_real        numeric(12, 2),
  valor_repassado   numeric(12, 2),
  comissao          numeric(12, 2),
  taxa_servico      numeric(12, 2),
  seguro            numeric(12, 2),
  marcacao_assento  numeric(12, 2),
  cupom             numeric(12, 2),
  consultado_em     timestamptz not null default now()
);

-- Uma linha por execução da IA. Reprocessar um ticket acrescenta uma linha; o
-- ticket aponta pra mais recente em tickets.decisao_id.
create table public.decisoes_ia (
  id               bigint generated always as identity primary key,
  ticket_id        bigint not null references public.tickets (id) on delete cascade,
  prompt_versao    text not null references public.prompts (versao),
  modelo           text,
  status_ia        text not null references public.status_ia_regras (status),
  resumo_motivo    text,
  parecer          text,
  acionar_operador boolean not null,
  criado_em        timestamptz not null default now(),
  criado_por       text not null default 'n8n'
);
create index decisoes_ia_ticket_idx on public.decisoes_ia (ticket_id, criado_em desc);

alter table public.tickets
  add constraint tickets_decisao_fk foreign key (decisao_id) references public.decisoes_ia (id);

-- -----------------------------------------------------------------------------
-- EVENTOS: histórico de cada mudança. SÓ o trigger escreve aqui.
-- -----------------------------------------------------------------------------
create table public.eventos (
  id        bigint generated always as identity primary key,
  ticket_id bigint not null references public.tickets (id) on delete cascade,
  campo     text not null,   -- 'criado' ou o nome da coluna que mudou
  de        text,
  para      text,
  autor     text not null,
  criado_em timestamptz not null default now()
);
create index eventos_ticket_idx on public.eventos (ticket_id, criado_em);

-- -----------------------------------------------------------------------------
-- FUNÇÕES E TRIGGERS
-- -----------------------------------------------------------------------------

create or replace function public.tocar_atualizado_em()
returns trigger language plpgsql as $$
begin
  new.atualizado_em := now();
  return new;
end $$;

create trigger parceiros_atualizado_em before update on public.parceiros
  for each row execute function public.tocar_atualizado_em();

-- Antes de gravar um ticket: liga ao parceiro, valida a transição e carimba.
create or replace function public.ticket_antes_de_gravar()
returns trigger language plpgsql as $$
begin
  new.atualizado_em := now();

  -- 1. Liga ao parceiro pelo nome da empresa (nome exato, sem espaço nas pontas).
  if new.empresa is not null and (tg_op = 'INSERT' or new.empresa is distinct from old.empresa) then
    select pn.parceiro_id into new.parceiro_id
    from public.parceiro_nomes pn
    where pn.nome = btrim(new.empresa);
  end if;

  -- 2. Transição de estado (só em UPDATE que muda o estado).
  -- A importação do histórico liga app.importando pra poder restaurar qualquer estado.
  if tg_op = 'UPDATE'
     and new.estado is distinct from old.estado
     and coalesce(current_setting('app.importando', true), '') <> 'sim' then

    if not exists (select 1 from public.transicoes_estado
                   where de = old.estado and para = new.estado) then
      raise exception 'Transição de estado inválida: % -> % (ticket %)',
        old.estado, new.estado, old.jira_key;
    end if;

    -- 3. Carimbos de tempo: quem grava não precisa lembrar, e ninguém esquece.
    if new.estado = 'enviado_parceiro' then new.enviado_parceiro_em := now(); end if;
    if new.estado = 'decidido'         then new.decidido_em := now(); end if;
    if new.estado = 'resolvido'        then new.resolvido_em := now(); end if;
    if old.estado = 'enviado_parceiro' and new.estado = 'pendente' then
      new.enviado_parceiro_em := null;   -- reverter envio zera o SLA
    end if;
    if old.estado = 'resolvido' then new.resolvido_em := null; end if;
  end if;

  -- 4. Multa. (a) Reembolso confirmado num caso que nunca gera multa de parceiro
  -- (ex.: Alinhado) já fica 'custo_bx', sem precisar consultar o banco.
  if tg_op = 'UPDATE'
     and new.reembolso_confirmado_em is not null and old.reembolso_confirmado_em is null
     and new.multa_status is null
     and exists (select 1
                 from public.decisoes_ia d
                 join public.status_ia_regras r on r.status = d.status_ia
                 where d.id = new.decisao_id and r.gera_multa is false) then
    new.multa_status := 'custo_bx';
  end if;
  -- (b) Ao ENTRAR em 'aguardando', carimba o início da espera. Tentar de novo a
  -- cada hora não reinicia o prazo (senão ele nunca esgotaria).
  if tg_op = 'UPDATE' and new.multa_status = 'aguardando'
     and old.multa_status is distinct from 'aguardando' then
    new.multa_aguardando_desde := now();
  end if;

  return new;
end $$;

create trigger tickets_antes before insert or update on public.tickets
  for each row execute function public.ticket_antes_de_gravar();

-- Quando um nome novo é cadastrado num parceiro, liga os tickets que já
-- chegaram com esse nome e ainda estavam sem parceiro.
create or replace function public.ligar_tickets_ao_parceiro()
returns trigger language plpgsql as $$
begin
  update public.tickets
     set parceiro_id = new.parceiro_id, atualizado_por = 'sistema'
   where parceiro_id is null and btrim(empresa) = new.nome;
  return new;
end $$;

create trigger parceiro_nomes_liga_tickets after insert on public.parceiro_nomes
  for each row execute function public.ligar_tickets_ao_parceiro();

-- Quando a IA decide: aponta o ticket pra decisão e, se o status é automático,
-- já resolve o caso. É a regra única de "decisão automática": n8n e página não
-- precisam repeti-la.
create or replace function public.aplicar_decisao_ia()
returns trigger language plpgsql as $$
declare
  regra public.status_ia_regras%rowtype;
begin
  select * into regra from public.status_ia_regras where status = new.status_ia;

  update public.tickets t set
    decisao_id       = new.id,
    acionar_operador = new.acionar_operador,
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

create trigger decisoes_ia_aplica after insert on public.decisoes_ia
  for each row execute function public.aplicar_decisao_ia();

-- Histórico: um evento por coluna que mudou, com o autor da escrita.
create or replace function public.registrar_eventos_ticket()
returns trigger language plpgsql as $$
declare
  col    text;
  antes  jsonb;
  depois jsonb := to_jsonb(new);
  colunas text[] := array[
    'estado', 'aprovado', 'motivo_parceiro', 'obs', 'acionar_operador',
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

create trigger tickets_eventos after insert or update on public.tickets
  for each row execute function public.registrar_eventos_ticket();

-- "14h" ou "2d 5h". Regra de formatação do tempo de resposta, usada na página e no n8n.
create or replace function public.formatar_sla(horas integer)
returns text language sql immutable as $$
  select case
    when horas is null then null
    when horas < 24    then horas || 'h'
    else (horas / 24) || 'd ' || (horas % 24) || 'h'
  end
$$;

-- -----------------------------------------------------------------------------
-- VIEWS (security_invoker: respeitam as permissões de quem consulta)
-- -----------------------------------------------------------------------------

-- O que a fila lê. SEM dado pessoal de passageiro.
-- Limite do SLA do parceiro: 48 horas.
create view public.v_fila with (security_invoker = true) as
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
  end                         as situacao_sla
from public.tickets t
left join public.parceiros   p on p.id = t.parceiro_id
left join public.decisoes_ia d on d.id = t.decisao_id
cross join lateral (
  select case
    when t.enviado_parceiro_em is null then null
    when t.estado in ('decidido', 'resolvido') and t.decidido_em is not null
      then floor(extract(epoch from (t.decidido_em - t.enviado_parceiro_em)) / 3600)::int
    when t.estado = 'enviado_parceiro'
      then floor(extract(epoch from (now() - t.enviado_parceiro_em)) / 3600)::int
  end as horas
) sla;

-- Tickets parados num estado que deveria ser rápido (o n8n alerta no Slack).
-- Traz a origem: quem consome decide se ignora os de teste.
create view public.v_tickets_presos with (security_invoker = true) as
select t.id, t.jira_key, t.origem, t.estado, t.atualizado_em, t.erro
from public.tickets t
where (t.estado = 'processando' and t.atualizado_em < now() - interval '30 minutes')
   or (t.estado = 'enviando'    and t.atualizado_em < now() - interval '15 minutes');

-- Reembolsos confirmados cuja multa ainda não foi resolvida. O n8n tenta de novo
-- a cada rodada e desiste quando prazo_esgotado (7 dias de espera) fica true.
create view public.v_multas_pendentes with (security_invoker = true) as
select
  t.id, t.jira_key, t.origem, t.reserva, t.multa_status,
  coalesce(t.multa_aguardando_desde, t.reembolso_confirmado_em) as esperando_desde,
  (now() - coalesce(t.multa_aguardando_desde, t.reembolso_confirmado_em)) >= interval '7 days'
    as prazo_esgotado
from public.tickets t
where t.reembolso_confirmado_em is not null
  and (t.multa_status is null or t.multa_status in ('aguardando', 'erro'));

-- Volume por dia e por decisão da IA (base do dashboard de impacto)
create view public.v_metricas_diarias with (security_invoker = true) as
select
  (t.recebido_em at time zone 'America/Sao_Paulo')::date as dia,
  t.origem,
  d.status_ia,
  count(*)                                   as tickets,
  count(*) filter (where t.estado = 'falha') as falhas
from public.tickets t
left join public.decisoes_ia d on d.id = t.decisao_id
where t.origem <> 'teste'   -- dado de teste nunca entra no cálculo de impacto
group by 1, 2, 3;

-- Uso humano do app por dia: ações, pessoas e tickets tratados. Autor sem "@"
-- (n8n, importacao, sistema) é máquina e não conta como uso.
create view public.v_uso_diario with (security_invoker = true) as
select
  (e.criado_em at time zone 'America/Sao_Paulo')::date as dia,
  count(*)                    as acoes,
  count(distinct e.autor)     as pessoas,
  count(distinct e.ticket_id) as tickets_tratados
from public.eventos e
join public.tickets t on t.id = e.ticket_id
where t.origem <> 'teste'
  and e.autor like '%@%'
group by 1;

-- -----------------------------------------------------------------------------
-- SEGURANÇA
-- RLS ligado e SEM política = a chave pública (anon) não lê nem grava nada.
-- Só a service_role (guardada no n8n e no Hub) acessa, porque ela ignora o RLS.
-- -----------------------------------------------------------------------------
alter table public.parceiros         enable row level security;
alter table public.parceiro_nomes     enable row level security;
alter table public.status_ia_regras   enable row level security;
alter table public.prompts            enable row level security;
alter table public.transicoes_estado  enable row level security;
alter table public.tickets            enable row level security;
alter table public.reservas_oficiais  enable row level security;
alter table public.decisoes_ia        enable row level security;
alter table public.eventos            enable row level security;
