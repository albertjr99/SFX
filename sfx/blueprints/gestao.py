from __future__ import annotations

from flask import Blueprint, abort, render_template, request

from ..constants import LINHAS_PADRAO_POR_SEMANA, MESES
from ..extensions import db
from ..models import Usuario
from ..security import exige
from ..services import itens as itens_svc
from ..services import producao as svc
from ..services.periodo import Periodo
from .producao import render_estatisticas

bp = Blueprint("gestao", __name__, url_prefix="/gestao")


@bp.get("/")
@exige("eh_gestor")
def painel():
    periodo = Periodo.da_requisicao(request.args)
    ranking = svc.ranking_equipe(periodo)
    total_mes = {c: sum(r["valores"][c] for r in ranking) for c in itens_svc.chaves_atividades()}
    semanas = len(periodo.semanas)
    referencia = semanas * LINHAS_PADRAO_POR_SEMANA  # 15 processos/semana, como na grade
    return render_template(
        "gestao/painel.html",
        periodo=periodo,
        ranking=ranking,
        total_mes=total_mes,
        total=sum(total_mes.values()),
        processos=svc.processos_distintos(ano=periodo.ano, mes=periodo.nome_mes),
        referencia=referencia,
        maior=max((r["total"] for r in ranking), default=0),
    )


@bp.get("/analista/<int:analista_id>")
@exige("eh_gestor")
def analista(analista_id: int):
    alvo = db.session.get(Usuario, analista_id)
    if alvo is None or not alvo.eh_analista:
        abort(404)
    return render_estatisticas(alvo, "gestao.analista", {"analista_id": alvo.id})


@bp.get("/setor")
@exige("eh_gestor")
def setor():
    periodo = Periodo.da_requisicao(request.args)
    serie = svc.serie_mensal(periodo.ano)
    totais = {c: sum(m[c] for m in serie.values()) for c in itens_svc.chaves_atividades()}
    grafico = {
        "meses": list(MESES),
        "series": [{"rotulo": a.rotulo, "valores": [serie[m][a.chave] for m in MESES]} for a in itens_svc.atividades()],
    }
    return render_template(
        "gestao/setor.html",
        periodo=periodo,
        serie=serie,
        totais=totais,
        total=sum(totais.values()),
        grafico=grafico,
    )
