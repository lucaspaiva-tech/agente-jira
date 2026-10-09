# Arquitetura

## Visão geral

```
Jira (fila MKTPL)
   │
   ▼
n8n ──► Databricks SQL Warehouse (dados da reserva, multa)
 │  └─► Gemini via serving endpoint do Databricks (decisão do ticket)
 │
 ├──► Supabase (tickets, parceiros, eventos)  ◄──  página no Buser Hub (Streamlit)
 ├──► planilhas dos parceiros (n8n escreve o ticket e lê a resposta)
 └──► Slack (alertas de falha)
```

Cada peça tem um papel só:

| Peça | Papel |
|---|---|
| **Supabase** | Fonte única da verdade. Guarda o ticket, o parceiro e o histórico de cada ação. |
| **Página (Streamlit)** | Só interface. Lê e grava no Supabase. Não tem regra de negócio nem fala com Jira, Databricks ou planilhas. |
| **n8n** | Toda regra e integração. Reage às mudanças gravadas no banco. |
| **Databricks** | Fonte de dados (reserva, multa) e o modelo de IA. Não há mais Job nem notebook no caminho. |
| **Planilhas dos parceiros** | Continuam como canal de resposta das empresas de ônibus. |

## Workflows do n8n

| Workflow | O que faz | Disparo |
|---|---|---|
| **W1, motor** | Lê a fila do Jira, cria o ticket (`processando`, chave do Jira = idempotência), baixa anexos, consulta a reserva no SQL Warehouse, lê o prompt ativo da tabela `prompts`, chama o modelo, grava `reservas_oficiais` e `decisoes_ia` (incluindo `autorizado_lideranca`). O banco aplica a decisão (pendente, ou decidido se automática). Atualiza o Jira. Retry nativo com limite; falha definitiva grava `falha` e `erro`. | agendado (5 minutos), até 3 tickets por rodada, em sequência |
| **W2, ações** | Reage a `enviando`: escreve a linha na planilha do parceiro, marca `enviado_parceiro` e acende o aviso de contato; se falhar, volta pra `pendente` com `erro`. Reage a reembolso confirmado: busca a multa. | webhook do Supabase |
| **W3, rotinas** | Lê as respostas das planilhas dos parceiros e grava `aprovado` e `motivo_parceiro`; atualiza o "Tempo de Resposta" nelas (texto e cor vêm de `v_fila`); reconsulta `v_multas_pendentes` e desiste quando `prazo_esgotado`; alerta `v_tickets_presos`. | horário |
| **W4, alertas** | Qualquer falha não tratada vai pro Slack. | Error Workflow |

> Estado: W1 a W4 ainda serão construídos. Esta tabela é o desenho aprovado.
> Em desenvolvimento, o n8n grava `origem = 'teste'`. Só o motor em produção grava `'motor'`.

## Dados

- **`parceiros`** e **`parceiro_nomes`**: um nome de empresa aponta pra um parceiro só (garantido pelo banco).
- **`tickets`**: um por ticket do Jira, com estado, viagem, resposta do parceiro, multa e linha do tempo.
- **`reservas_oficiais`**: nome do passageiro e valores. Dado pessoal isolado.
- **`decisoes_ia`**: uma linha por execução da IA, com a versão do prompt. **`prompts`**: versões do
  checklist (uma ativa). **`status_ia_regras`**: o que cada status da IA faz (decisão automática e se admite custo BX com autorização de liderança).
- **`eventos`**: histórico automático por trigger (campo, de, para, autor, horário). Base da auditoria
  e da contagem de uso do impacto.
- **`transicoes_estado`**: as mudanças de estado permitidas.
- **Views**: `v_fila` (sem dado de passageiro, com SLA de 48h), `v_multas_pendentes`,
  `v_tickets_presos`, `v_metricas_diarias`, `v_uso_diario`.

### Quem escreve o quê

| Dado | Dono |
|---|---|
| Decisão da IA, reserva, multa, resposta do parceiro, estados `processando`, `falha` e `enviado_parceiro` | n8n |
| Ações humanas: envio, decisão manual, reembolso, resolver, OBS | página |
| Carimbos de tempo dos estados, histórico, ligação empresa-parceiro, decisão automática | banco (triggers) |

## Segurança

- A página só abre pelo Buser Hub, para o time COMERCIAL - MARKTPLACE.
- A identidade vem do cabeçalho `X-Hub-User-Email`, que o Hub sempre sobrescreve. Sem ele, o app
  mostra "Acesso negado" e só o Diagnóstico abre.
- Toda escrita grava o e-mail de quem agiu. Sem identificação, a escrita é bloqueada.
- Chaves ficam em `st.secrets` (Hub) ou no `secrets.toml` local, fora do Git. A chave do Supabase
  ignora o RLS, então o controle de acesso é do código do app.
- O repositório nunca recebe dado de passageiro nem segredo.
