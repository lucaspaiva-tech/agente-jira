-- =============================================================================
-- Tickets FICTÍCIOS para desenvolver e testar a página (origem = 'teste').
-- Rodar DEPOIS do seed.sql (precisa dos parceiros) e da migration 002. Cobre todos os estados e as bordas.
-- Rodar de novo = apagar e recriar estes tickets, ou seja, restaurar ao original
-- depois de bagunçar nos testes. Apagados de vez por limpar_teste.sql.
-- Nomes de passageiro e valores são inventados.
-- =============================================================================
begin;

delete from public.tickets where origem = 'teste';   -- o resto cai junto (cascade)

insert into public.prompts (versao, conteudo, ativo, notas)
values ('teste', 'Prompt fictício dos tickets de teste', false, 'Não usar em produção')
on conflict (versao) do nothing;

insert into public.tickets (
  jira_key, origem, estado, reserva, empresa, origem_viagem, destino_viagem, data_viagem, hora_viagem,
  acionar_operador, aprovado, motivo_parceiro, obs, reembolso_confirmado_em,
  multa_valor, multa_status, multa_aguardando_desde, erro,
  recebido_em, enviado_parceiro_em, decidido_em, resolvido_em, atualizado_por, autorizado_lideranca
) values
  -- 1. Pendente, pode ser enviado ao parceiro
  ('TESTE-1', 'teste', 'pendente', 'TST001', 'Expresso Diamante', 'São Paulo - SP', 'Belo Horizonte - MG',
   current_date - 3, '22:00', true, null, null, null, null, null, null, null, null,
   now() - interval '2 hours', null, null, null, 'seed_teste', false),
  -- 2. Pendente, sem acionar operador (envio não deve aparecer). Nome alternativo do parceiro.
  ('TESTE-2', 'teste', 'pendente', 'TST002', 'Gran Express', 'Campinas - SP', 'Rio de Janeiro - RJ',
   current_date - 1, '08:30', false, null, null, null, null, null, null, null, null,
   now() - interval '5 hours', null, null, null, 'seed_teste', false),
  -- 3. Enviado ao parceiro, dentro do SLA (10h)
  ('TESTE-3', 'teste', 'enviado_parceiro', 'TST003', 'Viação Nova', 'Curitiba - PR', 'São Paulo - SP',
   current_date - 2, '23:15', true, null, null, null, null, null, null, null, null,
   now() - interval '1 day', now() - interval '10 hours', null, null, 'seed_teste', false),
  -- 4. Enviado ao parceiro, SLA estourado (60h)
  ('TESTE-4', 'teste', 'enviado_parceiro', 'TST004', 'Brasil Bus', 'Belo Horizonte - MG', 'Vitória - ES',
   current_date - 5, '21:00', true, null, null, null, null, null, null, null, null,
   now() - interval '3 days', now() - interval '60 hours', null, null, 'seed_teste', false),
  -- 5. Parceiro aprovou, reembolso ainda não confirmado
  ('TESTE-5', 'teste', 'decidido', 'TST005', 'Lopesul', 'Porto Alegre - RS', 'Florianópolis - SC',
   current_date - 6, '07:00', true, 'Sim', 'Viagem cancelada por problema mecânico.', null, null, null, null, null, null,
   now() - interval '4 days', now() - interval '3 days', now() - interval '2 days', null, 'seed_teste', false),
  -- 6. Parceiro reprovou
  ('TESTE-6', 'teste', 'decidido', 'TST006', 'Arte Transportes', 'Belo Horizonte - MG', 'Jundiaí - SP',
   current_date - 7, '23:00', true, 'Não', 'Passageiro não compareceu ao embarque.', null, null, null, null, null, null,
   now() - interval '5 days', now() - interval '4 days', now() - interval '3 days', null, 'seed_teste', false),
  -- 7. Decisão automática (Aprovado Viação), reembolso confirmado e multa batendo com o repassado
  ('TESTE-7', 'teste', 'decidido', 'TST007', 'Eucatur', 'Porto Velho - RO', 'Cuiabá - MT',
   current_date - 8, '19:00', false, 'Sim', null, 'Aprovado', now() - interval '5 days', 289.00, 'encontrada', null, null,
   now() - interval '6 days', null, now() - interval '6 days', null, 'seed_teste', false),
  -- 8. Resolvido, Alinhado autorizado por TL: reembolso virou custo BX
  ('TESTE-8', 'teste', 'resolvido', 'TST008', 'Viação Sete', 'Goiânia - GO', 'Brasília - DF',
   current_date - 10, '06:00', false, 'Sim', null, 'Alinhado', now() - interval '8 days', null, 'custo_bx', null, null,
   now() - interval '9 days', null, now() - interval '9 days', now() - interval '8 days', 'seed_teste', true),
  -- 9. Falha técnica e empresa SEM parceiro mapeado (deve aparecer como pendência de cadastro)
  ('TESTE-9', 'teste', 'falha', 'TST009', 'AO - Ponce Turismo', 'Salvador - BA', 'Aracaju - SE',
   current_date - 2, '14:00', null, null, null, null, null, null, null, null, 'O Databricks não respondeu a tempo (3 tentativas).',
   now() - interval '1 hour', null, null, null, 'seed_teste', false),
  -- 10. Ainda processando no n8n
  ('TESTE-10', 'teste', 'processando', 'TST010', null, null, null, null, null,
   null, null, null, null, null, null, null, null, null,
   now() - interval '3 minutes', null, null, null, 'seed_teste', false),
  -- 11. Envio pedido na página, esperando o n8n escrever na planilha do parceiro
  ('TESTE-11', 'teste', 'enviando', 'TST011', 'Expresso Diamante', 'Recife - PE', 'Maceió - AL',
   current_date - 1, '20:00', true, null, null, null, null, null, null, null, null,
   now() - interval '3 hours', null, null, null, 'seed_teste', false),
  -- 12. Reembolso confirmado, multa ainda não registrada no banco (aguardando há 3 dias)
  ('TESTE-12', 'teste', 'decidido', 'TST012', 'Eucatur', 'Cuiabá - MT', 'Porto Velho - RO',
   current_date - 9, '09:00', true, 'Sim', 'Aprovado por falta de retorno em 48 horas.', null, now() - interval '3 days',
   null, 'aguardando', now() - interval '3 days', null,
   now() - interval '8 days', now() - interval '7 days', now() - interval '6 days', null, 'seed_teste', false),
  -- 13. Alinhado SEM autorização de liderança: reembolso ainda não confirmado (vai ser multa do parceiro)
  ('TESTE-13', 'teste', 'decidido', 'TST013', 'Viação Sete', 'Brasília - DF', 'Goiânia - GO',
   current_date - 4, '18:00', false, 'Sim', null, 'Alinhado', null, null, null, null, null,
   now() - interval '3 days', null, now() - interval '3 days', null, 'seed_teste', false);

