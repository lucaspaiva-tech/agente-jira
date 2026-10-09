-- =============================================================================
-- Rode ANTES do reset: mostra o que existe hoje no banco, pra você conferir
-- o que será apagado. Só lê, não altera nada.
-- =============================================================================

-- 1. Tabelas e views existentes no schema public
select table_name as objeto, table_type as tipo
from information_schema.tables
where table_schema = 'public'
order by table_type, table_name;

-- 2. Quantas linhas em cada tabela do desenho antigo (ignora as que não existem)
select 'parceiros' as tabela, count(*) as linhas from public.parceiros
union all select 'tickets', count(*) from public.tickets
union all select 'eventos', count(*) from public.eventos;

-- 3. De onde vieram os tickets (importação, teste ou algo editado à mão)
select origem, count(*) as tickets
from public.tickets
group by origem
order by origem;

-- 4. Quem mexeu nos tickets (se aparecer um e-mail seu aqui, houve edição manual)
select atualizado_por, count(*) as tickets
from public.tickets
group by atualizado_por
order by tickets desc;
