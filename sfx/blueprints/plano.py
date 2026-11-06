from __future__ import annotations

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from ..extensions import db
from ..models import PlanoAcaoCiclo
from ..security import exige
from ..services import plano_acao as svc

bp = Blueprint("plano", __name__, url_prefix="/plano-acao")


@bp.get("/")
@exige("acessa_plano_acao")
def indice():
    ultimo = db.session.query(db.func.max(PlanoAcaoCiclo.ano)).scalar()
    if ultimo is None:
        return render_template("plano/vazio.html")
    ano = request.args.get("ano", type=int)  # compatível com ?ano=2024 antigo
    return redirect(url_for("plano.ciclo", ano=ano or ultimo))


@bp.get("/<int:ano>")
@exige("acessa_plano_acao")
def ciclo(ano: int):
    ciclo = db.session.get(PlanoAcaoCiclo, ano)
    if ciclo is None:
        abort(404)
    anos = [a for (a,) in db.session.query(PlanoAcaoCiclo.ano).order_by(PlanoAcaoCiclo.ano)]
    return render_template(
        "plano/ciclo.html",
        ciclo=ciclo,
        anos=anos,
        linhas=svc.serializar_ciclo(ciclo),
    )


@bp.post("/<int:ano>")
@exige("acessa_plano_acao")
def salvar(ano: int):
    ciclo = db.session.get(PlanoAcaoCiclo, ano)
    if ciclo is None:
        abort(404)
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        abort(400)
    svc.salvar_ciclo(ciclo, dados)
    return jsonify(ok=True, linhas=svc.serializar_ciclo(ciclo))


@bp.post("/<int:ano>/excluir")
@exige("eh_admin")
def excluir(ano: int):
    ciclo = db.session.get(PlanoAcaoCiclo, ano)
    if ciclo is None:
        abort(404)
    db.session.delete(ciclo)
    db.session.commit()
    flash(f"Ciclo {ano} excluído.", "sucesso")
    return redirect(url_for("plano.indice"))


@bp.post("/novo")
@exige("acessa_plano_acao")
def novo():
    ano = request.form.get("ano", type=int)
    if not ano or not 2000 <= ano <= 2100:
        flash("Informe um ano válido.", "erro")
        return redirect(url_for("plano.indice"))
    svc.criar_ciclo(ano)
    flash(f"Ciclo {ano} pronto para preenchimento.", "sucesso")
    return redirect(url_for("plano.ciclo", ano=ano))
