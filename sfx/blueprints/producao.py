from __future__ import annotations

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..constants import (
    MESES,
    PERFIL_ANALISTA,
)
from ..extensions import db
from ..models import LinhaProducao, Usuario, agora_utc
from ..security import exige, perfis_requeridos
from ..services import itens as itens_svc
from ..services import producao as svc
from ..services.periodo import Periodo, mes_numero, semana_atual

bp = Blueprint("producao", __name__)


def analistas_ativos() -> list[Usuario]:
    return (
        Usuario.query.filter_by(tipo=PERFIL_ANALISTA)
        .filter(or_(Usuario.ativo.is_(True), Usuario.ativo.is_(None)))
        .order_by(Usuario.modalidade, Usuario.nome)
        .all()
    )


def _render_grade(alvo: Usuario, periodo: Periodo, endpoint: str, extra_args: dict | None = None):
    extra_args = extra_args or {}
    if request.method == "POST":
        resultado = svc.salvar_grade(alvo, periodo, request.form, current_user)
        flash(resultado.mensagem, "sucesso")
        return redirect(url_for(endpoint, **periodo.args(), **extra_args))

    grade = svc.carregar_grade(alvo.id, periodo)
    por_semana = svc.contagem_por_semana(alvo.id, periodo)
    total_mes = {c: sum(s[c] for s in por_semana.values()) for c in itens_svc.chaves_atividades()}
    return render_template(
        "producao/grade.html",
        alvo=alvo,
        periodo=periodo,
        grade=grade,
        por_semana=por_semana,
        total_mes=total_mes,
        total_atividades=sum(total_mes.values()),
        processos=svc.processos_distintos(usuario_id=alvo.id, ano=periodo.ano, mes=periodo.nome_mes),
        semana_corrente=semana_atual(periodo.mes, periodo.ano),
        endpoint=endpoint,
        extra_args=extra_args,
        analistas=analistas_ativos() if endpoint == "producao.equipe" else [],
    )


@bp.route("/producao", methods=["GET", "POST"])
@perfis_requeridos(PERFIL_ANALISTA)
def minha_producao():
    return _render_grade(current_user, Periodo.da_requisicao(request.args), "producao.minha_producao")


@bp.route("/equipe/producao", methods=["GET", "POST"])
@exige("edita_equipe")
def equipe():
    periodo = Periodo.da_requisicao(request.args)
    analista_id = request.args.get("analista_id", type=int)
    if not analista_id:
        return render_template("producao/escolher_analista.html", analistas=analistas_ativos(), periodo=periodo)
    alvo = db.session.get(Usuario, analista_id)
    if alvo is None or not alvo.eh_analista:
        abort(404)
    return _render_grade(alvo, periodo, "producao.equipe", {"analista_id": alvo.id})


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------
def render_estatisticas(alvo: Usuario, endpoint: str, extra_args: dict | None = None):
    periodo = Periodo.da_requisicao(request.args)
    visao = request.args.get("visao", "mes")
    if visao not in {"semana", "mes", "ano"}:
        visao = "mes"
    semanas = periodo.semanas
    semana = request.args.get("semana")
    if semana not in semanas:
        semana = semana_atual(periodo.mes, periodo.ano) or (semanas[0] if semanas else None)

    por_semana = svc.contagem_por_semana(alvo.id, periodo)
    serie_ano = svc.serie_mensal(periodo.ano, alvo.id)

    if visao == "semana":
        valores = por_semana.get(semana, dict.fromkeys(itens_svc.chaves_atividades(), 0))
        processos = svc.processos_distintos(usuario_id=alvo.id, ano=periodo.ano, mes=periodo.nome_mes, semana=semana)
        titulo = f"Semana {semana}"
    elif visao == "ano":
        valores = {c: sum(m[c] for m in serie_ano.values()) for c in itens_svc.chaves_atividades()}
        processos = svc.processos_distintos(usuario_id=alvo.id, ano=periodo.ano)
        titulo = f"Ano de {periodo.ano}"
    else:
        valores = {c: sum(s[c] for s in por_semana.values()) for c in itens_svc.chaves_atividades()}
        processos = svc.processos_distintos(usuario_id=alvo.id, ano=periodo.ano, mes=periodo.nome_mes)
        titulo = periodo.rotulo

    grafico = {
        "atividades": [a.rotulo for a in itens_svc.atividades()],
        "valores": [valores[c] for c in itens_svc.chaves_atividades()],
        "semanas": list(por_semana.keys()),
        "por_semana": [sum(v.values()) for v in por_semana.values()],
        "meses": list(MESES),
        "por_mes": [sum(v.values()) for v in serie_ano.values()],
    }
    return render_template(
        "producao/estatisticas.html",
        alvo=alvo,
        periodo=periodo,
        visao=visao,
        semana=semana,
        semanas=semanas,
        valores=valores,
        total=sum(valores.values()),
        processos=processos,
        por_semana=por_semana,
        serie_ano=serie_ano,
        titulo=titulo,
        grafico=grafico,
        endpoint=endpoint,
        extra_args=extra_args or {},
    )


@bp.get("/producao/estatisticas")
@perfis_requeridos(PERFIL_ANALISTA)
def estatisticas():
    return render_estatisticas(current_user, "producao.estatisticas")


