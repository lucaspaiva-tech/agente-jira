---
description: Como caçar contexto do repo antes de codar, sem poluir o main loop
paths: ["**/*.py"]
---

# Context First

A causa raiz de solução ruim quase nunca é modelo fraco, é **contexto faltando**. O dev descreve o
topo do iceberg; o resto (invariante de domínio, onde a lógica mora, decisão passada) está no
repo. Puxa esse contexto antes da primeira linha de código, em vez de perguntar.

A ordem de leitura está no `CLAUDE.md` da raiz, seção "Antes de codar". Esta rule cobre os dois
passos que o índice não detalha, e como fazer isso sem estourar o main loop.

## Os dois passos que o índice não detalha

- **Decisões registradas.** Aqui é `docs/decisoes.md`. Decisão registrada não se contradiz de leve: pra divergir, cita o arquivo e justifica.
- **História do arquivo.** `git log -p -3 -- <arquivo>` mostra *por que* o código está assim e
  quem mexeu por último. Barato e quase sempre esclarecedor.

Inventário (stack, o que cada arquivo de `lib/` faz, onde a tela mora) vive **só** no `CLAUDE.md`.
Esta rule não repete a lista: lista copiada apodrece a cada commit e aí passa a mentir, que é pior
do que não existir.

## Como buscar sem estourar o main context

- Investigação de **>2 queries** (grep/glob/leitura de vários arquivos) → delega pro subagent
  `Explore` (read-only) ou `general-purpose`. Traz de volta a **conclusão**, não o dump.
- Vai criar lógica que "parece comum" (validação, formatação, integração, transformação) → agent
  `service-discovery` **antes** de escrever.
- Tarefa vaga ou multi-arquivo → agent `task-framer` pra enquadrar objetivo, arquivos prováveis,
  premissas e plano antes de tocar código.

## Anti-patterns

- Codar direto da prompt sem abrir o `CLAUDE.md` nem a rule que casa o arquivo.
- Assumir premissa de domínio **em silêncio**. Premissa calada é bug futuro; premissa declarada no
  handoff o dev confirma em 30 segundos.
- Fazer 5 greps no main loop em vez de delegar ao subagent.
- Recriar util que já existe porque não buscou antes.
- Perguntar o que o repo já responde (`git log` e o ADR resolvem).
- Inventar módulo, comando ou caminho que este repo não tem só porque o template sugere.
