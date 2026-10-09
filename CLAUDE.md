---
description: Porta de entrada do projeto pra AI coding agents (Claude Code, Copilot, Cursor) atuando neste repo
---

# CLAUDE.md: agente-jira

Página interna (Streamlit) do time Comercial - Marketplace da Buser pra tratar tickets de
ressarcimento do Jira (projeto MKTPL). Substitui as planilhas Central, Resolvidos e Planilhas e o
Apps Script `Central.gs`. Inscrição no Desafio de IA Buser 2026: o impacto é medido em horas
poupadas (R$100/h) menos o custo da solução. Quem pede é pessoa de negócio, não engenheira:
responde em português, direto, sem travessão.

## Mentalidade

- **Olha antes de agir.** Varre o que existe antes de escrever: `lib/`, `supabase/migrations/`,
  `docs/decisoes.md`. **Reutilizar > Evoluir > Criar.** Vai criar algo? Roda o agent `service-discovery`.
- **TDD sempre.** Escreve o teste, RODA e vê vermelho pelo motivo certo, implementa o mínimo, vê
  verde. Como fazer: `Skill(escrever-teste)`.
- **Simplicidade primeiro.** Sem abstração antes da Regra do Três. Apagar código > escrever código.
- **Tarefa subespecificada?** Escolhe o caminho mais provável, declara no máximo 2-3 premissas
  ("assumindo X porque Y") e segue. Só pergunta antes se a premissa errada joga o trabalho fora.
- **Aprende com correção.** Foi corrigido? Internaliza o padrão pra não repetir.

## Git policy

- **Agent não comita, agent não pusha.** `git commit`, `push`, `reset --hard` e `rebase` estão no
  deny do `.claude/settings.json`. Agent faz `status`, `diff`, `log`, `add` e sugere a mensagem
  (`/commit-message`). Quem comita é o dev, depois de revisar o diff.
- **Nunca** `Co-Authored-By: Claude` (ou qualquer LLM) em commit.

## Secrets policy

- **Agent não lê credencial.** O deny cobre `.streamlit/secrets.toml`, `.env*`, chaves (`*.pem`,
  `*.key`), `.ssh/` e o `supabase/seed/seed.sql` (nome de passageiro). Pra saber os nomes dos
  segredos, leia `.streamlit/secrets.toml.example`. Se precisa de um valor, pergunte pelo nome e
  uso, nunca peça o conteúdo.
- Segredo nunca entra em código, ZIP, Git, log ou mensagem de erro.

## Stack

| Camada | Tech |
|---|---|
| Linguagem | Python 3.12, nomes em pt-BR |
| App | Streamlit (publicado no Buser Hub, só pro time COMERCIAL - MARKTPLACE) |
| Banco | Supabase (Postgres), acessado só pela API (`supabase-py`) |
| Orquestração | n8n: Jira, Databricks (SQL Warehouse + Gemini), planilhas dos parceiros, Slack |
| Teste e lint | pytest e ruff |

## Arquitetura

```
Jira ──► n8n ──► Databricks (SQL Warehouse + Gemini)    decide o ticket
          │
          ├──► Supabase (fonte única da verdade) ◄── este app (lê e grava)
          ├──► planilhas dos parceiros (n8n escreve o ticket, lê a resposta)
          └──► Slack (alertas de falha)
```

**Regra que não se quebra: o app só fala com o Supabase.** Jira, Databricks, planilhas dos
parceiros e Slack são do n8n. Se a tela precisa de algo disso, ela grava a intenção no banco e o
n8n reage.

| Arquivo | O que faz |
|---|---|
| `app.py` | entrada: menu (`st.navigation`) e trava de identidade. Tela nova entra em `PAGINAS_COM_DADOS` |
| `lib/config.py` | `ler_segredo(nome)` (`st.secrets`, depois variável de ambiente) e `ambiente()` (`local` ou `hub`) |
| `lib/supabase_client.py` | `cliente()`: único jeito de conectar, com cache |
| `lib/identidade.py` | `usuario_atual()`: e-mail de quem usa, só pelo cabeçalho `X-Hub-User-Email` |
| `lib/dados.py` | TODA leitura e escrita no banco: `contar`, `atualizar_ticket`, `atualizar_parceiro` e as de leitura das telas |
| `lib/dominio.py` | regras só da página, funções puras: aprovação, reembolso, ações permitidas, multa, formatação, contato |
| `pages/diagnostico.py` | confere segredos, conexão e identidade. Única página sem trava |
| `scripts/gerar_seed.py` | gera o SQL de importação a partir da exportação `.xlsx` da planilha |
| `supabase/migrations/` | schema do banco (fonte da verdade das colunas) |
| `supabase/tests/` | `testes_banco.sql`: testes do banco, em rollback |
| `entrega/` | itens do checklist do desafio (página, vídeos, medição) |
| `docs/` | `decisoes.md` e `arquitetura.md` |

