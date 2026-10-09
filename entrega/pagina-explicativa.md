# Agente JIRA: tratamento de ressarcimentos do Marketplace

> Modelo da página de entrega. Os trechos em `<...>` são pra preencher com dado real e fonte.
> Não escreva número sem fonte: o que não tem fonte não entra na conta.

## 1. O problema

Quando um passageiro de uma viagem do Marketplace pede ressarcimento, abre-se um ticket no Jira
(projeto MKTPL). Alguém do time precisa cruzar a descrição e os anexos com os dados oficiais da
reserva, decidir o que fazer, avisar a empresa de ônibus parceira, esperar a resposta, conferir a
multa e fechar o caso.

<Quantos tickets por semana, quem faz, por que isso custa caro. Fonte: ...>

## 2. Como era antes

<Descreva o processo passo a passo, como era feito nas planilhas Central, Resolvidos e Planilhas
e no Apps Script. Inclua o tempo por ticket e quem confirmou. Fonte: aba Baseline de
`medicao.xlsx`, confirmação do gestor em <link ou data>.>

Vídeo do antes: <link>

## 3. O que já existia e o que foi construído

O regulamento exclui trabalho feito antes de 30/09. Aqui fica claro o que é novo.

| | Já existia em 30/09 | Construído depois |
|---|---|---|
| Decisão do ticket | <o que já rodava> | <o que mudou> |
| Onde o time trabalha | <planilhas e Apps Script> | página no Buser Hub |
| Dados | <planilhas> | banco Supabase, com histórico de cada ação e de cada decisão da IA |
| Motor | <notebook Databricks> | workflows n8n consultando o SQL Warehouse e o modelo direto |

<Referência da confirmação dos organizadores sobre o escopo: ...>

## 4. O que foi construído

- **Motor (n8n):** lê a fila do Jira, consulta a reserva no Databricks, usa IA multimodal (texto,
  imagem, áudio, vídeo) pra aplicar o checklist de regras e devolve status e parecer. Detalhe em
  [arquitetura.md](../docs/arquitetura.md).
- **Banco (Supabase):** fonte única da verdade. Cada ação vira um evento com autor e horário.
- **Página (Streamlit no Buser Hub):** fila, detalhe do ticket, ações e parceiros. Só o time
  Comercial - Marketplace acessa, identificado pelo e-mail do Hub.
- **Parceiros:** continuam respondendo nas planilhas deles; o n8n escreve e lê.

<Print da fila e do detalhe, sem dado de passageiro.>

Vídeo do depois: <link>

## 5. Impacto

| | Antes | Depois |
|---|---|---|
| Minutos por ticket | <...> | <...> |
| Tickets no período | <...> | <...> |
| Horas no período | <...> | <...> |

**Conta:**

```
(A) horas poupadas x R$100  = <...>
(B) receita gerada          = <0, se não houver>
(C) custo da solução        = <...>
resultado = A + B - C       = <...>
```

Medições: 1ª em <data>, 2ª em <data, 30 dias depois>. Planilha: `medicao.xlsx`.

## 6. Premissas

- <Como o tempo antes foi medido e quem confirmou.>
- <Como o tempo depois foi medido (amostra, tamanho, contando zero pros tickets decididos sozinhos).>
- <O que entrou e o que ficou de fora do custo (C).>

## 7. Fontes

| Número | Fonte |
|---|---|
| Minutos por ticket (antes) | <aba Baseline + mensagem do gestor> |
| Tickets no período | <consulta no Supabase, tabela `tickets`> |
| Uso do app | <view `v_uso_diario`> |
| Custo | <faturas e painéis: Supabase, Databricks, ...> |

## 8. Como rodar

Veja o [README](../README.md) na raiz do repositório.
