-- =============================================================================
-- TESTES DO BANCO (precisa das migrations 001 e 002). Seguro de rodar a qualquer hora: tudo acontece dentro de uma
-- transação que termina em ROLLBACK, então nada fica gravado.
--
-- Resultado: no fim aparece "TODOS OS TESTES PASSARAM". Se algum falhar, o erro
-- diz qual e por quê, e o script para.
-- Como rodar: SQL Editor do Supabase (cole tudo) ou scripts/testar_banco.sh.
-- =============================================================================
begin;

-- Ajudantes (existem só nesta sessão)
create or replace function pg_temp.afirmar(ok boolean, descricao text) returns void
language plpgsql as $$
begin
  if ok is not true then raise exception 'FALHOU: %', descricao; end if;
  raise notice 'ok: %', descricao;
end $$;

-- Executa um comando que DEVE dar erro, e confere se a mensagem contém o trecho.
create or replace function pg_temp.deve_falhar(comando text, trecho text, descricao text)
returns void language plpgsql as $$
declare mensagem text;
begin
  begin
    execute comando;
  exception when others then
    mensagem := sqlerrm;
  end;
  if mensagem is null then
    raise exception 'FALHOU: % (era pra dar erro e não deu)', descricao;
  end if;
  if position(trecho in mensagem) = 0 then
    raise exception 'FALHOU: % (erro diferente do esperado: %)', descricao, mensagem;
  end if;
  raise notice 'ok: %', descricao;
end $$;

-- Cenário base (tudo some no rollback do fim)
update public.prompts set ativo = false where ativo;   -- o prompt real volta a ser ativo no rollback
insert into public.prompts (versao, conteudo, ativo) values ('t1', 'prompt de teste', true);
insert into public.parceiros (nome, planilha_id) values ('Parceiro A', 'planilha-a'), ('Parceiro B', 'planilha-b');
insert into public.parceiro_nomes (nome, parceiro_id)
  select 'Empresa A', id from public.parceiros where nome = 'Parceiro A';
insert into public.parceiro_nomes (nome, parceiro_id)
  select 'Empresa A Filial', id from public.parceiros where nome = 'Parceiro A';

-- ---------------------------------------------------------------- parceiros
select pg_temp.deve_falhar(
  $q$insert into public.parceiro_nomes (nome, parceiro_id) select 'Empresa A', id from public.parceiros where nome = 'Parceiro B'$q$,
  'parceiro_nomes_pkey', 'um nome de empresa não pode apontar pra dois parceiros');
select pg_temp.deve_falhar(
  $q$insert into public.parceiro_nomes (nome, parceiro_id) select ' Empresa X', id from public.parceiros limit 1$q$,
  'sem_espaco_nas_pontas', 'nome com espaço nas pontas é recusado');
select pg_temp.deve_falhar(
  $q$insert into public.prompts (versao, conteudo, ativo) values ('t2', 'outro', true)$q$,
  'prompts_so_um_ativo_idx', 'só pode haver um prompt ativo');

-- ---------------------------------------------------------------- tickets: ligação ao parceiro
insert into public.tickets (jira_key, origem, empresa, atualizado_por)
values ('TESTEDB-1', 'teste', 'Empresa A', 'n8n'), ('TESTEDB-2', 'teste', 'Empresa Nova', 'n8n');

select pg_temp.afirmar(
  (select parceiro_id from public.tickets where jira_key = 'TESTEDB-1')
    = (select id from public.parceiros where nome = 'Parceiro A'),
  'ticket é ligado ao parceiro pelo nome da empresa');
select pg_temp.afirmar(
  (select parceiro_id is null from public.tickets where jira_key = 'TESTEDB-2'),
  'empresa sem cadastro fica sem parceiro');

insert into public.parceiro_nomes (nome, parceiro_id)
  select 'Empresa Nova', id from public.parceiros where nome = 'Parceiro B';
select pg_temp.afirmar(
  (select parceiro_id from public.tickets where jira_key = 'TESTEDB-2')
    = (select id from public.parceiros where nome = 'Parceiro B'),
  'cadastrar um nome novo liga os tickets que já tinham chegado com ele');

