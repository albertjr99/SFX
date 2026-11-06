import pytest

from sfx.extensions import db
from sfx.models import LinhaProducao, PlanoAcaoCiclo, Usuario
from sfx.services import plano_acao

from .conftest import _usuario


@pytest.fixture()
def lucas(usuarios):
    return _usuario("Lucas", "analista", "presencial", administrador=True, pode_plano_acao=True)


def test_analista_admin_tem_acesso_total(client, usuarios, lucas, entrar):
    r = entrar(lucas)
    assert r.headers["Location"].endswith("/producao")  # continua com a própria grade
    ana = usuarios["analista"]
    for rota in [
        "/producao",
        "/producao/estatisticas",
        "/gestao/",
        "/gestao/setor",
        f"/gestao/analista/{ana.id}",
        f"/equipe/producao?analista_id={ana.id}",
        "/admin/usuarios",
        "/plano-acao/",
        "/pendencias?equipe=1",
        f"/pendencias?analista_id={ana.id}",
    ]:
        assert client.get(rota).status_code == 200, rota
    assert "Analista · Administrador" in client.get("/producao").get_data(as_text=True)


def test_admin_altera_pendencias_de_outro_analista(client, usuarios, lucas, entrar):
    ana = usuarios["analista"]
    l = LinhaProducao(
        usuario_id=ana.id, ano=2025, mes="Julho", semana="07/07 a 11/07", numero_processo="P-9", status="aguardando"
    )
    db.session.add(l)
    db.session.commit()
    entrar(lucas)
    r = client.post(
        f"/pendencias?analista_id={ana.id}",
        data={"acao": "salvar_resolucao", "linha_id": l.id, "resolucao": "feito pelo admin"},
    )
    assert r.status_code == 302 and f"analista_id={ana.id}" in r.headers["Location"]
    db.session.refresh(l)
    assert l.resolucao == "feito pelo admin"


def test_gerente_nao_altera_pendencias_nem_contas_admin(client, usuarios, lucas, entrar):
    entrar(usuarios["gerente"])
    ana = usuarios["analista"]
    assert client.post(f"/pendencias?analista_id={ana.id}", data={"acao": "adicionar"}).status_code == 403
    assert client.post(f"/admin/usuarios/{lucas.id}", data={"acao": "redefinir_senha"}).status_code == 403
    # gerente não consegue se promover a administrador
    gil = usuarios["gerente"]
    client.post(
        f"/admin/usuarios/{gil.id}",
        data={"nome": "Gil", "email": "gil@teste.gov.br", "tipo": "gerente", "administrador": "1"},
    )
    db.session.refresh(gil)
    assert not gil.eh_admin


def test_admin_concede_e_retira_admin_e_exclui_acesso(client, usuarios, lucas, entrar):
    entrar(lucas)
    gil = usuarios["gerente"]
    client.post(
        f"/admin/usuarios/{gil.id}",
        data={"nome": "Gil", "email": "gil@teste.gov.br", "tipo": "gerente", "administrador": "1"},
    )
    db.session.refresh(gil)
    assert gil.eh_admin
    client.post(f"/admin/usuarios/{gil.id}", data={"nome": "Gil", "email": "gil@teste.gov.br", "tipo": "gerente"})
    db.session.refresh(gil)
    assert not gil.eh_admin

    # exclui quem não tem produção
    eva = usuarios["estagiaria"]
    client.post(f"/admin/usuarios/{eva.id}", data={"acao": "excluir"})
    assert db.session.get(Usuario, eva.id) is None

    # não exclui quem tem produção (preserva histórico)
    ana = usuarios["analista"]
    db.session.add(LinhaProducao(usuario_id=ana.id, ano=2025, mes="Julho", semana="07/07 a 11/07", numero_processo="X"))
    db.session.commit()
    client.post(f"/admin/usuarios/{ana.id}", data={"acao": "excluir"})
    assert db.session.get(Usuario, ana.id) is not None


def test_admin_nao_se_tranca_para_fora(client, usuarios, lucas, entrar):
    entrar(lucas)
    client.post(
        f"/admin/usuarios/{lucas.id}",
        data={"nome": "Lucas", "email": "lucas@teste.gov.br", "tipo": "analista", "modalidade": "presencial"},
    )
    db.session.refresh(lucas)
    assert lucas.eh_admin  # não removeu o próprio admin
    client.post(f"/admin/usuarios/{lucas.id}", data={"acao": "excluir"})
    client.post(f"/admin/usuarios/{lucas.id}", data={"acao": "alternar_ativo"})
    db.session.refresh(lucas)
    assert lucas.ativo


def test_gerente_nao_exclui(client, usuarios, entrar):
    entrar(usuarios["gerente"])
    eva = usuarios["estagiaria"]
    assert client.post(f"/admin/usuarios/{eva.id}", data={"acao": "excluir"}).status_code == 403


def test_admin_exclui_ciclo_do_plano(client, usuarios, lucas, entrar):
    plano_acao.criar_ciclo(2030)
    entrar(usuarios["gerente"])
    assert client.post("/plano-acao/2030/excluir").status_code == 403
    client.post("/logout")
    entrar(lucas)
    assert client.post("/plano-acao/2030/excluir").status_code == 302
    assert db.session.get(PlanoAcaoCiclo, 2030) is None


def test_busca_do_admin_alcanca_toda_equipe(client, usuarios, lucas, entrar):
    ana = usuarios["analista"]
    db.session.add(
        LinhaProducao(usuario_id=ana.id, ano=2025, mes="Julho", semana="07/07 a 11/07", numero_processo="Z-1")
    )
    db.session.commit()
    entrar(lucas)
    res = client.get("/api/busca?q=Z-1").get_json()["resultados"]
    assert res and "/equipe/producao" in res[0]["url"]