insert into public.reservas_oficiais
  (ticket_id, nome_passageiro, valor_total_pago, valor_reserva, valor_real, valor_repassado, comissao, taxa_servico)
select t.id, v.nome, v.total, v.reserva, v.real, v.repassado, v.comissao, v.taxa
from (values
  ('TESTE-1',  'Ana Teste',   250.00, 230.00, 200.00, 170.00, 30.00, 20.00),
  ('TESTE-2',  'Bruno Teste', 180.00, 160.00, 140.00, 119.00, 21.00, 20.00),
  ('TESTE-3',  'Carla Teste', 300.00, 280.00, 250.00, 212.50, 37.50, 30.00),
  ('TESTE-4',  'Diego Teste', 220.00, 200.00, 180.00, 144.00, 36.00, 20.00),
  ('TESTE-5',  'Elisa Teste', 150.00, 140.00, 120.00,  96.00, 24.00, 20.00),
  ('TESTE-6',  'Fábio Teste', 177.90, 171.00, 150.00, 120.00, 30.00, 21.00),
  ('TESTE-7',  'Gabi Teste',  400.00, 380.00, 340.00, 289.00, 51.00, 40.00),
  ('TESTE-8',  'Hugo Teste',   90.00,  85.00,  75.00,  60.00, 15.00, 10.00),
  ('TESTE-11', 'Iara Teste',  210.00, 195.00, 170.00, 136.00, 34.00, 25.00),
  ('TESTE-12', 'João Teste',  260.00, 240.00, 210.00, 168.00, 42.00, 30.00),
  ('TESTE-13', 'Lia Teste',   120.00, 110.00,  95.00,  76.00, 19.00, 15.00)
) as v(jira_key, nome, total, reserva, real, repassado, comissao, taxa)
join public.tickets t on t.jira_key = v.jira_key;

insert into public.decisoes_ia (ticket_id, prompt_versao, status_ia, resumo_motivo, parecer, acionar_operador, autorizado_lideranca, criado_por)
select t.id, 'teste', v.status, v.resumo, v.parecer, coalesce(t.acionar_operador, false), t.autorizado_lideranca, 'seed_teste'
from (values
  ('TESTE-1',  'Em Análise', 'Ônibus atrasou 4 horas e a passageira perdeu um compromisso.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-2',  'Falta informação BX', 'Passageiro pede reembolso sem descrever o motivo.', 'Ticket sem descrição do motivo da solicitação.'),
  ('TESTE-3',  'Em Análise', 'Ar-condicionado quebrado durante toda a viagem.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-4',  'Em Análise', 'Ônibus não apareceu no ponto de embarque.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-5',  'Em Análise', 'Viagem cancelada pela empresa sem aviso.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-6',  'Em Análise', 'Passageiro alega que o ônibus partiu antes do horário.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-7',  'Aprovado Viação', 'Motorista informou que o reembolso é com a Buser.', 'Evidência encontrada em print de WhatsApp anexado.'),
  ('TESTE-8',  'Alinhado', 'Ressarcimento autorizado por TL Fulana.', 'Ciente da tratativa já alinhada.'),
  ('TESTE-11', 'Em Análise', 'Passageira não conseguiu embarcar por atraso do ônibus.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-12', 'Em Análise', 'Ônibus quebrou no meio da viagem.', 'Necessita de análise para as devidas tratativas'),
  ('TESTE-13', 'Alinhado', 'Ticket aberto apenas para registro do ressarcimento.', 'Ciente da tratativa já alinhada.')
) as v(jira_key, status, resumo, parecer)
join public.tickets t on t.jira_key = v.jira_key;

commit;
