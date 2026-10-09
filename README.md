# Agente JIRA

Página do time Comercial - Marketplace da Buser para tratar tickets de ressarcimento do Jira
(projeto MKTPL). Substitui as planilhas Central, Resolvidos e Planilhas. Projeto do Desafio de IA
Buser 2026, construído sobre o template do desafio.

- Como funciona: [docs/arquitetura.md](docs/arquitetura.md)
- Por que foi feito assim: [docs/decisoes.md](docs/decisoes.md)
- O que falta construir: [TAREFAS.md](TAREFAS.md)
- Entrega e medição de impacto: [entrega/CHECKLIST.md](entrega/CHECKLIST.md)

## Estrutura

```
app.py                      entrada: menu e trava de identidade
lib/                        configuração, conexão, identidade, acesso ao banco e regras (dominio.py)
pages/                      uma tela por arquivo
supabase/migrations/        schema do banco (001)
supabase/seed/              dados de importação e de teste
supabase/tests/             testes do banco (SQL, em rollback)
supabase/reset.sql          troca o desenho antigo (destrutivo, trancado)
scripts/                    gerar_seed.py, verificar.sh
tests/                      pytest
entrega/                    checklist, página explicativa, roteiro dos vídeos e medicao.xlsx
.claude/                    regras, agents, skills, hooks e permissões do Claude Code
```

## 1. Supabase (uma vez)

1. Criar o projeto na conta da empresa, região **São Paulo**.
2. Guardar a **URL do projeto** e a chave **service_role** (Project Settings > API).
3. No **SQL Editor**, rodar nesta ordem:
   1. `supabase/inspecionar.sql`: só mostra o que existe hoje. Confira o que será apagado.
   2. `supabase/reset.sql`: **apaga o desenho antigo**. Só roda depois de você descomentar a linha de confirmação no topo.
   3. `supabase/migrations/001_schema.sql`
   4. `supabase/migrations/002_autorizacao_lideranca.sql`
   5. `supabase/tests/testes_banco.sql`: precisa terminar sem erro (não grava nada).
   6. `supabase/seed/seed.sql`: parceiros e histórico importados. Gere antes com `python scripts/gerar_seed.py exportacao.xlsx`.
   7. `supabase/seed/seed_teste.sql`: tickets fictícios TESTE-1 a TESTE-13.
   8. `supabase/seed/prompt_v10.sql` e depois `supabase/seed/prompt_v11.sql`: a v10 fica guardada pra comparação, a v11 vira a ativa.

> A chave `service_role` dá acesso total ao banco. Nunca cole em chat, código ou print.

## 2. Máquina (Linux, Python 3.12)

```bash
# Se o venv reclamar de "ensurepip": sudo apt install python3.12-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# editar .streamlit/secrets.toml com a URL e a chave do Supabase

streamlit run app.py
```

Abre em `http://localhost:8501`. A página **Diagnóstico** precisa mostrar três itens verdes.
Toda vez que abrir um terminal novo: `source .venv/bin/activate`.

## 3. Verificar

```bash
scripts/verificar.sh      # ruff + pytest
```

## 4. Configuração no Buser Hub

- **Segredos:** no campo **Segredos** do app, colar:
  ```
  SUPABASE_URL = "https://xxxx.supabase.co"
  SUPABASE_SERVICE_KEY = "..."
  JIRA_BASE_URL = "https://SEU-SITE.atlassian.net"
  ```
  **Não** colocar `AMBIENTE` nem `USUARIO_LOCAL_EMAIL`: com `AMBIENTE=local` no Hub, o app aceitaria
  um e-mail fixo e as ações ficariam no nome errado.
- **Rede:** só HTTPS (porta 443). A API do Supabase funciona; conexão direta no Postgres não.
- **Identidade:** cabeçalho `X-Hub-User-Email`. Vem vazio no link externo `/s/...`.
- **Quem vê:** COMERCIAL - MARKTPLACE.
- Quem vê o app consegue baixar o código: o ZIP só pode ter código, nunca segredos nem dados.

## 5. Troca (checklist)

1. Baseline confirmada pelo gestor por escrito e vídeo do antes gravado.
2. Exportar a planilha atual (abas Central, Resolvidos e Planilhas) em `.xlsx`.
3. `python scripts/gerar_seed.py exportacao.xlsx` e conferir o relatório.
4. No SQL Editor: `supabase/limpar_teste.sql`, depois o `seed.sql` novo (e rode `testes_banco.sql` de novo).
5. Gerar o ZIP (`python scripts/empacotar_hub.py`) e publicar no Hub.
6. Abrir o Diagnóstico **pelo Hub**: três itens verdes, seu e-mail via `X-Hub-User-Email` e sem o
   aviso de modo local.
7. Desativar o workflow antigo e os gatilhos do Apps Script; ativar os novos.

## Trabalhando com o Claude Code

Abra o projeto no VS Code. O Claude Code lê o `CLAUDE.md` sozinho. Siga o `TAREFAS.md` na ordem.
Ele não comita: você lê o `git diff` e comita.
