# Tarefas para o Claude Code (Bloco 4: telas)

Uma tarefa por vez. Cole o "Pedido" no Claude Code, teste com o roteiro de "Teste" e comite quando
estiver "Pronto". O Claude Code **não comita nem pusha**: ele faz `git add` e sugere a mensagem
(`/commit-message`); quem comita é você, depois de ler o `git diff`.

Antes de qualquer tarefa: `scripts/verificar.sh` verde e o Diagnóstico com os três itens verdes.

## Como o app lê e grava (vale pra todas as tarefas)

- **Lê** o ticket da view `v_fila` (fila e detalhe; sem dado de passageiro) e, no detalhe, também
  `reservas_oficiais` (passageiro e valores), `decisoes_ia` e `eventos`; na tela de parceiros,
  `parceiros` e `parceiro_nomes`. Funções de leitura ficam em `lib/dados.py`.
- **Grava** só o que é ação humana, por `lib/dados.py` (`atualizar_ticket` já preenche o autor):
  - enviar ao parceiro: `estado = 'enviando'` (o n8n escreve na planilha e muda pra `enviado_parceiro`);
  - reverter envio: `estado = 'pendente'`;
  - decisão manual: `aprovado`, `motivo_parceiro` e `estado = 'decidido'`;
  - corrigir a autorização de liderança (TL ou supervisão): `autorizado_lideranca`, só antes de
    confirmar o reembolso;
  - confirmar reembolso: `reembolso_confirmado_em` com a hora atual. O banco decide sozinho: Alinhado
    com autorização de liderança vira custo BX; o resto fica pendente de multa e o n8n busca;
  - resolver: `estado = 'resolvido'`; reabrir: `estado = 'decidido'`;
  - OBS e "acionar operador": editam a coluna.
- **Nunca grava** datas de estado (`enviado_parceiro_em`, `decidido_em`, `resolvido_em`): o banco carimba.
- **Quem pode fazer o quê** vem de `lib/dominio.py` (`acoes_disponiveis(ticket)`). A tela não repete a regra.
- Estado inválido é recusado pelo banco; mostre a mensagem em linguagem simples, não o erro cru.

---

## Tarefa 1: Fila

**Pedido:**
> Leia o CLAUDE.md. Crie `telas/fila.py` (título "Fila") e registre na lista `PAGINAS_COM_DADOS` do
> `app.py` (primeira da lista). Lista os tickets da view `v_fila` em tabela: chave Jira, empresa,
> reserva, status da IA, estado, SLA (`sla_texto`, colorido por `situacao_sla` usando
> `dominio.cor_sla`) e recebido em (`dominio.formatar_data_hora`). Filtros no topo: estado
> (múltipla escolha, padrão tudo menos "resolvido"), empresa, status da IA e busca por chave Jira
> ou reserva. Ordenar do mais recente pro mais antigo. Contadores por estado no topo. Ao selecionar
> uma linha, guardar o id do ticket pra página de detalhe. Funções de leitura em `lib/dados.py`,
> com teste. Ticket com `erro` mostra o texto do erro.

**Teste:** aparecem os tickets importados e TESTE-1 a TESTE-12; filtrar "enviado_parceiro" mostra
TESTE-3 (no prazo) e TESTE-4 (estourado); buscar "TST005" acha só o TESTE-5; TESTE-9 mostra o erro.

**Pronto quando:** filtros e busca funcionam juntos e a seleção guarda o id.

---

## Tarefa 2: Detalhe (só leitura)

**Pedido:**
> Crie `telas/detalhe.py` (título "Detalhe", registrada em `PAGINAS_COM_DADOS`), aberta a partir da
> seleção na Fila. Mostrar: viagem, passageiro e valores (de `reservas_oficiais`, com
> `dominio.formatar_real`), decisão da IA em vigor (de `decisoes_ia` via `tickets.decisao_id`:
> status, resumo, parecer, versão do prompt), resposta do parceiro, OBS, situação do reembolso
> (`dominio.situacao_reembolso`), pra onde o reembolso vai (`v_fila.destino_reembolso` com
> `dominio.descricao_destino_reembolso`; nos casos com `pede_autorizacao`, mostrar também se houve
> autorização de liderança) e a multa (`dominio.descricao_multa`, com cor), link pro Jira
> (`JIRA_BASE_URL` + "/browse/" + chave) e a linha do tempo de `eventos`, mais recente primeiro.

