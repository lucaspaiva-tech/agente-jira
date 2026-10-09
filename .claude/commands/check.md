---
allowed-tools: Bash(scripts/verificar.sh:*), Bash(.venv/bin/ruff:*), Bash(.venv/bin/pytest:*)
description: Roda lint e testes e reporta o que quebrou
---

# /check

Roda `scripts/verificar.sh` (ruff + pytest).

Verde: diz "verde" e o número de testes que passaram.

Vermelho: para na primeira falha, mostra o erro, aponta `arquivo:linha` e propõe a correção.
Não reporta "done" com isso vermelho.
