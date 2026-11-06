"""Gestão de usuários (perfis de gestão)."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from ..constants import MODALIDADES, PERFIL_ADMIN, PERFIL_ANALISTA, PERFIS
from ..extensions import db
from ..models import Usuario
from ..security import exige, senha_provisoria

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _perfis_atribuiveis() -> dict[str, str]:
    # Só um administrador cria outro administrador.
    if current_user.tipo == PERFIL_ADMIN:
        return PERFIS
    return {k: v for k, v in PERFIS.items() if k != PERFIL_ADMIN}


@bp.get("/usuarios")
@exige("eh_gestor")
def usuarios():
    lista = Usuario.query.order_by(Usuario.ativo.desc(), Usuario.tipo, Usuario.nome).all()
    return render_template(
        "admin/usuarios.html",
        usuarios=lista,
        perfis=_perfis_atribuiveis(),
        modalidades=MODALIDADES,
        senha_gerada=None,
    )


def _ler_formulario(usuario: Usuario) -> list[str]:
    erros = []
    nome = (request.form.get("nome") or "").strip()[:50]
    email = (request.form.get("email") or "").strip().lower()[:100]
    tipo = request.form.get("tipo") or ""
    modalidade = request.form.get("modalidade") or ""

    if not nome:
        erros.append("Informe o nome.")
    if "@" not in email:
        erros.append("Informe um e-mail válido.")
    if tipo not in _perfis_atribuiveis():
        erros.append("Perfil inválido.")
    if tipo == PERFIL_ANALISTA and modalidade not in MODALIDADES:
        erros.append("Analistas precisam de modalidade (presencial ou teletrabalho).")

    duplicado_nome = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower(), Usuario.id != usuario.id).first()
    if nome and duplicado_nome:
        erros.append("Já existe alguém com esse nome — ele é usado no login.")
    duplicado_email = Usuario.query.filter(func.lower(Usuario.email) == email, Usuario.id != usuario.id).first()
    if email and duplicado_email:
        erros.append("Já existe alguém com esse e-mail.")

    if not erros:
        usuario.nome = nome
        usuario.email = email
        usuario.tipo = tipo
        usuario.modalidade = modalidade if tipo == PERFIL_ANALISTA else ""
        usuario.pode_plano_acao = bool(request.form.get("pode_plano_acao"))
    return erros


def _render_com_senha(usuario: Usuario, senha: str):
    flash(f"Senha provisória de {usuario.nome} gerada. Ela aparece só desta vez.", "sucesso")
    return render_template(
        "admin/usuarios.html",
        usuarios=Usuario.query.order_by(Usuario.ativo.desc(), Usuario.tipo, Usuario.nome).all(),
        perfis=_perfis_atribuiveis(),
        modalidades=MODALIDADES,
        senha_gerada={"usuario": usuario, "senha": senha},
    )


@bp.post("/usuarios/novo")
@exige("eh_gestor")
def criar():
    usuario = Usuario(ativo=True)
    erros = _ler_formulario(usuario)
    if erros:
        for e in erros:
            flash(e, "erro")
        return redirect(url_for("admin.usuarios"))
    senha = senha_provisoria()
    usuario.definir_senha(senha, provisoria=True)
    db.session.add(usuario)
    db.session.commit()
    return _render_com_senha(usuario, senha)


@bp.post("/usuarios/<int:usuario_id>")
@exige("eh_gestor")
def editar(usuario_id: int):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    if usuario.tipo == PERFIL_ADMIN and current_user.tipo != PERFIL_ADMIN:
        abort(403)
    acao = request.form.get("acao", "salvar")

    if acao == "redefinir_senha":
        senha = senha_provisoria()
        usuario.definir_senha(senha, provisoria=True)
        db.session.commit()
        return _render_com_senha(usuario, senha)

    if acao == "alternar_ativo":
        if usuario.id == current_user.id:
            flash("Você não pode desativar o próprio acesso.", "erro")
        else:
            usuario.ativo = not usuario.ativo
            db.session.commit()
            flash(f"{usuario.nome} {'reativado' if usuario.ativo else 'desativado'}.", "sucesso")
        return redirect(url_for("admin.usuarios"))

    erros = _ler_formulario(usuario)
    if erros:
        db.session.rollback()
        for e in erros:
            flash(e, "erro")
    else:
        db.session.commit()
        flash(f"Dados de {usuario.nome} atualizados.", "sucesso")
    return redirect(url_for("admin.usuarios"))
