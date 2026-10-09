---
description: O que um reviewer vai cobrar do código que você está escrevendo agora
paths: ["**/*.py"]
---

# Code Review Mindset

Esta rule carrega enquanto você **escreve**, então ela traz só o que muda o código na hora. O
procedimento de revisar PR (categorias, roteamento, bloqueantes, formato de comentário) vive em
`.github/skills/code-review/SKILL.md` e em `.github/copilot-instructions.md`, e não é repetido
aqui.

## As quatro perguntas antes de considerar a função pronta

1. **Reuso** — existe lib, util ou componente que já faz isso? Tabela do `CLAUDE.md`, ou o agent
   `service-discovery`. Reutilizar > Evoluir > Criar.
2. **Segurança** — input externo foi validado? injeção (SQL/HTML/shell)? secret ou dado de passageiro em log,
   `print` ou mensagem de erro?
3. **Erro** — o que acontece se falhar? se for lento? se vier `null` ou vazio? Happy path não é
   implementação completa.
4. **Teste** — caminho feliz, borda e erro. O teste ancora no texto que só a implementação certa
   produz (`Skill(escrever-teste)`).

## Broken windows

Viu código ruim ao lado da mudança? **Não "mantenha consistência" com ele.** Conserta, ou anota
pra depois. Copiar o anti-pattern do vizinho é como ele virou padrão.

## Não faça

- `Co-Authored-By: Claude` / `Co-Authored-By: Copilot` em commit. Ferramenta não é co-autor.