select pg_temp.deve_falhar(
  $q$insert into public.tickets (jira_key, atualizado_por) values ('chave invalida', 'n8n')$q$,
  'tickets_jira_key_valida', 'chave do Jira inválida é recusada');
select pg_temp.deve_falhar(
  $q$insert into public.tickets (jira_key, atualizado_por) values ('TESTEDB-1', 'n8n')$q$,
  'tickets_jira_key_key', 'o mesmo ticket não entra duas vezes (idempotência)');

-- ---------------------------------------------------------------- decisão da IA
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, parecer)
select id, 't1', 'Em Análise', true, 'precisa de análise' from public.tickets where jira_key = 'TESTEDB-1';

select pg_temp.afirmar(
  (select estado from public.tickets where jira_key = 'TESTEDB-1') = 'pendente',
  'decisão não automática deixa o ticket pendente');
select pg_temp.afirmar(
  (select acionar_operador from public.tickets where jira_key = 'TESTEDB-1') is true
  and (select decisao_id from public.tickets where jira_key = 'TESTEDB-1') is not null,
  'ticket aponta pra decisão e herda acionar_operador');

insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador)
select id, 't1', 'Aprovado Viação', false from public.tickets where jira_key = 'TESTEDB-2';
select pg_temp.afirmar(
  (select (estado, aprovado, obs) = ('decidido', 'Sim', 'Aprovado') from public.tickets where jira_key = 'TESTEDB-2'),
  'decisão automática já resolve o caso (estado, aprovado e obs)');
select pg_temp.afirmar(
  (select decidido_em is not null from public.tickets where jira_key = 'TESTEDB-2'),
  'decisão automática carimba decidido_em');

select pg_temp.deve_falhar(
  $q$insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador)
     select id, 't1', 'Status Inventado', false from public.tickets where jira_key = 'TESTEDB-1'$q$,
  'decisoes_ia_status_ia_fkey', 'status da IA desconhecido é recusado');

-- ---------------------------------------------------------------- transições
select pg_temp.deve_falhar(
  $q$update public.tickets set estado = 'resolvido', atualizado_por = 'a@b.com' where jira_key = 'TESTEDB-1'$q$,
  'Transição de estado inválida', 'pendente -> resolvido é recusado');

select pg_temp.deve_falhar(
  $q$update public.tickets set estado = 'enviando', acionar_operador = false, atualizado_por = 'a@b.com' where jira_key = 'TESTEDB-1'$q$,
  'tickets_envio_exige_operador_e_parceiro', 'não envia sem acionar_operador');
select pg_temp.deve_falhar(
  $q$update public.tickets set estado = 'enviando', atualizado_por = 'a@b.com' where jira_key = 'TESTEDB-2'$q$,
  'Transição de estado inválida', 'decidido -> enviando é recusado');

update public.tickets set estado = 'enviando', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
update public.tickets set estado = 'enviado_parceiro', atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select enviado_parceiro_em is not null from public.tickets where jira_key = 'TESTEDB-1'),
  'entrar em enviado_parceiro carimba enviado_parceiro_em');

update public.tickets set estado = 'pendente', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select enviado_parceiro_em is null from public.tickets where jira_key = 'TESTEDB-1'),
  'reverter o envio zera enviado_parceiro_em');

update public.tickets set estado = 'enviando', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
update public.tickets set estado = 'enviado_parceiro', atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
update public.tickets set estado = 'decidido', aprovado = 'Sim', motivo_parceiro = 'ok', atualizado_por = 'n8n'
 where jira_key = 'TESTEDB-1';
update public.tickets set estado = 'resolvido', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select decidido_em is not null and resolvido_em is not null from public.tickets where jira_key = 'TESTEDB-1'),
  'decidido e resolvido carimbam as datas');
update public.tickets set estado = 'decidido', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select resolvido_em is null from public.tickets where jira_key = 'TESTEDB-1'),
  'reabrir um ticket resolvido zera resolvido_em');

