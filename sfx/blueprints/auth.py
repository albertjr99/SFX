from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_

from ..extensions import db
from ..models import Usuario
from ..security import limitador_login, problemas_senha

bp = Blueprint("auth", __name__)


def destino_inicial(usuario: Usuario) -> str:
    if usuario.eh_analista:
        return url_for("producao.minha_producao")
    if usuario.eh_gestor:
        return url_for("gestao.painel")
    if usuario.edita_equipe:
        return url_for("producao.equipe")
    return url_for("auth.trocar_senha")


def _proximo_seguro(valor: str | None) -> str | None:
    if not valor:
        return None
    partes = urlsplit(valor)
    if partes.scheme or partes.netloc or not valor.startswith("/"):
        return None
    return valor


@bp.get("/")
def inicio():
    if current_user.is_authenticated:
        return redirect(destino_inicial(current_user))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(destino_inicial(current_user))

    identificador = ""
    if request.method == "POST":
        identificador = (request.form.get("usuario") or "").strip()
        senha = request.form.get("senha") or ""
        chave = f"{request.remote_addr}|{identificador.lower()}"

        if limitador_login.bloqueado(chave):
            flash("Muitas tentativas seguidas. Aguarde alguns minutos e tente de novo.", "erro")
            return render_template("auth/login.html", identificador=identificador), 429

        usuario = Usuario.query.filter(
            or_(
                func.lower(Usuario.nome) == identificador.lower(),
                func.lower(Usuario.email) == identificador.lower(),
            )
        ).first()

        if usuario and usuario.is_active and usuario.confere_senha(senha):
            limitador_login.sucesso(chave)
            login_user(usuario, remember=bool(request.form.get("lembrar")))
            if usuario.precisa_trocar_senha:
                flash("Bem-vindo! Defina sua senha pessoal para continuar.", "info")
                return redirect(url_for("auth.trocar_senha"))
            return redirect(_proximo_seguro(request.args.get("next")) or destino_inicial(usuario))

        limitador_login.falhou(chave)
        if usuario and not usuario.is_active:
            flash("Este acesso está desativado. Procure a gerência.", "erro")
        else:
            flash("Usuário ou senha incorretos.", "erro")

    return render_template("auth/login.html", identificador=identificador)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/conta/senha", methods=["GET", "POST"])
@login_required
def trocar_senha():
    obrigatoria = current_user.precisa_trocar_senha
    if request.method == "POST":
        atual = request.form.get("senha_atual") or ""
        nova = request.form.get("nova_senha") or ""
        confirmacao = request.form.get("confirmacao") or ""

        erros = []
        if not current_user.confere_senha(atual):
            erros.append("A senha atual não confere.")
        erros += problemas_senha(nova, confirmacao)
        if nova and nova == atual:
            erros.append("A nova senha precisa ser diferente da atual.")

        if erros:
            for erro in erros:
                flash(erro, "erro")
        else:
            current_user.definir_senha(nova)
            db.session.commit()
            flash("Senha atualizada.", "sucesso")
            return redirect(destino_inicial(current_user))

    return render_template("auth/senha.html", obrigatoria=obrigatoria)
