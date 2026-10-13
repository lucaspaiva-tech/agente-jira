---
description: Paleta Buser e princípios de UX desta app: cor, hierarquia e contraste. Toda tela nova segue este arquivo
---

# DESIGN.md: cor e UX

Esta app usa **a paleta da Buser, não o design system Andromeda**. É ferramenta interna pra time
de negócio tratar ticket, não superfície de produto. Cor e postura de UX é o que faz a tela
parecer da Buser, e é só isso que vem de lá.

A paleta e os números de contraste vêm do `DESIGN.md` do template do Desafio de IA (Buser
Andromeda 2.1.0 como fonte). Se precisar de um tom que não está aqui, busque na fonte em vez de
inventar.

## Como a paleta entra no Streamlit

Tudo pelo tema nativo do Streamlit (`.streamlit/config.toml`), no visual de painel: conteúdo em
branco, barra lateral em cinza claro com borda, cartões com borda e cantos arredondados.

| Config do tema | Valor | Token de origem |
|---|---|---|
| `primaryColor` | `#e6006a` | `primaria-ativa` |
| `backgroundColor` | `#ffffff` | `cartao` (fundo do conteúdo) |
| `secondaryBackgroundColor` | `#fafafa` | `tela` (campos e cabeçalho de tabela) |
| `sidebar.backgroundColor` | `#fafafa` | `tela` |
| `textColor` | `#454545` | `tinta` (não é preto) |
| `borderColor` | `#e0e0e0` | `fio` |
| `greenColor` / `redColor` / `orangeColor` | `#40b552` / `#dc2e36` / `#e4ad1c` | `sucesso` / `erro` / `aviso` |
| `baseRadius` / `buttonRadius` | `0.75rem` / `0.5rem` | cantos dos cartões e botões |
| `font` | Inter (Google Fonts), com `sans-serif` de reserva | |

`primaryColor` usa o `primaria-ativa` e não o `primaria` (#f11075) de propósito: botão tem texto
branco por cima, e o #f11075 mede 4.14:1 de contraste (não passa AA), enquanto o #e6006a mede
4.59:1 (passa).

Sucesso, erro e aviso saem das cores nativas do Streamlit (`st.success`, `st.error`,
`st.warning`, etiquetas `:red-badge[...]`), já ajustadas pra paleta pelo tema.

**HTML próprio só em blocos isolados:** o cartão em degradê rosa da Visão geral ("Precisa de você")
e o cabeçalho escuro da tabela da Fila (`tinta` com texto branco). Nada que mexa no estilo interno
do Streamlit. CSS global sobrescrevendo o Streamlit quebra a
cada atualização: não use. Precisou de um visual que o tema não cobre? Bloco isolado com
`st.html` e estilo só dentro dele.

## Paleta de referência

| Token | Hex | Onde usa |
|---|---|---|
| `primaria` | `#f11075` | marcação e superfície, nunca texto pequeno |
| `primaria-ativa` | `#e6006a` | ação primária (botão) |
| `primaria-pressionada` | `#b00051` | botão em hover ou pressionado |
| `primaria-lavada` | `#fff7fa` | marcação leve (linha sob o mouse) |
| `tinta` | `#454545` | todo texto de leitura |
| `tinta-suave` | `#757575` | texto secundário, legenda |
| `tela` | `#fafafa` | fundo da página |
| `cartao` | `#ffffff` | interior de bloco |
| `fio` | `#e0e0e0` | borda e divisória de 1px |
| `sucesso` / `erro` / `aviso` | `#40b552` / `#dc2e36` / `#e4ad1c` | só pra dizer o que aconteceu |

## Princípios de UX

**O rosa é ação, não decoração.** `primaria` carrega botão primário, estado ativo e seleção.
Título, ícone ou divisória em rosa "pra ficar bonito" gasta a voltagem e o botão para de chamar
atenção.

**Não existe cor de marca secundária.** O sistema é monocromático-rosa. Não invente azul ou verde
de apoio, nem gradiente. Pra diferenciar dois blocos, use `tela` contra `cartao` e uma borda `fio`.

**Cor semântica só carrega significado.** Verde que não é sucesso, vermelho que não é erro e
amarelo que não é aviso mentem pra quem lê. Erro é vermelho, nunca rosa.

**A hierarquia é texto, não cor.** Informação principal em `tinta`, secundária em `tinta-suave`.
Dois níveis bastam. Se a tela precisa de um terceiro, o problema é a estrutura.

**Contraste é requisito.** Rosa é fundo com texto branco por cima, nunca cor de texto.

**Tabela é instrumento de leitura.** A fila existe pra ser comparada: poucas colunas, as que
decidem a ação (empresa, status, SLA), e o resto no detalhe. Sem sombra nem enfeite.

**Mensagem de erro diz o que fazer.** Em português, em linguagem de negócio, sem stack trace e
sem dado de passageiro.

## Estados do ticket na tela

Use o mesmo significado de cor em toda tela:

| Situação | Cor | Observação |
|---|---|---|
| SLA no prazo / respondido | sucesso | |
| SLA estourado / falha técnica | erro | |
| Aguardando (parceiro, multa) | aviso | |
| Resolvido / sem ação | `tinta-suave` | cinza, não colorido |

## O que não fazer

- Hex solto no código. Se falta um tom, ele vem da fonte e entra aqui.
- Emoji como única informação: sempre acompanha um texto.
- Rosa como enfeite.

## Cores de categoria na Fila

A Fila usa etiquetas coloridas (`:cor-badge[texto]`) pra diferenciar estado e status da IA à
primeira vista, como nas tabelas de painel atuais (referência: shadcn/ui Data Table). É a única
exceção a "cor semântica só carrega significado": aqui a cor é legenda de categoria. A etiqueta
sempre traz o texto (a cor nunca é o único sinal) e a cor é única dentro de cada coluna.

| Estado (grupo) | Cor | Status da IA | Cor |
|---|---|---|---|
| Processando | blue | Aprovado Viação | green |
| Pendente | orange | Alinhado | blue |
| Com o parceiro (inclui enviando) | violet | Em Análise | gray |
| Respondido (decidido) | green | Falta informação BX | violet |
| Falha | red | Reprovado | red |
| Resolvido | gray | Sem decisão / desconhecido | gray |

A fonte da verdade é `lib/dominio.py` (`COR_GRUPO`, `COR_STATUS_IA`).

