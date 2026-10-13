---
description: Padrão pra construir tela e lógica nova neste projeto (Python + Streamlit). Quem pede a mudança é pessoa de negócio
paths: ["app.py", "telas/**", "lib/**", "tests/**"]
---

# Python + Streamlit neste projeto

Quem pede a mudança é pessoa de negócio. Ela não lê código, lê mensagem de erro.

## Não negociável

- **Escrita só por `lib/dados.py`.** Página nenhuma chama `cliente().table(...)` pra gravar.
  Toda escrita em `tickets` preenche `atualizado_por` com o e-mail do usuário: é isso que o
  trigger do banco usa pra montar o histórico. Sem usuário identificado, a escrita é bloqueada.
- **Regra de negócio da página mora em `lib/dominio.py`**, função pura com teste. A tela só chama:
  nada de `if` de regra espalhado em `telas/`.
- **Reusar o que existe.** O `CLAUDE.md` da raiz diz o que cada arquivo de `lib/` faz, e
  `ls lib/` confirma. Antes de escrever função nova pra ler config, conectar, identificar usuário
  ou gravar, leia o que já existe.
- **O app só fala com o Supabase.** Jira, Databricks, planilhas dos parceiros e Slack são do n8n.
  Se a tela precisa de algo desses, ela grava uma intenção no banco e o n8n reage.
- **Nenhum segredo novo sem avisar.** Hoje são três no Hub (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
  `JIRA_BASE_URL`) e dois só locais (`AMBIENTE`, `USUARIO_LOCAL_EMAIL`). Precisou de outro, isso é
  mudança de setup: diz no handoff, não inventa em silêncio.
- **pt-BR em tudo que é nosso.** Nome de arquivo, função, variável, comentário, mensagem de erro e
  texto de tela. Inglês só no que não é nosso.
- **Mensagem de erro diz o que fazer.** "Erro 403" não serve. "O Supabase recusou a chave,
  confira SUPABASE_SERVICE_KEY" serve. Sem stack trace na tela e sem dado de passageiro.

## Tela nova

Copia o padrão de `telas/diagnostico.py`: um arquivo por tela em `telas/`, título com `st.title`,
dados lidos por funções de `lib/dados.py`, erro mostrado com `st.error` em linguagem simples.
Registra a página na lista `PAGINAS_COM_DADOS` do `app.py`. Depois de gravar algo, `st.rerun()`.
Passo a passo: `Skill(nova-tela)`.

## TDD em `lib/` e nas telas

Teste vem antes do código. Ciclo: escreve o teste do comportamento que falta, RODA e vê vermelho
pelo motivo certo, escreve o mínimo pra ficar verde, roda de novo. Como fazer direito, com
exemplo real deste repo: `Skill(escrever-teste)`.

## Antes de dizer "pronto"

`scripts/verificar.sh` verde. Se a mudança grava no banco, rodar o caminho real uma vez contra
tickets `TESTE-*` e dizer no handoff que rodou.
