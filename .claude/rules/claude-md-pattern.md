---
description: Como escrever CLAUDE.md em módulos
paths: ["**/CLAUDE.md"]
---

# CLAUDE.md Pattern

## Critério ouro

> "Vou ler isso toda vez que mexer neste módulo?"

Se sim → vai pra `<modulo>/CLAUDE.md`.
Se não → documentação normal (README, docs/).

## Limite duro: 200 linhas

| Tamanho | Veredicto |
|---|---|
| < 100 linhas | ok |
| 100–200 linhas | aceitável |
| 200–300 linhas | refatora **logo** |
| > 300 linhas | **bloqueante**. Quebra em `.claude/rules/<tema>.md` com `paths:` |

O hook `post-edit-markdown-validate.sh` avisa em stderr quando CLAUDE.md ultrapassa o limite.

## Estrutura recomendada

```markdown
# CLAUDE.md — <Módulo>

## Propósito
1-2 frases. O que esse módulo faz e em qual fluxo entra.

## Invariantes
Regras de negócio que NUNCA quebram (FSM válida, ACID, autorização obrigatória).

## Patterns
Como estendê-lo sem quebrar (camadas, ports, naming).

## Downlinks
Links pra subdiretórios com CLAUDE.md próprio.
```

## Frontmatter `paths:` em rules

Rule grande não vai dentro do CLAUDE.md. Vai pra `.claude/rules/<tema>.md` com frontmatter:

```markdown
---
description: O que essa rule cobre
paths: ["**/*.py", "**/manage.py"]
---
```

Claude carrega a rule **sob demanda** quando edita arquivo casando o glob. Economiza contexto.

## Quem guarda o quê

- **Raiz** (`./CLAUDE.md`): propósito do repo, comandos de verificação, **inventário** (stack, o
  que cada arquivo de `lib/` faz, downlinks de módulo). Este é o único lugar onde o inventário
  mora.
- **Módulo** (`<modulo>/CLAUDE.md`): só quando o módulo tem invariante ou pattern próprio que a
  raiz não cobre. Módulo sem regra própria não precisa de arquivo.
- **Rules** (`.claude/rules/<tema>.md`): convenção e padrão, com `paths:` casando a extensão.
  **Rule não carrega inventário.** "as oito libs", "o repo ainda não tem commit", "estado atual:
  X" desatualizam no commit seguinte e o agente passa a codar contra um repo que não existe.
  Se precisa citar o que existe hoje, aponte pro `CLAUDE.md` em vez de copiar.

Invariante só entra depois de confirmada no código ou com o time. Seção vazia é melhor que regra
falsa.

## Anti-patterns

- Tutorial passo-a-passo → README, não CLAUDE.md
- Doc de API auto-gerável → docstrings + OpenAPI
- Lista exaustiva de arquivos → `ls` resolve
- Copy-paste do mesmo conteúdo em vários CLAUDE.md → vira regra global
- CLAUDE.md como "wiki" do módulo → wiki é wiki, CLAUDE.md é briefing pra agent
- Invariante inventada pra preencher seção → seção vazia é melhor que regra falsa
