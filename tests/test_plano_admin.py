import re

import openpyxl

from sfx.extensions import db
from sfx.models import PlanoAcaoCiclo, Usuario
from sfx.services import plano_acao as svc

from .conftest import _usuario


def _planilha(caminho):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = svc.ABA_PADRAO
    ws["A2"] = "Histórico"
    ws.append([])
    linhas_2024 = [("Janeiro", None, None, None, "1145"), ("Fevereiro", None, None, None, 746)]
    for i, l in enumerate(linhas_2024):
        for j, v in enumerate(l):
            ws.cell(row=4 + i, column=j + 1, value=v)
    ws.cell(row=16, column=1, value="Dezembro de 2024")
    for j, v in enumerate([57, 194, 108, 108]):
        ws.cell(row=16, column=2 + j, value=v)
    ws.cell(row=17, column=1, value="Janeiro")
    for j, v in enumerate(["57", "225", "139", "203"]):
        ws.cell(row=17, column=2 + j, value=v)
    ws.cell(row=17, column=8, value="19/02/2025")
    ws.cell(row=17, column=9, value="Mês de início")
    ws["A31"] = "Até agosto de 2024 o acompanhamento era outro."
    wb.save(caminho)


def test_variacao_igual_a_planilha():
    assert svc.variacao(1145, 746) == 34.8
    assert svc.variacao(467, 624) == -33.6
    assert svc.variacao(None, 10) is None


def test_importacao_da_planilha(app, tmp_path):
    caminho = tmp_path / "Pasta2.xlsx"
    _planilha(caminho)
    assert svc.importar_planilha(caminho) == [2024, 2025]
    c24 = db.session.get(PlanoAcaoCiclo, 2024)
    assert [m.total for m in c24.meses] == [1145, 746]
    assert "agosto de 2024" in c24.nota
    linhas = svc.serializar_ciclo(db.session.get(PlanoAcaoCiclo, 2025))
    assert linhas[0]["eh_base"] and linhas[0]["total"] == 467
    assert linhas[1]["total"] == 624 and linhas[1]["variacao"] == -33.6
    assert linhas[1]["data_extracao"] == "19/02/2025"
    assert svc.importar_planilha(caminho) == []  # não duplica


def test_criar_ciclo_com_linha_base_e_salvar_via_api(client, app, usuarios, entrar):
    anterior = svc.criar_ciclo(2025)
    anterior.meses[-1].caixa_pa = 100
    db.session.commit()
    novo = svc.criar_ciclo(2026)
    assert novo.meses[0].eh_base and novo.meses[0].caixa_pa == 100
    assert len(novo.meses) == 13

    entrar(usuarios["gerente"])
    jan = novo.meses[1]
    r = client.post(
        "/plano-acao/2026", json={"linhas": [{"id": jan.id, "caixa_pa": "80", "observacoes": "ok"}], "nota": "n"}
    )
    assert r.status_code == 200
    jan_api = r.get_json()["linhas"][1]
    assert jan_api["total"] == 80 and jan_api["variacao"] == 20.0


def test_plano_liberado_por_flag(client, app, entrar):
    lucas = _usuario("Lucas", "analista", "presencial", pode_plano_acao=True)
    entrar(lucas)
    assert client.get("/plano-acao/").status_code == 200


def test_admin_cria_usuario_com_senha_provisoria(client, usuarios, entrar):
    entrar(usuarios["gerente"])
    r = client.post(
        "/admin/usuarios/novo",
        data={"nome": "Nova", "email": "nova@teste.gov.br", "tipo": "analista", "modalidade": "presencial"},
    )
    html = r.get_data(as_text=True)
    senha = re.search(r'class="senha-revelada">([^<]+)<', html).group(1)
    nova = Usuario.query.filter_by(nome="Nova").one()
    assert nova.precisa_trocar_senha and nova.confere_senha(senha)

    # gerente não cria administrador
    client.post("/admin/usuarios/novo", data={"nome": "Root", "email": "root@teste.gov.br", "tipo": "admin"})
    assert Usuario.query.filter_by(nome="Root").first() is None

    # nome duplicado é recusado
    client.post("/admin/usuarios/novo", data={"nome": "nova", "email": "outra@teste.gov.br", "tipo": "estagiaria"})
    assert Usuario.query.filter(Usuario.email == "outra@teste.gov.br").first() is None


def test_admin_desativa_e_redefine(client, usuarios, entrar):
    ana = usuarios["analista"]
    entrar(usuarios["gerente"])
    client.post(f"/admin/usuarios/{ana.id}", data={"acao": "alternar_ativo"})
    db.session.refresh(ana)
    assert not ana.ativo
    client.post(f"/admin/usuarios/{ana.id}", data={"acao": "redefinir_senha"})
    db.session.refresh(ana)
    assert ana.precisa_trocar_senha
    # não desativa a si mesmo
    gil = usuarios["gerente"]
    client.post(f"/admin/usuarios/{gil.id}", data={"acao": "alternar_ativo"})
    db.session.refresh(gil)
    assert gil.ativo
