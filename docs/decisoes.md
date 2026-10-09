# Decisões

Registro das decisões que moldam o projeto. Pra divergir de uma, cite o item e justifique.

| # | Decisão | Motivo |
|---|---|---|
| 1 | **Página em Streamlit, publicada no Buser Hub.** | O TI confirmou segredos (`st.secrets`), rede (HTTPS 443) e identidade. Next.js exigiria Kubernetes e pedidos à infra sem prazo garantido. |
| 2 | **Template do desafio como esqueleto** (convenções, regras do Claude Code, hooks, CI, tema), sem o código Next.js. | O template é ponto de partida, não exigência. A stack Python/Streamlit já estava validada. |
| 3 | **Identidade só por `X-Hub-User-Email`.** | É o único cabeçalho que o Hub sobrescreve. Aceitar outro permitiria se passar por outra pessoa. |
| 4 | **Sem e-mail no Hub, só o Diagnóstico abre.** | A chave do Supabase ignora o RLS: sem identidade, a leitura também precisa ser bloqueada. |
| 5 | **Um único projeto Supabase** (teste e produção), com `origem = 'teste'` nos dados fictícios. | Dois projetos custariam tempo que não há. Dado de teste fica fora das métricas e é apagado antes da troca. |
| 6 | **Motor no n8n, sem o Job do Databricks.** O n8n consulta o SQL Warehouse e o modelo direto. | Elimina cluster subindo do zero, polling, retry com `run_id` novo e o bug de `SKIPPED`. |
| 7 | **Modelo e prompt mantidos** (Gemini via Databricks). | O prompt foi calibrado nele. Trocar de modelo no meio da medição muda o comportamento e adiciona fornecedor ao custo. |
| 8 | **Parceiros seguem nas planilhas deles** nesta versão. | Portal do parceiro exige login e adoção de dezenas de empresas. Fica pra depois. |
| 9 | **"Tempo de Resposta" continua visível nas planilhas dos parceiros.** | Pressiona a resposta e o time já usa. |
| 10 | **Histórico por trigger**, não pelo app. | Nenhuma ação fica sem registro, e é dali que sai o cálculo de impacto. |
| 11 | **Baseline por escrito e vídeo do antes são portões da troca.** | Depois que o processo muda, o tempo de antes vira estimativa, e estimativa não entra na conta. |
| 12 | **Anexos não são guardados**, só o link do Jira. Vídeo acima de um limite é ignorado com aviso no parecer. | Evita dado pessoal duplicado e custo de armazenamento e de token. |
| 13 | **Repositório privado na organização**, com acesso de edição pra quem avalia e sem dados nem segredos. | Exigência da entrega, com a LGPD preservada. |
| 14 | **O agente de código não comita.** | Quem assina o commit revisa o diff e assume a autoria (política do template). |
| 15 | **Refatoração limpa do desenho**: banco, camadas e regras redesenhados, sem remendar o kit anterior. | O primeiro kit nasceu em dias e acumulou remendos. O prazo pede base simples de manter. |
| 16 | **`parceiro_nomes` em tabela**, não lista numa coluna. | O banco passa a impedir um nome de empresa em dois parceiros. |
| 17 | **Decisões da IA e prompts versionados em tabelas.** | Permite comparar versões, reprocessar com segurança e auditar. |
| 18 | **Transições de estado validadas no banco** (`transicoes_estado` + trigger), com carimbos de tempo no trigger. | n8n e página escrevem nos mesmos tickets: a regra não pode depender de quem lembra. |
| 19 | **Estado `enviando`** entre `pendente` e `enviado_parceiro`. | A página mostrava "enviado" antes de a planilha do parceiro receber a linha. Agora só vira enviado quando o n8n confirma. |
| 20 | **Dado pessoal do passageiro isolado em `reservas_oficiais`.** | Facilita LGPD e mantém a fila sem nome de passageiro. |
| 21 | **Regra compartilhada mora no banco; regra só da página mora em `lib/dominio.py`.** | Evita a mesma regra em dois lugares (o defeito do Apps Script com o prompt). |
| 22 | **Reembolso é sempre multa na carteira do parceiro; só vira custo BX quando o ticket é Alinhado e foi autorizado por liderança (TL ou supervisão).** A IA marca a autorização (prompt v11), a página deixa corrigir antes de confirmar, e o banco decide ao confirmar. | Regra de negócio confirmada pelo Lucas. Substitui a da 001, em que todo Alinhado virava custo BX. |
| 23 | **Motor a cada 5 minutos, até 3 tickets por rodada.** | O n8n antigo rodava a cada 30 minutos com 1 ticket (no máximo 2 por hora). |
