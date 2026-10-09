#!/usr/bin/env bash
# PostToolUse hook: scaneia arquivo recém-editado em busca de padrões de
# secret colados sem perceber (AWS key, OpenAI key, GitHub PAT, Slack token,
# JWT, private key header, password=" hardcoded). NÃO bloqueia — sempre
# exit 0. Apenas avisa em stderr pra o dev ver imediatamente após a edição
# e retirar antes do commit.
#
# Defesa em camada com o deny de `.env`/`.pem`/etc no settings.json. Aquele
# impede o agent de LER; este pega o caso "agent (ou dev) colou secret
# dentro de um arquivo qualquer".

set -u

input="$(cat)"
file_path=""
if command -v jq >/dev/null 2>&1; then
  file_path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi
if [[ -z "$file_path" ]]; then
  file_path="$(printf '%s' "$input" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
fi

[[ -n "$file_path" ]] || exit 0
[[ -f "$file_path" ]] || exit 0

# Skipa arquivos onde "secret"/credencial é nome legítimo (testes, doc).
case "$file_path" in
  */tests/*) exit 0 ;;
  */test/*) exit 0 ;;
  *test_*.py) exit 0 ;;
  *_test.go) exit 0 ;;
  *.test.ts|*.test.tsx|*.test.js|*.test.jsx) exit 0 ;;
  *.spec.ts|*.spec.tsx|*.spec.js|*.spec.jsx) exit 0 ;;
  *.md|*.mdx) exit 0 ;;
  */fixtures/*) exit 0 ;;
  */__snapshots__/*) exit 0 ;;
esac

found=""

scan() {
  local label="$1"
  local pattern="$2"
  local hits
  hits="$(grep -nE "$pattern" "$file_path" 2>/dev/null || true)"
  if [[ -n "$hits" ]]; then
    found="$found
[$label]
$(printf '%s\n' "$hits" | head -3 | sed 's/^/    /')"
  fi
}

# AWS access key id (alfanumérico fixo 20 chars começando com AKIA/ASIA/AIDA/AGPA)
scan "AWS access key id"                'A(KIA|SIA|IDA|GPA|NPA|ROA|IPA|RAA|3T)[0-9A-Z]{16}'

# AWS secret access key (40 chars base64-ish atrás de aws_secret/secret_key) — heurístico
scan "AWS secret key (heurístico)"      '(aws_secret|secret_key|aws_secret_access_key)[^=:]*[=:]\s*["'"'"']?[A-Za-z0-9/+=]{40}["'"'"']?'

# OpenAI / Anthropic
scan "OpenAI/Anthropic key"             '(sk-[A-Za-z0-9]{32,}|sk-ant-[A-Za-z0-9_-]{20,})'

# GitHub Personal Access Tokens (classic + fine-grained + others)
scan "GitHub token"                     '(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}'

# Slack tokens
scan "Slack token"                      'xox[baprs]-[A-Za-z0-9-]{10,}'

# Google API key
scan "Google API key"                   'AIza[0-9A-Za-z_\-]{35}'

# Stripe live keys
scan "Stripe live key"                  '(sk|rk)_live_[0-9a-zA-Z]{24,}'

# JWT-shaped (3 segments base64url separated by dots) — sinaliza mas com false positive
scan "JWT-shaped string"                'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'

# Private key header (RSA, EC, DSA, OPENSSH, PGP)
scan "private key header"               '-----BEGIN (RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----'

# password = "..." hardcoded (muito comum)
scan "password literal"                 '(password|passwd|pwd)[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"' \t\r\n]{6,}["'"'"']'

# Connection string com password embarcada (postgres://user:pass@host)
scan "connection string com senha"      '(postgres|postgresql|mysql|mongodb|redis|amqp|rabbitmq):\/\/[^:[:space:]]+:[^@[:space:]]+@'

if [[ -n "$found" ]]; then
  {
    echo "⚠  post-edit-secret-scan: padrão suspeito em $file_path$found"
    echo "    retira antes de comitar. Se for false positive, ignora — esse hook não bloqueia."
  } >&2
fi

exit 0
