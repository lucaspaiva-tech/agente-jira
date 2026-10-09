-- =============================================================================
-- LIMPEZA DOS DADOS DE TESTE: rodar UMA vez, antes da troca, e depois rodar o
-- seed.sql gerado com a exportação final da planilha.
-- =============================================================================
begin;

-- Trava de segurança: se o motor novo já criou tickets reais, a troca já
-- aconteceu e este script não pode mais rodar (apagaria histórico real).
-- "raise exception" aborta a transação inteira: nada abaixo é executado.
-- Durante o desenvolvimento, o n8n grava origem = 'teste', nunca 'motor'.
do $$
begin
  if exists (select 1 from public.tickets where origem = 'motor') then
    raise exception 'A troca já foi feita (existem tickets do motor). Limpeza bloqueada.';
  end if;
end $$;

-- Tickets fictícios e execuções de teste do n8n. Reservas, decisões e eventos
-- deles somem junto (on delete cascade).
delete from public.tickets where origem = 'teste';

-- Eventos de testes feitos em tickets IMPORTADOS (quem testou no lugar errado).
-- O conteúdo desses tickets volta ao original com o seed final.
delete from public.eventos e
using public.tickets t
where e.ticket_id = t.id
  and t.origem = 'importacao'
  and e.autor <> 'importacao';

-- Prompt de teste e prompts criados só pelo desenvolvimento ficam; só o ativo vale.
commit;
