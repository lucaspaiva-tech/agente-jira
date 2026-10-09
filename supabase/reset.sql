-- =============================================================================
-- AGENTE JIRA | RESET: apaga o desenho antigo do banco (DESTRUTIVO)
--
-- Quando usar: UMA vez, antes de rodar migrations/001_schema.sql, só pra trocar
-- o desenho antigo (parceiros, tickets, eventos e as views v_tickets_sla e
-- v_metricas_diarias) pelo novo.
--
-- O que se perde: tudo que está nessas tabelas. Hoje é só dado importado da
-- planilha e ticket de teste, que o scripts/gerar_seed.py recria. Se alguém
-- editou algo real direto no banco, ANOTE ANTES.
--
-- Trava: o script se recusa a rodar sozinho. Pra confirmar, descomente a linha
-- "set app.reset_confirmado" logo abaixo (e só depois de rodar inspecionar.sql).
-- =============================================================================

-- set app.reset_confirmado = 'sim';

do $$
begin
  if current_setting('app.reset_confirmado', true) is distinct from 'sim' then
    raise exception 'Reset bloqueado. Rode inspecionar.sql, confira o que será apagado e descomente a linha "set app.reset_confirmado" no topo deste arquivo.';
  end if;
end $$;

-- Views primeiro (dependem das tabelas)
drop view if exists public.v_fila cascade;
drop view if exists public.v_tickets_presos cascade;
drop view if exists public.v_tickets_sla cascade;
drop view if exists public.v_metricas_diarias cascade;
drop view if exists public.v_uso_diario cascade;

-- Tabelas (cascade leva triggers, índices e as chaves entre elas)
drop table if exists public.eventos cascade;
drop table if exists public.decisoes_ia cascade;
drop table if exists public.reservas_oficiais cascade;
drop table if exists public.tickets cascade;
drop table if exists public.parceiro_nomes cascade;
drop table if exists public.parceiros cascade;
drop table if exists public.prompts cascade;
drop table if exists public.status_ia_regras cascade;
drop table if exists public.transicoes_estado cascade;

-- Funções
drop function if exists public.tocar_atualizado_em() cascade;
drop function if exists public.registrar_eventos_ticket() cascade;
drop function if exists public.ticket_antes_de_gravar() cascade;
drop function if exists public.aplicar_decisao_ia() cascade;
drop function if exists public.ligar_tickets_ao_parceiro() cascade;
drop function if exists public.formatar_sla(integer) cascade;