## Banco (resumo; detalhe em `.claude/rules/banco-supabase.md`)

Cada dado tem um dono: o **n8n** escreve a decisão da IA, a reserva, a multa e a resposta do parceiro;
a **página** escreve as ações humanas. Regra que os dois compartilham mora no banco.

- **`parceiros`** e **`parceiro_nomes`**: um nome de empresa aponta pra um parceiro só (o banco garante).
- **`tickets`**: um por ticket do Jira (`jira_key` única). `origem` é `motor`, `importacao` ou `teste`.
- **`reservas_oficiais`**: passageiro e valores (dado pessoal isolado). **`decisoes_ia`**: uma linha por
  execução da IA. **`prompts`** e **`status_ia_regras`**: versões do checklist e o que cada status faz.
- **`eventos`**: histórico por trigger. Ninguém escreve aqui.
- **Views**: `v_fila` (sem dado de passageiro, com SLA), `v_multas_pendentes`, `v_tickets_presos`,
  `v_metricas_diarias`, `v_uso_diario`.

Estados: `processando` e `falha` (n8n), `pendente`, `enviando` (página pediu, n8n executa),
`enviado_parceiro`, `decidido`, `resolvido`. Só mudam por transição da tabela `transicoes_estado`:

| De | Para | Quem | Condição |
|---|---|---|---|
| processando | pendente / decidido / falha | n8n | decisão da IA (automática vai pra decidido) ou erro |
| falha | processando | n8n | reprocessamento |
| pendente | enviando | página | `acionar_operador` e `parceiro_id` preenchidos |
| enviando | enviado_parceiro / pendente | n8n | linha escrita na planilha ou erro (coluna `erro`) |
| enviado_parceiro | pendente | página | reverter envio |
| pendente / enviado_parceiro | decidido | página ou n8n | decisão manual ou resposta do parceiro |
| decidido | resolvido | página | arquivar |
| resolvido | decidido | página | reabrir |

`aprovado` é texto livre; a regra de aprovado ou reprovado está em `dominio.classificar_aprovacao`.

**Reembolso é sempre multa na carteira do parceiro.** Só vira custo BX quando o ticket é Alinhado
e foi autorizado por liderança (TL ou supervisão): a IA marca `autorizado_lideranca`, a página
deixa corrigir antes de confirmar o reembolso, e o banco decide ao confirmar.

## Comandos

```bash
source .venv/bin/activate        # toda vez que abrir um terminal novo
streamlit run app.py             # sobe em http://localhost:8501
scripts/verificar.sh             # ruff + pytest: é o que define "done"
scripts/testar_banco.sh <url>    # testes do banco (SQL, termina em rollback)
```

CI (`.github/workflows/verificar.yml`) roda a mesma verificação a cada push e PR.

## Workflow

1. **Plan First.** Multi-arquivo ou 3+ passos: enquadra antes (agent `task-framer`). Se desviar, para e re-planeja.
2. **Investigação >2 consultas** vai pra subagent, não pro main loop.
3. **Self-verify.** `scripts/verificar.sh` verde. Se grava no banco, roda o caminho real num ticket `TESTE-*`.
4. **Mudança de banco** vira migration nova, mostrada pro dev aprovar antes, e roda `supabase/tests/testes_banco.sql`. O banco é o de produção.

## Done = handoff revisável

Antes de dizer "pronto", entregue sempre: **O que mudou** (1 frase), **Premissas que assumi**
(ou "nenhuma"), **Verifiquei** (comando real + resultado), **NÃO cobri / risco** e **Revise
primeiro** (`arquivo:linha`). Handoff vazio ou genérico é red flag.

## Regras carregadas sob demanda

Em `.claude/rules/`, com `paths:`, só carregam quando o arquivo relevante é tocado:
`python-streamlit.md`, `seguranca-hub.md`, `banco-supabase.md`, `context-first.md`,
`code-review-mindset.md`, `claude-md-pattern.md`.

## Agents, skills, comandos e hooks

- **Agents** (`.claude/agents/`): `task-framer`, `service-discovery`, `test-gap`, `secret-scanner`, `pr-description`.
- **Skills**: `escrever-teste`, `nova-tela`. **Comandos**: `/check`, `/commit-message`.
- **Hooks** (`.claude/settings.json`): a cada edição valida markdown, varre secret e roda o ruff;
  ao terminar, roda `scripts/verificar.sh`. Hook vermelho: conserta antes de seguir.

## Modo professor

O dev está aprendendo os fundamentos. Ao usar um conceito pela primeira vez nesta base
(ex.: `st.session_state`, o filtro `.in_()` do supabase-py), explique em UMA linha o que faz e
por que foi escolhido. Não repita conceito já usado. Se pedirem "desliga o professor", pare.

## Limite

Este arquivo tem **limite de 200 linhas**. Passou? Move o detalhe pra `.claude/rules/<tema>.md`.
