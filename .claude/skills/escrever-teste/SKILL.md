---
name: escrever-teste
description: Use antes de escrever qualquer teste neste projeto, ou depois de escrever um, pra confirmar que ele presta. Ensina o ciclo TDD e como não escrever um teste que passa com qualquer implementação.
---

# Escrever um teste que presta

Teste que passa com qualquer implementação não vale nada: dá confiança falsa. O ciclo abaixo existe
pra garantir que o teste, de fato, testa alguma coisa.

## O ciclo

1. Escreve o teste do comportamento que **falta**.
2. RODA (`.venv/bin/pytest -q tests/test_x.py`) e vê ele falhar. Confirma que falhou pelo
   **motivo certo**: a asserção que você escreveu, não um erro de import ou de digitação.
3. Escreve o mínimo de código pra passar.
4. Roda de novo e vê verde.
5. **Quebra o código de propósito** e roda outra vez. Se continuar verde, o teste não testa nada.

Pular o passo 2 é a diferença entre TDD e teste escrito depois, que não prova nada.

## Como o `hub` simula o Hub

`tests/conftest.py` tem a fixture `hub`, que troca o Streamlit por um falso: define os segredos,
as variáveis de ambiente e os cabeçalhos que o Hub mandaria. Teste de identidade, de segredo e de
escrita usa ela, sem abrir o app.

```python
def test_sem_cabecalho_no_hub_nao_identifica_ninguem(hub):
    hub()
    assert usuario_atual() == (None, None)
```

## Caso real 1: ancorar no que só o comportamento certo produz

Em `lib/identidade.py`, só o cabeçalho `X-Hub-User-Email` vale. O teste que protege isso manda
**três outros cabeçalhos com e-mail** e exige `(None, None)`:

```python
hub(cabecalhos={"X-Forwarded-Email": "diretor@buser.com.br",
                "X-Auth-Request-Email": "diretor@buser.com.br"})
assert usuario_atual() == (None, None)
```

Se alguém voltar a aceitar um deles, esse teste fica vermelho. Teste que só conferisse o caso
feliz (cabeçalho certo devolve o e-mail) continuaria verde com a falha de segurança.

## Caso real 2: a ação bloqueada não pode encostar no banco

Em `tests/test_dados.py`, o cliente falso guarda cada chamada. O teste da escrita sem usuário
confere que a lista de chamadas ficou **vazia**, não só que a exceção apareceu. Exceção sem
checar o efeito deixa passar uma função que lança o erro depois de já ter gravado.

## Caso real 3: a trava do `app.py`

`tests/test_app_trava.py` copia o projeto, registra uma página falsa com o texto
`DADOS DE PASSAGEIRO` em `PAGINAS_COM_DADOS` e roda o app com `AppTest`. O teste procura esse
texto na tela: com e-mail ele aparece, sem e-mail não pode aparecer. Ancora no texto da página de
dados, que só existe se a trava falhou.

## Checklist antes de dar o teste como pronto

- [ ] Rodei e vi vermelho antes de implementar.
- [ ] A asserção usa valor ou texto que só o ramo certo produz.
- [ ] Cobre o caminho feliz, uma borda (vazio, `None`) e o erro.
- [ ] Quebrei o código de propósito e o teste ficou vermelho.
- [ ] Nenhum dado real de passageiro no teste: nomes e e-mails são inventados.
