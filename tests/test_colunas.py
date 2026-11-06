from werkzeug.datastructures import MultiDict

from sfx.extensions import db
from sfx.models import ItemGrade, LinhaProducao, Situacao
from sfx.services import itens as itens_svc
from sfx.services import producao as svc
from sfx.services.periodo import Periodo

from .conftest import _usuario, marcar

JUL = Periodo(2025, 7)
S0 = "01/07 a 04/07"


def _admin():
    return _usuario("Lucas", "analista", "presencial", administrador=True)


def test_so_admin_configura(client, usuarios, entrar):
    entrar(usuarios["gerente"])
    assert client.get("/admin/colunas").status_code == 403
    assert client.post("/admin/colunas/item/novo", data={"grupo": "atividade", "rotulo": "X"}).status_code == 403


def test_admin_cria_coluna_que_vira_producao(client, usuarios, entrar):
    lucas = _admin()
    entrar(lucas)
    assert client.get("/admin/colunas").status_code == 200
    client.post(
        "/admin/colunas/item/novo", data={"grupo": "atividade", "rotulo": "Revisão de cálculo", "curto": "Revisão"}
    )
    item = ItemGrade.query.filter_by(rotulo="Revisão de cálculo").one()
    assert item.chave == "revisao_de_calculo" and item.curto == "Revisão"

    pagina = client.get("/producao?ano=2025&mes=7").get_data(as_text=True)
    assert "Revisão" in pagina

    form = MultiDict([("s0", S0), ("s0_linha", "n1"), ("n1__numero_processo", "P"), (f"n1__{item.chave}", "on")])
    client.post("/producao?ano=2025&mes=7", data=form)
    assert svc.contagem(usuario_id=lucas.id, ano=2025)[item.chave] == 1


def test_ocultar_preserva_historico_e_nao_apaga_ao_salvar(app, usuarios):
    ana = usuarios["analista"]
    linha = LinhaProducao(usuario_id=ana.id, ano=2025, mes="Julho", semana=S0, indice_linha=0, numero_processo="A")
    marcar(linha, "in_68", "dtc_doc")
    db.session.add(linha)
    db.session.commit()

    in68 = ItemGrade.query.filter_by(chave="in_68").one()
    in68.ativo = False
    db.session.commit()
    itens_svc.limpar_cache()
    assert "in_68" not in itens_svc.chaves_atividades()
    assert "in_68" not in svc.contagem(usuario_id=ana.id)

    # salvar a grade (sem a coluna oculta na tela) não apaga a marcação antiga
    svc.salvar_grade(
        ana, JUL, MultiDict([("s0", S0), ("s0_linha", f"e{linha.id}"), (f"e{linha.id}__numero_processo", "A")]), ana
    )
    db.session.refresh(linha)
    assert "in_68" in linha.chaves_marcadas
    assert "dtc_doc" not in linha.chaves_marcadas  # documento ativo desmarcado na tela

    in68.ativo = True
    db.session.commit()
    itens_svc.limpar_cache()
    assert svc.contagem(usuario_id=ana.id)["in_68"] == 1


def test_excluir_so_quando_nunca_usada(client, usuarios, entrar):
    lucas = _admin()
    ana = usuarios["analista"]
    linha = LinhaProducao(usuario_id=ana.id, ano=2025, mes="Julho", semana=S0, numero_processo="A")
    marcar(linha, "outros")
    db.session.add(linha)
    db.session.commit()
    entrar(lucas)
    usada = ItemGrade.query.filter_by(chave="outros").one()
    client.post(f"/admin/colunas/item/{usada.id}", data={"acao": "excluir"})
    assert db.session.get(ItemGrade, usada.id) is not None
    livre = ItemGrade.query.filter_by(chave="siarhes_doc").one()
    client.post(f"/admin/colunas/item/{livre.id}", data={"acao": "excluir"})
    assert db.session.get(ItemGrade, livre.id) is None


def test_renomear_e_reordenar(client, usuarios, entrar):
    entrar(_admin())
    homolog = ItemGrade.query.filter_by(chave="homologacao").one()
    client.post(
        f"/admin/colunas/item/{homolog.id}", data={"acao": "salvar", "rotulo": "Homologação TCE", "curto": "Homol."}
    )
    client.post(f"/admin/colunas/item/{homolog.id}", data={"acao": "descer"})
    itens_svc.limpar_cache()
    chaves = itens_svc.chaves_atividades()
    assert chaves[1] == "homologacao"
    db.session.refresh(homolog)
    assert homolog.rotulo == "Homologação TCE" and homolog.curto == "Homol."


def test_situacoes_editaveis_controlam_pendencias(client, usuarios, entrar):
    lucas = _admin()
    entrar(lucas)
    client.post(
        "/admin/colunas/situacao/nova",
        data={
            "rotulo": "Devolvido ao protocolo",
            "curto": "Devolvido",
            "simbolo": "↩",
            "cor": "#123abc",
            "pendente": "1",
        },
    )
    st = Situacao.query.filter_by(chave="devolvido_ao_protocolo").one()
    assert st.pendente and st.cor == "#123abc"

    form = MultiDict([("s0", S0), ("s0_linha", "n1"), ("n1__numero_processo", "DEV-1"), ("n1__status", st.chave)])
    client.post("/producao?ano=2025&mes=7", data=form)
    assert "DEV-1" in client.get("/pendencias").get_data(as_text=True)

    # deixando de ser pendência, sai da lista
    client.post(
        f"/admin/colunas/situacao/{st.id}",
        data={"acao": "salvar", "rotulo": st.rotulo, "curto": st.curto, "simbolo": st.simbolo, "cor": st.cor},
    )
    assert "DEV-1" not in client.get("/pendencias").get_data(as_text=True)

    # em uso: não exclui
    client.post(f"/admin/colunas/situacao/{st.id}", data={"acao": "excluir"})
    assert db.session.get(Situacao, st.id) is not None


def test_cor_de_texto_legivel():
    assert Situacao(cor="#f3c04a").cor_texto == "#1b2633"
    assert Situacao(cor="#2c6493").cor_texto == "#ffffff"


def test_excluir_linha_remove_marcacoes(app, usuarios):
    ana = usuarios["analista"]
    svc.salvar_grade(
        ana,
        JUL,
        MultiDict(
            [
                ("s0", S0),
                ("s0_linha", "n1"),
                ("n1__numero_processo", "A"),
                ("n1__homologacao", "on"),
                ("n1__dtc_doc", "on"),
            ]
        ),
        ana,
    )
    from sfx.models import linha_item

    assert db.session.query(linha_item).count() == 2
    svc.salvar_grade(ana, JUL, MultiDict([("s0", S0)]), ana)  # semana enviada sem linhas
    assert LinhaProducao.query.count() == 0
    assert db.session.query(linha_item).count() == 0
