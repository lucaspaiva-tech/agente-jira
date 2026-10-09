#!/usr/bin/env bash
# Roda supabase/tests/testes_banco.sql num Postgres e mostra só o resultado.
# Uso: scripts/testar_banco.sh postgresql://usuario@host:5432/banco
# O teste termina em ROLLBACK: não deixa nada gravado.
set -euo pipefail
cd "$(dirname "$0")/.."

[ $# -eq 1 ] || { echo "Uso: $0 <url-do-postgres>"; exit 1; }

psql "$1" -v ON_ERROR_STOP=1 -q -f supabase/migrations/001_schema.sql >/dev/null 2>&1 \
  && echo "(schema aplicado neste banco)" || echo "(schema já existia ou falhou: seguindo com os testes)"
psql "$1" -v ON_ERROR_STOP=1 -f supabase/tests/testes_banco.sql 2>&1 | grep -E "ok:|FALHOU|PASSARAM|ERROR"
