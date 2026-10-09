---
description: Regras do banco (Supabase/Postgres): migration, máquina de estados, donos dos dados, auditoria e dados de teste
paths: ["supabase/**", "lib/dados.py", "scripts/gerar_seed.py"]
---

# Banco (Supabase)

Fonte da verdade das colunas: `supabase/migrations/` (001 e as seguintes, na ordem). Resumo e fluxo de estados: `CLAUDE.md`.

- **Mudança de banco sempre vira migration nova** (`002_nome.sql`...). Nunca edite uma migration que
  já rodou. Mostre o SQL e espere aprovação antes de considerar pronto: o banco é o de produção.
- **Cada dado tem um dono.** n8n: decisão da IA, dados da reserva, multa, resposta do parceiro, e as
  transições `processando`, `falha`, `enviado_parceiro`. Página: ações humanas, `enviando`, decisão
  manual, reembolso, resolver. Não grave no que é do outro.
- **O estado só muda por transição permitida** (tabela `transicoes_estado`, validada por trigger).
  Mudar o fluxo é mudar essa tabela, com migration.
- **Nunca grave `enviado_parceiro_em`, `decidido_em` nem `resolvido_em`:** o trigger carimba.
- **Regra compartilhada com o n8n mora no banco:** decisão automática (`status_ia_regras`), ligação
  empresa-parceiro (`parceiro_nomes`), SLA de 48h (`v_fila`), espera da multa (`v_multas_pendentes`).
  Regra só da página mora em `lib/dominio.py`. Não duplique uma na outra.
- **Custo BX:** reembolso é sempre multa do parceiro, exceto status com `custo_bx_se_autorizado`
  (hoje só Alinhado) e `autorizado_lideranca = true`. Quem decide é o trigger, ao confirmar o
  reembolso. Depois de confirmado, a autorização não muda mais (o banco recusa).
- **Tabela `eventos`: só o trigger escreve.**
- **Todo update em `tickets` preenche `atualizado_por`.** Sem isso o evento herda o autor da escrita anterior.
- **Dado pessoal do passageiro só em `reservas_oficiais`.** Nunca em `tickets`, `v_fila` ou log.
- **Tickets `origem = 'teste'` são os únicos pra testar ação.** O n8n em desenvolvimento grava
  `origem = 'teste'`; só o motor em produção grava `'motor'`. `seed_teste.sql` recria os de teste.
- **`limpar_teste.sql` tem trava:** depois do primeiro ticket `origem = 'motor'` ele se recusa a rodar.
- **O seed nunca sobrescreve ticket do motor** nem de teste (`where origem = 'importacao'` no upsert).
- **View nova usa `security_invoker = true`** e nunca expõe dado pessoal.
- **Mudou o banco? Rode `supabase/tests/testes_banco.sql`** (termina em rollback, não suja nada).
