#!/usr/bin/env bash
# Verificação do projeto: lint + testes. É o que define "pronto".
# Usa o venv do projeto quando existe (máquina do dev) e o python do sistema no CI.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python; fi

echo "== ruff"
"$PY" -m ruff check .
echo "== pytest"
"$PY" -m pytest -q
