---
name: nova-tela
description: Use quando precisar adicionar uma página nova no app (Streamlit). Passo a passo do arquivo, do registro protegido, da leitura de dados e do tratamento de erro.
---

# Adicionar tela nova

Antes de começar: `.claude/rules/python-streamlit.md` e `.claude/rules/seguranca-hub.md`.
Visual: `DESIGN.md` (o rosa é ação, não decoração).

## 1. Criar `pages/<nome>.py`

Um arquivo por tela, em pt-BR. Padrão mínimo:

```python
"""Fila: lista os tickets do Marketplace com filtros."""

import streamlit as st

from lib.dados import listar_tickets  # função de lib/dados.py, nunca cliente().table() aqui

st.title("📋 Fila")

try:
    tickets = listar_tickets()
except Exception:
    st.error("Não consegui ler os tickets agora. Abra o Diagnóstico pra ver o que falhou.")
    st.stop()
```

- **Dado vem de `lib/dados.py`.** Função de leitura nova entra lá, com teste em `tests/test_dados.py`.
- **Erro em linguagem de negócio.** Diz o que houve e o que fazer. Sem stack trace, sem dado de
  passageiro na mensagem. O `try/except` não é opcional: sem ele, falha de rede vira tela vermelha.
- **Escrita só por `lib/dados.py`** (`atualizar_ticket`, `atualizar_parceiro`). Elas bloqueiam
  sozinhas quando o usuário não é identificado.

## 2. Registrar em `PAGINAS_COM_DADOS`

No `app.py`, dentro da lista `PAGINAS_COM_DADOS` (nunca direto em `paginas`):

```python
PAGINAS_COM_DADOS: list = [
    st.Page("pages/fila.py", title="Fila", icon="📋"),
]
```

É essa lista que a trava de identidade protege. Página registrada fora dela abriria sem login
no link externo. A primeira da lista é a que abre por padrão.

## 3. Depois de gravar, recarregar

```python
if st.button("Enviar ao parceiro"):
    atualizar_ticket(ticket["id"], {"estado": "enviado_parceiro"})
    st.rerun()
```

## 4. Teste

Lógica de filtro, formatação e regra de exibição vai em função pura de `lib/`, com teste
(`Skill(escrever-teste)`). A tela em si é conferida na mão com um ticket `TESTE-*`.

## 5. Antes de dizer "pronto"

`scripts/verificar.sh` verde, a tela aberta com um ticket de teste, e o handoff do `CLAUDE.md`.