**Teste:** TESTE-7 mostra a multa verde (R$ 289,00 igual ao repassado); TESTE-9 (falha) e TESTE-10
(processando) abrem sem erro mesmo quase vazios; TESTE-12 mostra "aguardando registro no banco";
TESTE-8 mostra custo BX autorizado por liderança; TESTE-13 mostra multa do parceiro, sem autorização.

**Pronto quando:** todo ticket abre sem erro.

---

## Tarefa 3: Ações

**Pedido:**
> Na página de detalhe, adicione as ações que `dominio.acoes_disponiveis(ticket)` devolver, cada uma
> como função em `lib/dados.py` que usa `atualizar_ticket` (veja "Como o app lê e grava"): enviar ao
> parceiro, reverter envio (pede confirmação e avisa que a linha já copiada na planilha do parceiro
> não é removida), registrar decisão manual (Sim/Não + motivo), corrigir a autorização de liderança
> (marcar ou desmarcar, mostrando antes pra onde o reembolso vai), confirmar reembolso, resolver,
> reabrir, e editar OBS. Depois de cada ação: mensagem de sucesso e `st.rerun()`. Se o banco recusar
> uma transição, mostrar mensagem simples.

**Teste (só em tickets TESTE):** TESTE-1 enviar → vira `enviando` (o n8n ainda não existe, então
fica assim); TESTE-2 e TESTE-9 não oferecem envio; TESTE-5 confirma reembolso; TESTE-6 não oferece
confirmar; TESTE-13: marcar a autorização muda o destino pra custo BX, confirmar o reembolso fecha
como custo BX e a autorização não pode mais ser mudada; a linha do tempo mostra seu e-mail. Rodar
`seed_teste.sql` restaura tudo.

**Pronto quando:** cada ação grava e aparece na linha do tempo com o seu e-mail.

---

## Tarefa 4: Parceiros

**Pedido:**
> Crie `telas/parceiros.py` (título "Parceiros", registrada em `PAGINAS_COM_DADOS`). Três blocos:
> 1. **Avisos pendentes:** parceiros com `contato_pendente = true`, com o botão de
>    `dominio.link_contato(whatsapp, email, planilha_id)` e "Já enviei" (grava `contato_pendente = false`).
> 2. **Lista:** nome, nomes de empresa (`parceiro_nomes`), WhatsApp, e-mail e link da planilha
>    (`dominio.link_planilha`), com edição de WhatsApp e e-mail.
> 3. **Empresas sem parceiro:** `dominio.empresas_sem_parceiro(empresas dos tickets, nomes cadastrados)`,
>    com a opção de adicionar o nome a um parceiro (insert em `parceiro_nomes`; o banco liga os
>    tickets sozinho). O banco recusa um nome já usado: mostre isso em linguagem simples.

**Teste:** "AO - Ponce Turismo" (TESTE-9) aparece em "Empresas sem parceiro"; adicionar a um
parceiro some da lista e liga o ticket; adicionar um nome já existente é recusado.

**Pronto quando:** avisos, edição e cadastro de nome funcionam.

---

## Tarefa 5: Empacotar pro Hub

**Pedido:**
> Crie `scripts/empacotar_hub.py`, que gera `dist/agente-jira-hub.zip` com `app.py`,
> `requirements.txt`, `telas/`, `lib/` e `.streamlit/config.toml` (o tema, sem segredo), sem
> `__pycache__`. Deve abortar com erro se qualquer `secrets.toml`, `.sql`, `.xlsx` ou `.csv` for
> entrar no ZIP, e listar no fim o que foi incluído. Com teste.

**Teste:** abrir o ZIP e conferir que só tem código.

**Pronto quando:** o ZIP roda com `streamlit run app.py` numa pasta limpa, com segredos de teste.
