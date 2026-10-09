from lib.config import ambiente, ler_segredo


def test_ler_segredo_prefere_o_st_secrets_a_variavel_de_ambiente(hub):
    hub(segredos={"SUPABASE_URL": "https://do-secrets"}, ambiente_so={"SUPABASE_URL": "https://do-env"})
    assert ler_segredo("SUPABASE_URL") == "https://do-secrets"


def test_ler_segredo_cai_na_variavel_de_ambiente_quando_nao_ha_secrets(hub):
    hub(ambiente_so={"SUPABASE_URL": "https://do-env"})
    assert ler_segredo("SUPABASE_URL") == "https://do-env"


def test_ler_segredo_devolve_none_quando_nao_existe_em_lugar_nenhum(hub):
    hub()
    assert ler_segredo("SUPABASE_URL") is None


def test_ambiente_e_hub_por_padrao(hub):
    hub()
    assert ambiente() == "hub"


def test_ambiente_so_vira_local_com_o_valor_exato(hub):
    hub(segredos={"AMBIENTE": "local"})
    assert ambiente() == "local"
    hub(segredos={"AMBIENTE": "Local "})
    assert ambiente() == "hub"