# ---------------------------------------------------------------------------
# Pendências
# ---------------------------------------------------------------------------
@bp.route("/pendencias", methods=["GET", "POST"])
@login_required
def pendencias():
    analista_id = request.args.get("analista_id", type=int)
    if current_user.edita_equipe and analista_id and analista_id != current_user.id:
        alvo = db.session.get(Usuario, analista_id)
        if alvo is None or not alvo.eh_analista:
            abort(404)
        pode_editar = current_user.eh_admin  # administrador também altera pendências alheias
    elif current_user.eh_analista and not request.args.get("equipe"):
        alvo = current_user
        pode_editar = True
    elif current_user.edita_equipe:
        alvo = None
        pode_editar = False
    else:
        abort(403)

    if request.method == "POST":
        if not pode_editar:
            abort(403)
        return _acao_pendencia(alvo)

    linhas = []
    if alvo is not None:
        linhas = (
            LinhaProducao.query.filter(LinhaProducao.usuario_id == alvo.id)
            .filter(or_(LinhaProducao.status.in_(itens_svc.chaves_pendentes()), LinhaProducao.removido.is_(True)))
            .order_by(LinhaProducao.data_registro.asc())
            .all()
        )
    grupos = svc.agrupar_pendencias(linhas)
    hoje = Periodo.hoje()
    return render_template(
        "producao/pendencias.html",
        alvo=alvo,
        abertas=grupos.get("abertas", []),
        removidas=grupos.get("removidas", []),
        pode_editar=pode_editar,
        analistas=analistas_ativos() if current_user.edita_equipe else [],
        proprio=alvo is not None and alvo.id == current_user.id,
        status_pendentes=[st for st in itens_svc.situacoes() if st.pendente],
        semanas_ano=svc.semanas_por_mes_do_ano(hoje.ano),
        hoje=hoje,
    )


def _acao_pendencia(alvo: Usuario):
    acao = request.form.get("acao")
    volta = url_for("producao.pendencias", **({"analista_id": alvo.id} if alvo.id != current_user.id else {}))
    if acao == "adicionar":
        mes = request.form.get("mes", "")
        ano = request.form.get("ano", type=int)
        semana = request.form.get("semana", "")
        status = request.form.get("status", "")
        numero = (request.form.get("numero_processo") or "").strip()[:100]
        nome = (request.form.get("nome_do_segurado") or "").strip()[:100]
        if (
            mes not in MESES
            or not ano
            or semana not in Periodo(ano, mes_numero(mes)).semanas
            or status not in itens_svc.chaves_pendentes()
            or not numero
        ):
            flash("Preencha mês, semana, número do processo e status.", "erro")
            return redirect(volta)
        ultimo = (
            db.session.query(db.func.max(LinhaProducao.indice_linha))
            .filter_by(usuario_id=alvo.id, ano=ano, mes=mes, semana=semana)
            .scalar()
        )
        db.session.add(
            LinhaProducao(
                usuario_id=alvo.id,
                ano=ano,
                mes=mes,
                semana=semana,
                indice_linha=(ultimo + 1) if ultimo is not None else 0,
                numero_processo=numero,
                nome_do_segurado=nome,
                status=status,
                data_registro=agora_utc(),
                atualizado_por_id=current_user.id,
            )
        )
        db.session.commit()
        flash("Pendência adicionada. Ela também aparece na grade da semana.", "sucesso")
        return redirect(volta)

    linha = db.session.get(LinhaProducao, request.form.get("linha_id", type=int) or 0)
    if linha is None or linha.usuario_id != alvo.id:
        abort(404)

    if acao == "alternar_removido":
        linha.removido = not linha.removido
        flash("Pendência arquivada." if linha.removido else "Pendência reaberta.", "sucesso")
    elif acao == "salvar_resolucao":
        linha.resolucao = (request.form.get("resolucao") or "").strip()[:4000]
        flash("Resolução salva.", "sucesso")
    else:
        abort(400)
    linha.atualizado_por_id = current_user.id
    db.session.commit()
    return redirect(volta + f"#pendencia-{linha.id}")


# ---------------------------------------------------------------------------
# APIs usadas pelo front-end
# ---------------------------------------------------------------------------
@bp.get("/api/busca")
@login_required
def api_busca():
    termo = request.args.get("q", "")
    if current_user.edita_equipe:
        linhas = svc.buscar(termo)
    elif current_user.eh_analista:
        linhas = svc.buscar(termo, usuario_id=current_user.id)
    else:
        abort(403)

    def link(l: LinhaProducao) -> str:
        args = {"ano": l.ano, "mes": mes_numero(l.mes) if l.mes in MESES else None}
        if l.usuario_id == current_user.id and current_user.eh_analista:
            return url_for("producao.minha_producao", **args) + f"#linha-{l.id}"
        return url_for("producao.equipe", analista_id=l.usuario_id, **args) + f"#linha-{l.id}"

    return jsonify(
        resultados=[
            {
                "id": l.id,
                "numero_processo": l.numero_processo or "",
                "nome_do_segurado": l.nome_do_segurado or "",
                "analista": l.usuario.nome if l.usuario else "",
                "mes": l.mes,
                "ano": l.ano,
                "semana": l.semana,
                "status": st.rotulo if (st := itens_svc.situacao(l.status)) else "",
                "url": link(l),
            }
            for l in linhas
        ]
    )
