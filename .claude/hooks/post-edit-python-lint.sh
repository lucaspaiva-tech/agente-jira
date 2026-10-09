#!/usr/bin/env bash
# PostToolUse hook: roda o ruff no arquivo .py recém-editado.
#
# Exit 0 = segue. Exit 2 = o stderr volta pro Claude como instrução (único jeito do
# agente ver o problema e corrigir). Ver .claude/hooks/README.md.
#
# Stdin: JSON {"tool_input": {"file_path": "..."}}

set -u

entrada="$(cat)"
arquivo=""
if command -v jq >/dev/null 2>&1; then
  arquivo="$(printf '%s' "$entrada" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi
if [[ -z "$arquivo" ]]; then
  arquivo="$(printf '%s' "$entrada" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
fi

[[ "$arquivo" == *.py ]] || exit 0
[[ -f "$arquivo" ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

# Prefere o ruff do venv do projeto; sem ele instalado, não há o que checar.
if [[ -x .venv/bin/ruff ]]; then
  RUFF=.venv/bin/ruff
elif command -v ruff >/dev/null 2>&1; then
  RUFF=ruff
else
  exit 0
fi

if saida=$("$RUFF" check "$arquivo" 2>&1); then
  exit 0
fi

{
  echo "🔴 ruff encontrou problema em $arquivo:"
  printf '%s\n' "$saida" | head -20
  echo "   Corrige antes de seguir."
} >&2
exit 2
