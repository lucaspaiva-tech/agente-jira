#!/usr/bin/env bash
# Stop hook: roda a verificação quando o Claude acha que terminou.
# Vermelho volta pro Claude consertar antes de dizer "pronto".
#
# Fica no Stop e não no PostToolUse de propósito: rodar a suíte a cada edição
# trava o fluxo de quem está construindo.
#
# Exit 0 = segue. Exit 2 = o stderr volta pro Claude como instrução.

set -u

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Sem venv ou sem o script ainda, não há o que verificar.
[ -x scripts/verificar.sh ] || exit 0
[ -d .venv ] || exit 0

if saida=$(scripts/verificar.sh 2>&1); then
  exit 0
fi

{
  echo "🔴 scripts/verificar.sh falhou. Conserte antes de reportar pronto."
  echo
  printf '%s\n' "$saida" | tail -40
} >&2

exit 2
