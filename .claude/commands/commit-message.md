---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*)
description: Gera proposta de commit message em pt-BR seguindo Conventional Commits a partir do diff e do contexto da session
---

# /commit-message

Gera **proposta** de commit message a partir do que está staged + contexto do que foi feito nesta session.

> ⚠️ Não comita. `.claude/settings.json` (base do `buser agents`) bloqueia `git commit`/`git push`. Só sugere a mensagem pra o dev copiar/colar.

## Coleta de contexto

Roda em paralelo (mesmo turno):

```bash
git status --short
git diff --staged
git diff
git log -5 --oneline
```

Se **não houver staged** e houver unstaged: avisa o dev pra dar `git add` no que ele quer comitar e roda de novo. Não tenta adivinhar escopo a partir do working tree inteiro.

Se houver staged + unstaged: foca **só no staged**. Menciona em 1 linha que ficou X arquivo unstaged fora da proposta.

## Regras da mensagem

Conventional Commits 1.0.0 (https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>)?: <subject>

<body opcional>

<footer opcional>
```

- **type** obrigatório: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
- **scope** opcional: nome do módulo/pacote/serviço/app tocado (ex: `auth`, `api`, `web`, `cli`, ou o nome do crate/package). Se o diff abrange >1 escopo sem foco claro, omite scope
- **subject**: pt-BR, imperativo, minúsculo, sem ponto final, **máx 72 chars**
- **body**: só se a mudança precisar de "porquê". Bullet points curtos. Máx 3-4 linhas
- **breaking change**: `!` depois do scope + footer `BREAKING CHANGE: <descrição>`

## Tom

- Direto. Sem rodeio. Sem "este commit adiciona…"
- Foca no **porquê** no body, **o quê** no subject
- Se for óbvio pelo diff, pula o body
- **Nunca** adicionar `Co-Authored-By: Claude` (ou qualquer LLM) — ferramenta não é co-autor

## Output

Devolve **só** o bloco da mensagem dentro de fence, pronto pra copiar:

````
```
<type>(<scope>): <subject>

<body se precisar>
```
````

Depois, em 1 linha: "scope inferido de: <arquivos>" pra o dev validar se o escopo bate.

## Anti-patterns a evitar

- ❌ "atualiza arquivos" / "melhorias gerais" / "wip"
- ❌ Subject > 72 chars
- ❌ Listar cada arquivo tocado no body (o `git log -p` já mostra)
- ❌ Body explicando o que o diff já mostra
- ❌ Marketing-speak: "robusto", "elegante", "poderoso"
- ❌ Inglês no subject (a menos que o termo seja intraduzível: "refactor", "lint", "hook" passam; "improve" não)

## Exemplos bons

```
feat(auth): adiciona refresh token com rotação a cada uso

mitiga replay attack se o refresh vazar; cliente precisa reautenticar
após 7 dias de inatividade.
```

```
fix(api): corrige paginação retornando duplicata na borda da página
```

```
refactor(jobs): extrai retry policy pra módulo próprio
```

```
chore: bump tokio 1.40 -> 1.41
```