-- ---------------------------------------------------------------- reserva oficial
insert into public.reservas_oficiais (ticket_id, nome_passageiro, valor_repassado)
select id, 'Passageiro Teste', 100 from public.tickets where jira_key = 'TESTEDB-1';
select pg_temp.deve_falhar(
  $q$insert into public.reservas_oficiais (ticket_id) select id from public.tickets where jira_key = 'TESTEDB-1'$q$,
  'reservas_oficiais_pkey', 'um ticket tem uma reserva oficial só');

-- ---------------------------------------------------------------- eventos
select pg_temp.afirmar(
  (select count(*) from public.eventos e join public.tickets t on t.id = e.ticket_id
    where t.jira_key = 'TESTEDB-1' and e.campo = 'estado' and e.autor = 'ana@buser.com.br') >= 2,
  'cada mudança de estado vira evento com o e-mail de quem fez');
select pg_temp.afirmar(
  (select count(*) from public.eventos e join public.tickets t on t.id = e.ticket_id
    where t.jira_key = 'TESTEDB-1' and e.campo = 'criado') = 1,
  'a criação do ticket vira um evento "criado"');

do $$
declare antes int; depois int;
begin
  select count(*) into antes from public.eventos;
  update public.tickets set atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
  select count(*) into depois from public.eventos;
  perform pg_temp.afirmar(antes = depois, 'gravar sem mudar nada não gera evento');
end $$;

-- ---------------------------------------------------------------- v_fila (SLA)
insert into public.tickets (jira_key, origem, empresa, acionar_operador, estado, enviado_parceiro_em, atualizado_por)
values ('TESTEDB-3', 'teste', 'Empresa A', true, 'enviado_parceiro', now() - interval '10 hours', 'n8n'),
       ('TESTEDB-4', 'teste', 'Empresa A', true, 'enviado_parceiro', now() - interval '60 hours', 'n8n');

select pg_temp.afirmar(
  (select (situacao_sla, sla_texto) = ('no_prazo', '10h') from public.v_fila where jira_key = 'TESTEDB-3'),
  'SLA de 10h está no prazo e aparece como "10h"');
select pg_temp.afirmar(
  (select (situacao_sla, sla_texto) = ('estourado', '2d 12h') from public.v_fila where jira_key = 'TESTEDB-4'),
  'SLA de 60h está estourado e aparece como "2d 12h"');
select pg_temp.afirmar(
  (select situacao_sla from public.v_fila where jira_key = 'TESTEDB-2') = 'nao_enviado',
  'ticket nunca enviado ao parceiro é "nao_enviado"');
select pg_temp.afirmar(
  not exists (select 1 from information_schema.columns
               where table_schema = 'public' and table_name = 'v_fila'
                 and column_name like '%passageiro%'),
  'a view da fila não expõe dado pessoal de passageiro');

-- ---------------------------------------------------------------- tickets presos
insert into public.tickets (jira_key, origem, estado, atualizado_por) values ('TESTEDB-5', 'motor', 'processando', 'n8n');
-- o trigger sobrescreve atualizado_em com now(); força o valor antigo desligando-o só aqui
alter table public.tickets disable trigger tickets_antes;
update public.tickets set atualizado_em = now() - interval '2 hours' where jira_key = 'TESTEDB-5';
alter table public.tickets enable trigger tickets_antes;
select pg_temp.afirmar(
  (select origem from public.v_tickets_presos where jira_key = 'TESTEDB-5') = 'motor',
  'ticket parado em "processando" há 2h aparece como preso');
delete from public.tickets where jira_key = 'TESTEDB-5';

-- ---------------------------------------------------------------- multa e custo BX
-- Regra: o reembolso é sempre multa do parceiro. Só vira custo BX quando o ticket é
-- Alinhado E foi autorizado por liderança (TL ou supervisão).

-- Alinhado SEM autorização de liderança: continua sendo multa do parceiro.
insert into public.tickets (jira_key, origem, empresa, atualizado_por) values ('TESTEDB-6', 'teste', 'Empresa A', 'n8n');
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, autorizado_lideranca)
select id, 't1', 'Alinhado', false, false from public.tickets where jira_key = 'TESTEDB-6';
update public.tickets set reembolso_confirmado_em = now(), atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-6';
select pg_temp.afirmar(
  (select multa_status is null from public.tickets where jira_key = 'TESTEDB-6')
  and exists (select 1 from public.v_multas_pendentes where jira_key = 'TESTEDB-6'),
  'Alinhado sem autorização de liderança é multa do parceiro (fica pendente de consulta)');

