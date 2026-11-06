"""Gestão de usuários.

* Perfis de gestão cadastram, editam, redefinem senha e desativam a equipe.
* Administradores fazem tudo isso com qualquer pessoa (inclusive outros
  administradores), concedem/retiram o acesso de administrador e excluem
  acessos definitivamente.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from ..constants import MODALIDADES, PERFIL_ADMIN, PERFIL_ANALISTA, PERFIS
from ..extensions import db
from ..models import LinhaProducao, Usuario
from ..security import exige, senha_provisoria

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _perfis_atribuiveis() -> dict[str, str]:
    if current_user.eh_admin:
        return PERFIS
    return {k: v for k, v in PERFIS.items() if k != PERFIL_ADMIN}


def _admins_ativos(exceto: int | None = None) -> int:
    consulta = Usuario.query.filter(
        Usuario.ativo.is_(True),
        or_(Usuario.administrador.is_(True), Usuario.tipo == PERFIL_ADMIN),
    )
    if exceto is not None:
        consulta = consulta.filter(Usuario.id != exceto)
    return consulta.count()


def _lista():
    usuarios = Usuario.query.order_by(Usuario.ativo.desc(), Usuario.tipo, Usuario.nome).all()
    registros = dict(
        db.session.query(LinhaProducao.usuario_id, func.count(LinhaProducao.id))
        .group_by(LinhaProducao.usuario_id)
        .all()
    )
    return usuarios, registros


def _render(senha_gerada=None):
    usuarios, registros = _lista()
    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios,
        registros=registros,
        perfis=_perfis_atribuiveis(),
        modalidades=MODALIDADES,
        senha_gerada=senha_gerada,
    )


@bp.get("/usuarios")
@exige("eh_gestor")
def usuarios():
    return _render()


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

    administrador = bool(usuario.administrador)
    if current_user.eh_admin:
        administrador = bool(request.form.get("administrador"))
        perde_admin = usuario.id is not None and usuario.eh_admin and not (administrador or tipo == PERFIL_ADMIN)
        if perde_admin and usuario.id == current_user.id:
            erros.append("Você não pode retirar o próprio acesso de administrador.")
        elif perde_admin and _admins_ativos(exceto=usuario.id) == 0:
            erros.append("O sistema precisa de pelo menos um administrador ativo.")

    if not erros:
        usuario.nome = nome
        usuario.email = email
        usuario.tipo = tipo
        usuario.modalidade = modalidade if tipo == PERFIL_ANALISTA else ""
        usuario.pode_plano_acao = bool(request.form.get("pode_plano_acao"))
        usuario.administrador = administrador
    return erros


def _render_com_senha(usuario: Usuario, senha: str):
    flash(f"Senha provisória de {usuario.nome} gerada. Ela aparece só desta vez.", "sucesso")
    return _render({"usuario": usuario, "senha": senha})


@bp.post("/usuarios/novo")
@exige("eh_gestor")
def criar():
    usuario = Usuario(ativo=True, administrador=False)
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
    # Só administradores mexem em contas de administrador.
    if usuario.eh_admin and not current_user.eh_admin:
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
        elif usuario.ativo and usuario.eh_admin and _admins_ativos(exceto=usuario.id) == 0:
            flash("O sistema precisa de pelo menos um administrador ativo.", "erro")
        else:
            usuario.ativo = not usuario.ativo
            db.session.commit()
            flash(f"{usuario.nome} {'reativado' if usuario.ativo else 'desativado'}.", "sucesso")
        return redirect(url_for("admin.usuarios"))

    if acao == "excluir":
        return _excluir(usuario)

    erros = _ler_formulario(usuario)
    if erros:
        db.session.rollback()
        for e in erros:
            flash(e, "erro")
    else:
        db.session.commit()
        flash(f"Dados de {usuario.nome} atualizados.", "sucesso")
    return redirect(url_for("admin.usuarios"))


def _excluir(usuario: Usuario):
    if not current_user.eh_admin:
        abort(403)
    if usuario.id == current_user.id:
        flash("Você não pode excluir o próprio acesso.", "erro")
        return redirect(url_for("admin.usuarios"))
    if usuario.eh_admin and _admins_ativos(exceto=usuario.id) == 0:
        flash("O sistema precisa de pelo menos um administrador ativo.", "erro")
        return redirect(url_for("admin.usuarios"))
    producao = LinhaProducao.query.filter_by(usuario_id=usuario.id).count()
    if producao:
        flash(
            f"{usuario.nome} tem {producao} registro(s) de produção. Para não apagar o histórico, "
            "desative o acesso em vez de excluir.",
            "erro",
        )
        return redirect(url_for("admin.usuarios"))
    # Linhas de outras pessoas alteradas por este usuário perdem só a autoria.
    LinhaProducao.query.filter_by(atualizado_por_id=usuario.id).update({"atualizado_por_id": None})
    nome = usuario.nome
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Acesso de {nome} excluído.", "sucesso")
    return redirect(url_for("admin.usuarios"))
