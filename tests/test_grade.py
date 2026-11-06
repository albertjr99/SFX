from werkzeug.datastructures import MultiDict

from sfx.extensions import db
from sfx.models import LinhaProducao
from sfx.services import producao as svc
from sfx.services.periodo import Periodo

JUL = Periodo(2025, 7)
S0 = "01/07 a 04/07"
S1 = "07/07 a 11/07"


def form(*semanas):
    """semanas: lista de (indice_semana, rotulo, [(uid, {campos})])."""
    dados = MultiDict()
    for w, rotulo, linhas in semanas:
        dados.add(f"s{w}", rotulo)
        for uid, campos in linhas:
            dados.add(f"s{w}_linha", uid)
            for k, v in campos.items():
                dados.add(f"{uid}__{k}", v)
    return dados


def test_cria_apenas_linhas_com_conteudo(app, usuarios):
    ana = usuarios["analista"]
    r = svc.salvar_grade(
        ana,
        JUL,
        form(
            (
                0,
                S0,
                [
                    ("n1", {"numero_processo": "2025-1", "homologacao": "on", "status": "finalizado"}),
                    ("n2", {}),  # linha em branco
                    ("n3", {"nome_do_segurado": "Maria", "rg_cpf_doc": "on"}),
                ],
            )
        ),
        ana,
    )
    assert r.criadas == 2
    linhas = svc.linhas_do_mes(ana.id, JUL)
    assert [l.indice_linha for l in linhas] == [0, 1]
    assert linhas[0].homologacao and linhas[0].ano == 2025 and linhas[0].mes == "Julho"
    assert linhas[1].rg_cpf_doc and not linhas[1].homologacao
    assert linhas[0].atualizado_por_id == ana.id


def test_atualiza_remove_e_reordena(app, usuarios):
    ana = usuarios["analista"]
    svc.salvar_grade(
        ana,
        JUL,
        form(
            (
                0,
                S0,
                [
                    ("n1", {"numero_processo": "A"}),
                    ("n2", {"numero_processo": "B"}),
                    ("n3", {"numero_processo": "C"}),
                ],
            )
        ),
        ana,
    )
    a, b, c = svc.linhas_do_mes(ana.id, JUL)

    # remove B (não volta no formulário), esvazia C (deve ser apagada), troca a ordem de A
    r = svc.salvar_grade(
        ana,
        JUL,
        form(
            (
                0,
                S0,
                [
                    ("n9", {"numero_processo": "D"}),
                    (f"e{a.id}", {"numero_processo": "A2", "fixacao_civil": "on"}),
                    (f"e{c.id}", {}),
                ],
            )
        ),
        ana,
    )
    assert (r.criadas, r.atualizadas, r.removidas) == (1, 1, 2)
    restantes = svc.linhas_do_mes(ana.id, JUL)
    assert [l.numero_processo for l in restantes] == ["D", "A2"]
    assert restantes[1].fixacao_civil


def test_semanas_nao_enviadas_ficam_intactas(app, usuarios):
    ana = usuarios["analista"]
    svc.salvar_grade(
        ana, JUL, form((0, S0, [("n1", {"numero_processo": "A"})]), (1, S1, [("n2", {"numero_processo": "B"})])), ana
    )
    svc.salvar_grade(ana, JUL, form((1, S1, [])), ana)  # só a semana 1, vazia
    assert [l.numero_processo for l in svc.linhas_do_mes(ana.id, JUL)] == ["A"]


def test_nao_altera_linha_de_outro_analista(app, usuarios):
    ana, beto = usuarios["analista"], usuarios["analista2"]
    svc.salvar_grade(beto, JUL, form((0, S0, [("n1", {"numero_processo": "do Beto"})])), beto)
    alheia = svc.linhas_do_mes(beto.id, JUL)[0]
    svc.salvar_grade(ana, JUL, form((0, S0, [(f"e{alheia.id}", {"numero_processo": "sequestro"})])), ana)
    db.session.refresh(alheia)
    assert alheia.numero_processo == "do Beto" and alheia.usuario_id == beto.id
    assert svc.linhas_do_mes(ana.id, JUL)[0].numero_processo == "sequestro"  # virou linha nova da Ana


def test_ignora_semana_invalida_e_status_desconhecido(app, usuarios):
    ana = usuarios["analista"]
    r = svc.salvar_grade(
        ana,
        JUL,
        form(
            (0, "99/99 a 99/99", [("n1", {"numero_processo": "X"})]),
            (1, S1, [("n2", {"numero_processo": "Y", "status": "hackeado"})]),
        ),
        ana,
    )
    assert r.ignoradas == ["99/99 a 99/99"]
    (linha,) = svc.linhas_do_mes(ana.id, JUL)
    assert linha.numero_processo == "Y" and linha.status == ""


def test_mesmo_mes_em_anos_diferentes_nao_se_misturam(app, usuarios):
    ana = usuarios["analista"]
    jul26 = Periodo(2026, 7)
    svc.salvar_grade(ana, JUL, form((0, S0, [("n1", {"numero_processo": "2025"})])), ana)
    svc.salvar_grade(ana, jul26, form((0, jul26.semanas[0], [("n1", {"numero_processo": "2026"})])), ana)
    assert [l.numero_processo for l in svc.linhas_do_mes(ana.id, JUL)] == ["2025"]
    assert [l.numero_processo for l in svc.linhas_do_mes(ana.id, jul26)] == ["2026"]


def test_grade_completa_ate_15_linhas(app, usuarios):
    ana = usuarios["analista"]
    grade = svc.carregar_grade(ana.id, JUL)
    assert list(grade) == JUL.semanas
    assert all(len(v) == 15 for v in grade.values())


def test_rota_salva_e_exibe(client, usuarios, entrar):
    ana = usuarios["analista"]
    entrar(ana)
    dados = form((0, S0, [("n1", {"numero_processo": "PROC-77", "in_68": "on"})]))
    r = client.post("/producao?ano=2025&mes=7", data=dados)
    assert r.status_code == 302
    pagina = client.get("/producao?ano=2025&mes=7").get_data(as_text=True)
    assert "PROC-77" in pagina and "Julho de 2025" in pagina


def test_equipe_edita_e_registra_autoria(client, usuarios, entrar):
    eva, ana = usuarios["estagiaria"], usuarios["analista"]
    entrar(eva)
    r = client.post(
        f"/equipe/producao?analista_id={ana.id}&ano=2025&mes=7",
        data=form((0, S0, [("n1", {"numero_processo": "lançado pela Eva"})])),
    )
    assert r.status_code == 302
    linha = LinhaProducao.query.one()
    assert linha.usuario_id == ana.id and linha.atualizado_por_id == eva.id


def test_reenviar_sem_mudancas_nao_conta_como_atualizacao(app, usuarios):
    ana = usuarios["analista"]
    linha = LinhaProducao(usuario_id=ana.id, ano=2025, mes="Julho", semana=S0, indice_linha=0, numero_processo="X")
    db.session.add(linha)  # campos antigos com None, como nos registros da v1
    db.session.commit()
    r = svc.salvar_grade(ana, JUL, form((0, S0, [(f"e{linha.id}", {"numero_processo": "X"})])), ana)
    assert (r.criadas, r.atualizadas, r.removidas) == (0, 0, 0)