-- Alinhado COM autorização de liderança: custo BX.
insert into public.tickets (jira_key, origem, empresa, atualizado_por) values ('TESTEDB-7', 'teste', 'Empresa A', 'n8n');
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, autorizado_lideranca)
select id, 't1', 'Alinhado', false, true from public.tickets where jira_key = 'TESTEDB-7';
select pg_temp.afirmar(
  (select autorizado_lideranca from public.tickets where jira_key = 'TESTEDB-7')
  and (select destino_reembolso from public.v_fila where jira_key = 'TESTEDB-7') = 'custo_bx',
  'o ticket herda a autorização da IA e a fila mostra que o reembolso vira custo BX');
update public.tickets set reembolso_confirmado_em = now(), atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-7';
select pg_temp.afirmar(
  (select multa_status from public.tickets where jira_key = 'TESTEDB-7') = 'custo_bx'
  and not exists (select 1 from public.v_multas_pendentes where jira_key = 'TESTEDB-7'),
  'Alinhado com autorização de liderança vira custo BX e não aparece nas multas pendentes');

-- Autorização marcada num status que não é Alinhado não muda nada: continua multa.
insert into public.tickets (jira_key, origem, empresa, atualizado_por) values ('TESTEDB-8', 'teste', 'Empresa A', 'n8n');
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, autorizado_lideranca)
select id, 't1', 'Em Análise', true, true from public.tickets where jira_key = 'TESTEDB-8';
update public.tickets set estado = 'decidido', aprovado = 'Sim', atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-8';
update public.tickets set reembolso_confirmado_em = now(), atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-8';
select pg_temp.afirmar(
  (select multa_status is null from public.tickets where jira_key = 'TESTEDB-8')
  and (select destino_reembolso from public.v_fila where jira_key = 'TESTEDB-8') = 'multa_parceiro',
  'autorização de liderança fora do Alinhado não vira custo BX');

-- A pessoa corrige a autorização antes de confirmar; depois de confirmar, não muda mais.
insert into public.tickets (jira_key, origem, empresa, atualizado_por) values ('TESTEDB-9', 'teste', 'Empresa A', 'n8n');
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, autorizado_lideranca)
select id, 't1', 'Alinhado', false, false from public.tickets where jira_key = 'TESTEDB-9';
update public.tickets set autorizado_lideranca = true, atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-9';
select pg_temp.afirmar(
  exists (select 1 from public.eventos e join public.tickets t on t.id = e.ticket_id
           where t.jira_key = 'TESTEDB-9' and e.campo = 'autorizado_lideranca' and e.autor = 'ana@buser.com.br'),
  'corrigir a autorização antes do reembolso é permitido e fica no histórico');
update public.tickets set reembolso_confirmado_em = now(), atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-9';
select pg_temp.afirmar(
  (select multa_status from public.tickets where jira_key = 'TESTEDB-9') = 'custo_bx',
  'a correção feita pela pessoa vale na hora de confirmar o reembolso');
select pg_temp.deve_falhar(
  $q$update public.tickets set autorizado_lideranca = false, atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-9'$q$,
  'não pode mais mudar', 'depois de confirmar o reembolso a autorização não muda mais');

-- Reprocessar a IA depois do reembolso confirmado não quebra nem muda a autorização.
insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, acionar_operador, autorizado_lideranca)
select id, 't1', 'Alinhado', false, false from public.tickets where jira_key = 'TESTEDB-9';
select pg_temp.afirmar(
  (select autorizado_lideranca from public.tickets where jira_key = 'TESTEDB-9'),
  'uma decisão nova da IA não desfaz a autorização de um reembolso já confirmado');

