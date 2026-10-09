from lib.identidade import CABECALHO_EMAIL, usuario_atual


def test_usa_o_cabecalho_do_hub_em_minusculo_e_sem_espaco(hub):
    hub(cabecalhos={"X-Hub-User-Email": " Ana.Silva@Buser.com.br "})
    email, origem = usuario_atual()
    assert email == "ana.silva@buser.com.br"
    assert origem == f"cabeçalho {CABECALHO_EMAIL}"


def test_ignora_cabecalhos_que_o_hub_nao_sobrescreve(hub):
    # Quem acessa consegue mandar esses cabeçalhos na mão: aceitar um deles
    # permitiria se passar por outra pessoa.
    hub(
        cabecalhos={
            "X-Forwarded-Email": "diretor@buser.com.br",
            "X-Auth-Request-Email": "diretor@buser.com.br",
            "X-User-Email": "diretor@buser.com.br",
        }
    )
    assert usuario_atual() == (None, None)


def test_sem_cabecalho_no_hub_nao_identifica_ninguem(hub):
    hub()
    assert usuario_atual() == (None, None)


def test_cabecalho_vazio_ou_so_espaco_nao_conta(hub):
    hub(cabecalhos={"X-Hub-User-Email": "   "})
    assert usuario_atual() == (None, None)


def test_modo_local_usa_o_email_do_secrets(hub):
    hub(segredos={"AMBIENTE": "local", "USUARIO_LOCAL_EMAIL": "Lucas.Paiva@buser.com.br "})
    email, origem = usuario_atual()
    assert email == "lucas.paiva@buser.com.br"
    assert origem == "modo local (secrets.toml)"


def test_modo_local_sem_email_configurado_nao_identifica(hub):
    hub(segredos={"AMBIENTE": "local"})
    assert usuario_atual() == (None, None)


def test_email_local_e_ignorado_fora_do_modo_local(hub):
    # Se USUARIO_LOCAL_EMAIL parar no Hub sem o AMBIENTE=local, não pode valer.
    hub(segredos={"USUARIO_LOCAL_EMAIL": "lucas.paiva@buser.com.br"})
    assert usuario_atual() == (None, None)


def test_cabecalho_real_vence_o_modo_local(hub):
    # AMBIENTE=local vazado pro Hub: quem manda é o cabeçalho, nunca o e-mail fixo.
    hub(
        cabecalhos={"X-Hub-User-Email": "real@buser.com.br"},
        segredos={"AMBIENTE": "local", "USUARIO_LOCAL_EMAIL": "lucas.paiva@buser.com.br"},
    )
    email, _ = usuario_atual()
    assert email == "real@buser.com.br"
