"""Redirecionamentos dos endereços da versão 1 (favoritos antigos continuam funcionando)."""

from flask import Blueprint, redirect, request, url_for

bp = Blueprint("legado", __name__)

_MAPA = {
    "/registrar-producao": "producao.minha_producao",
    "/acompanhamento-pessoal": "producao.estatisticas",
    "/painel-gerente": "gestao.painel",
    "/acompanhamento-anual": "gestao.setor",
    "/relatorio-geral": "gestao.setor",
    "/painel-estagiarias": "producao.equipe",
}


def _redirecionar(endpoint: str):
    def view():
        return redirect(url_for(endpoint, **request.args.to_dict()), code=301)

    view.__name__ = endpoint.replace(".", "_")
    return view


for caminho, destino in _MAPA.items():
    bp.add_url_rule(caminho, endpoint=caminho.strip("/").replace("-", "_"), view_func=_redirecionar(destino))


@bp.get("/acompanhamento-analista")
def acompanhamento_analista():
    analista_id = request.args.get("analista_id", type=int)
    if analista_id:
        return redirect(url_for("gestao.analista", analista_id=analista_id), code=301)
    return redirect(url_for("gestao.painel"), code=301)