-- Caso comum: fica pendente de consulta, e o prazo de espera conta a partir do 'aguardando'.
update public.tickets set reembolso_confirmado_em = now(), atualizado_por = 'ana@buser.com.br' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select multa_status is null from public.tickets where jira_key = 'TESTEDB-1')
  and exists (select 1 from public.v_multas_pendentes where jira_key = 'TESTEDB-1' and not prazo_esgotado),
  'reembolso confirmado em caso comum aguarda a consulta de multa');

update public.tickets set multa_status = 'aguardando', atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select multa_aguardando_desde is not null from public.tickets where jira_key = 'TESTEDB-1'),
  'entrar em "aguardando" carimba o início da espera');

update public.tickets set multa_aguardando_desde = now() - interval '8 days', atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
update public.tickets set multa_status = 'aguardando', obs = 'tentou de novo', atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  (select multa_aguardando_desde < now() - interval '7 days' from public.tickets where jira_key = 'TESTEDB-1'),
  'tentar de novo estando "aguardando" não reinicia o prazo');
select pg_temp.afirmar(
  (select prazo_esgotado from public.v_multas_pendentes where jira_key = 'TESTEDB-1'),
  'depois de 7 dias de espera o prazo aparece como esgotado');

update public.tickets set multa_status = 'encontrada', multa_valor = 100, atualizado_por = 'n8n' where jira_key = 'TESTEDB-1';
select pg_temp.afirmar(
  not exists (select 1 from public.v_multas_pendentes where jira_key = 'TESTEDB-1'),
  'multa encontrada sai das pendentes');

-- ---------------------------------------------------------------- uso e métricas
-- Mede a DIFERENÇA no uso de hoje: o banco real já pode ter uso registrado.
create temporary table uso_antes on commit drop as
select coalesce((select acoes from public.v_uso_diario
                  where dia = (now() at time zone 'America/Sao_Paulo')::date), 0) as acoes;

insert into public.tickets (jira_key, origem, estado, atualizado_por, recebido_em)
values ('TESTEDB-100', 'motor', 'pendente', 'n8n', now());
update public.tickets set obs = 'x', atualizado_por = 'lucas@buser.com.br' where jira_key = 'TESTEDB-100';
update public.tickets set obs = 'y', atualizado_por = 'n8n' where jira_key = 'TESTEDB-100';
update public.tickets set obs = 'teste', atualizado_por = 'lucas@buser.com.br' where jira_key = 'TESTEDB-1';

select pg_temp.afirmar(
  (select acoes from public.v_uso_diario where dia = (now() at time zone 'America/Sao_Paulo')::date)
    - (select acoes from uso_antes) = 1,
  'uso conta só ação de gente (e-mail), fora n8n e fora ticket de teste');
select pg_temp.afirmar(
  not exists (select 1 from public.v_metricas_diarias where origem = 'teste'),
  'métricas ignoram ticket de teste');

-- ---------------------------------------------------------------- segurança
-- A chave pública (papel anon) não pode ler nem pelas tabelas nem pelas views. No Supabase ela
-- tem permissão de tabela e quem barra é o RLS (conta 0 linhas); em outro Postgres pode nem ter
-- permissão (erro). As duas situações são "não lê", e as duas passam.
create or replace function pg_temp.anon_nao_le(objeto text, descricao text) returns void
language plpgsql as $$
declare n bigint;
begin
  begin
    execute format('select count(*) from %s', objeto) into n;
    if n <> 0 then raise exception 'FALHOU: % (a chave pública leu % linhas)', descricao, n; end if;
  exception when insufficient_privilege then
    null;  -- sem permissão: também não lê
  end;
  raise notice 'ok: %', descricao;
end $$;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    set local role anon;
    perform pg_temp.anon_nao_le('public.tickets', 'chave pública não lê tickets');
    perform pg_temp.anon_nao_le('public.reservas_oficiais', 'chave pública não lê dado de passageiro');
    perform pg_temp.anon_nao_le('public.v_fila', 'chave pública não lê a fila');
    reset role;
  else
    raise notice 'papel anon não existe aqui: teste de acesso público pulado';
  end if;
end $$;

do $$ begin raise notice '=== TODOS OS TESTES PASSARAM ==='; end $$;
rollback;
