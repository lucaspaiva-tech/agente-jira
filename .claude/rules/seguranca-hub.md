---
description: Regras de identidade, segredos, rede e acesso do app dentro do Buser Hub
paths: ["app.py", "pages/**", "lib/**", ".streamlit/**", "scripts/empacotar_hub.py"]
---

# Segurança no Buser Hub

Confirmado pelo TI do Hub. Se algo aqui divergir do que o Hub fizer de verdade, o Diagnóstico
mostra a causa e esta rule é corrigida.

- **Identidade só pelo cabeçalho `X-Hub-User-Email`** (em `lib/identidade.py`). O Hub sempre
  sobrescreve esse valor, então ninguém se passa por outra pessoa. Nunca aceitar outro
  cabeçalho nem `st.user`: qualquer outro pode ser forjado por quem acessa. Vem vazio no link
  externo `/s/...` e quando o app roda fora do Hub.
- **Telas com dados entram em `PAGINAS_COM_DADOS` no `app.py`**, nunca direto na lista final. É
  essa lista que a trava de identidade protege: no Hub, sem e-mail, só o Diagnóstico abre.
- **Segredos só via `st.secrets`.** No Hub não viram variável de ambiente. Nunca em código, nunca
  no ZIP, nunca no Git.
- **`AMBIENTE=local` nunca vai pro Hub.** Ele aceita um e-mail fixo e faria toda ação ficar no
  nome errado.
- **Rede: só HTTPS (porta 443) pra fora.** Nada de `psycopg`, `SQLAlchemy` ou conexão direta no
  Postgres do Supabase (portas 5432/6543). Só a API (`supabase-py`).
- **A `SERVICE_KEY` ignora o RLS.** O controle do que cada pessoa pode fazer é do código do app,
  com base no e-mail identificado.
- **Quem vê o app consegue baixar o código.** O ZIP só pode ter código: nunca `secrets.toml`,
  `.sql` de seed, `.xlsx` ou `.csv`. O script `scripts/empacotar_hub.py` aborta se algum entrar.
- **Dados de passageiro não vão pra log, `print`, mensagem de erro nem repositório.**
