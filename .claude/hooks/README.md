# Hooks

Scripts disparados pelo Claude Code via `.claude/settings.json` (chaves `PreToolUse`, `PostToolUse`, `Stop`).

## Padrão

- Bash (`#!/usr/bin/env bash`), executável (`chmod 755`).
- Recebem via stdin JSON `{ "tool_input": { ... }, "tool_response": ... }`.
- Mantenha rápido (<500ms). Hook lento atrasa todo turn.

## Exit code: o detalhe que faz o hook existir ou não

| Exit | O que acontece |
|---|---|
| `0` | segue em silêncio. Stdout só aparece pro dev em transcript mode |
| `2` | **o stderr volta pro Claude como instrução.** É a única forma do agente ver o problema e corrigir |
| outro não-zero | erro mostrado pro dev no terminal. **O Claude nunca fica sabendo** |

Hook que quer que o agente conserte algo sai com **2**. Este repo já teve dois hooks de markdown saindo com 0 e 1: os avisos apareciam no terminal, o Claude não via nenhum, e nada era corrigido.

Hook que só informa o dev (o scan de secret, por exemplo) sai com 0 de propósito: falso positivo de regex não pode travar o agente.

## Hooks deste repo

| Hook | Trigger | O que faz | Exit |
|---|---|---|---|
| `post-edit-markdown-validate.sh` | PostToolUse em `.md` | CLAUDE.md acima de 200 linhas, link relativo apontando pra arquivo inexistente (ignora exemplo dentro de code fence) | 2 no achado |
| `post-edit-secret-scan.sh` | PostToolUse em qualquer arquivo | Grep contra padrão de secret (AWS/OpenAI/GitHub/Slack/JWT/private key/`password=`) e connection string com senha | 0 sempre |
| `post-edit-python-lint.sh` | PostToolUse em `.py` | Roda `ruff check` no arquivo editado | 2 no achado |
| `stop-verify.sh` | Stop | Roda `scripts/verificar.sh` (ruff + pytest). Vermelho volta pro Claude antes dele dizer "pronto" | 2 no vermelho |
