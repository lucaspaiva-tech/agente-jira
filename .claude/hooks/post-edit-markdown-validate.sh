#!/usr/bin/env bash
# PostToolUse hook: valida edits em arquivos .md.
#
#   - Limite de 200 linhas em CLAUDE.md (doc oficial: arquivo acima disso reduz aderência).
#   - Link relativo apontando pra arquivo que não existe, em qualquer .md.
#
# Stdin: JSON {"tool_name": "Edit|Write|MultiEdit", "tool_input": {"file_path": "..."}}
#
# Exit 0 = silencioso, segue. Exit 2 = o stderr volta pro Claude como instrução, que é
# a ÚNICA forma do agente ver o problema e corrigir. Qualquer outro código não-zero só
# aparece pro dev no terminal e o Claude nunca fica sabendo — era o bug dos dois hooks
# que este arquivo substituiu.

set -u

LIMITE=200

entrada="$(cat)"

arquivo=""
if command -v jq >/dev/null 2>&1; then
  arquivo="$(printf '%s' "$entrada" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi
if [[ -z "$arquivo" ]]; then
  arquivo="$(printf '%s' "$entrada" \
    | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
fi

[[ "$arquivo" == *.md ]] || exit 0
[[ -f "$arquivo" ]] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true
relativo="${arquivo#"$PWD"/}"

problemas=0

# 1. Limite de linhas, só em CLAUDE.md.
if [[ "$(basename "$arquivo")" == "CLAUDE.md" ]]; then
  linhas=$(wc -l < "$arquivo" | tr -d ' ')
  if (( linhas > LIMITE )); then
    {
      echo "🔴 $relativo tem $linhas linhas (limite: $LIMITE)."
      echo "   Move o detalhe pra .claude/rules/<tema>.md com 'paths:' casando o arquivo"
      echo "   que a regra cobre, e deixa aqui só o índice."
    } >&2
    problemas=$((problemas + 1))
  fi
fi

# 2. Link relativo quebrado. Ignora o que está dentro de bloco ou span de código,
#    senão todo exemplo de markdown escrito na doc vira falso positivo.
quebrados=$(
  python3 - "$arquivo" <<'PY'
import os
import re
import sys

caminho = sys.argv[1]
base = os.path.dirname(os.path.abspath(caminho))

with open(caminho, encoding="utf-8") as f:
    conteudo = f.read()

crase = chr(96)
sem_codigo = re.sub(crase * 3 + r".*?" + crase * 3, "", conteudo, flags=re.DOTALL)
sem_codigo = re.sub(rf"{crase}[^{crase}]+{crase}", "", sem_codigo)

for achado in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", sem_codigo):
    rotulo, link = achado.group(1), achado.group(2).strip()
    if link.startswith(("http://", "https://", "mailto:", "#")):
        continue
    destino = link.split("#", 1)[0]
    if not destino:
        continue
    if not os.path.exists(os.path.normpath(os.path.join(base, destino))):
        print(f"{rotulo}|{link}")
PY
)

if [[ -n "$quebrados" ]]; then
  echo "🔴 $relativo tem link apontando pra arquivo que não existe:" >&2
  while IFS='|' read -r rotulo link; do
    [[ -z "$rotulo" ]] && continue
    echo "   [$rotulo]($link)" >&2
  done <<< "$quebrados"
  echo "   Corrige o caminho ou cria o arquivo antes de seguir." >&2
  problemas=$((problemas + 1))
fi

(( problemas > 0 )) && exit 2
exit 0
