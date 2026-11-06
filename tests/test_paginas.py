import pytest

from sfx.extensions import db
from sfx.models import LinhaProducao
from sfx.services import producao as svc
from sfx.services.periodo import Periodo

from .conftest import marcar


@pytest.fixture()
def producao(usuarios):
    ana, beto = usuarios["analista"], usuarios["analista2"]
    for u, n, campos in [
        (ana, "P-1", ("homologacao", "in_68")),
        (ana, "P-2", ("homologacao",)),
        (beto, "P-3", ("outros",)),
    ]:
        l = LinhaProducao(
            usuario_id=u.id,
            ano=2025,
            mes="Julho",
            semana="07/07 a 11/07",
            numero_processo=n,
            nome_do_segurado=f"Segurado {n}",
            status="tramitado",
        )
        marcar(l, *campos)
        db.session.add(l)
    db.session.commit()


ROTAS_GESTAO = ["/gestao/", "/gestao/setor", "/admin/usuarios", "/plano-acao/"]


def test_analista_nao_acessa_gestao(client, usuarios, entrar):
    entrar(usuarios["analista"])
    for rota in ROTAS_GESTAO + ["/equipe/producao"]:
        assert client.get(rota).status_code == 403, rota


def test_estagiaria_acessa_equipe_mas_nao_gestao(client, usuarios, entrar):
    entrar(usuarios["estagiaria"])
    assert client.get("/equipe/producao").status_code == 200
    assert client.get("/producao").status_code == 403
    for rota in ROTAS_GESTAO:
        assert client.get(rota).status_code == 403, rota


def test_paginas_de_gestao_renderizam(client, usuarios, entrar, producao):
    entrar(usuarios["gerente"])
    ana = usuarios["analista"]
    for rota in [
        "/gestao/?ano=2025&mes=7",
        "/gestao/setor?ano=2025",
        f"/gestao/analista/{ana.id}?ano=2025&mes=7",
        f"/gestao/analista/{ana.id}?visao=ano&ano=2025",
        f"/gestao/analista/{ana.id}?visao=semana&ano=2025&mes=7",
        f"/equipe/producao?analista_id={ana.id}&ano=2025&mes=7",
        "/admin/usuarios",
        f"/pendencias?analista_id={ana.id}",
        "/plano-acao/",
    ]:
        r = client.get(rota)
        assert r.status_code == 200, rota


def test_paginas_do_analista_renderizam(client, usuarios, entrar, producao):
    entrar(usuarios["analista"])
    for rota in [
        "/producao",
        "/producao?ano=2025&mes=7",
        "/producao/estatisticas?ano=2025&mes=7",
        "/producao/estatisticas?visao=ano&ano=2025",
        "/pendencias",
        "/conta/senha",
    ]:
        assert client.get(rota).status_code == 200, rota


def test_estatisticas(app, usuarios, producao):
    ana = usuarios["analista"]
    jul = Periodo(2025, 7)
    assert svc.contagem(usuario_id=ana.id, ano=2025)["homologacao"] == 2
    assert svc.processos_distintos(usuario_id=ana.id, ano=2025) == 2
    assert svc.serie_mensal(2025)["Julho"]["outros"] == 1
    ranking = svc.ranking_equipe(jul)
    assert [r["usuario"].nome for r in ranking] == ["Ana", "Beto"]
    assert ranking[0]["total"] == 3


def test_busca_respeita_dono(client, usuarios, entrar, producao):
    entrar(usuarios["analista"])
    nums = [r["numero_processo"] for r in client.get("/api/busca?q=P-").get_json()["resultados"]]
    assert sorted(nums) == ["P-1", "P-2"]
    client.post("/logout")
    entrar(usuarios["gerente"])
    nums = [r["numero_processo"] for r in client.get("/api/busca?q=P-").get_json()["resultados"]]
    assert sorted(nums) == ["P-1", "P-2", "P-3"]


def test_pendencias_fluxo(client, usuarios, entrar, producao):
    ana = usuarios["analista"]
    entrar(ana)
    pagina = client.get("/pendencias").get_data(as_text=True)
    assert "P-1" in pagina and "P-3" not in pagina

    r = client.post(
        "/pendencias",
        data={
            "acao": "adicionar",
            "mes": "Julho",
            "ano": "2025",
            "semana": "14/07 a 18/07",
            "numero_processo": "MANUAL-1",
            "status": "aguardando",
        },
    )
    assert r.status_code == 302
    nova = LinhaProducao.query.filter_by(numero_processo="MANUAL-1").one()
    assert nova.usuario_id == ana.id

    client.post("/pendencias", data={"acao": "salvar_resolucao", "linha_id": nova.id, "resolucao": "Chefia orientou"})
    client.post("/pendencias", data={"acao": "alternar_removido", "linha_id": nova.id})
    db.session.refresh(nova)
    assert nova.resolucao == "Chefia orientou" and nova.removido

    alheia = LinhaProducao.query.filter_by(numero_processo="P-3").one()
    assert client.post("/pendencias", data={"acao": "alternar_removido", "linha_id": alheia.id}).status_code == 404


def test_gestor_ve_pendencias_mas_nao_altera(client, usuarios, entrar, producao):
    entrar(usuarios["gerente"])
    assert client.post("/pendencias", data={"acao": "adicionar"}).status_code == 403


def test_enderecos_da_v1_redirecionam(client, usuarios, entrar):
    entrar(usuarios["analista"])
    r = client.get("/registrar-producao?mes=Julho")
    assert r.status_code == 301 and "/producao?mes=Julho" in r.headers["Location"]
    assert client.get("/painel-gerente").headers["Location"].endswith("/gestao/")


def test_healthz(client):
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_404_amigavel(client):
    r = client.get("/nao-existe")
    assert r.status_code == 404 and "Página não encontrada" in r.get_data(as_text=True)
