"""SFX — Sistema de Produção da Subgerência de Fixação."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from . import constants
from .config import CONFIGS
from .extensions import csrf, db, login_manager, migrate

__version__ = "2.0.0"


def create_app(config_name: str | None = None, **overrides) -> Flask:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover
        pass

    config_name = config_name or os.environ.get("SFX_ENV") or os.environ.get("FLASK_ENV") or "production"
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(CONFIGS.get(config_name, CONFIGS["production"]))
    app.config.update(overrides)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "Defina a variável de ambiente SECRET_KEY (veja .env.example). "
            "Para desenvolvimento local use SFX_ENV=development."
        )

    os.makedirs(app.instance_path, exist_ok=True)
    _configurar_logs(app)

    if app.config.get("PROXY_FIX"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(app.root_path), "migrations"))
    csrf.init_app(app)
    login_manager.init_app(app)

    from .models import Usuario

    @login_manager.user_loader
    def carregar_usuario(user_id: str):
        usuario = db.session.get(Usuario, int(user_id))
        return usuario if usuario and usuario.is_active else None

    from .blueprints import admin, auth, gestao, legado, plano, producao

    for bp in (auth.bp, producao.bp, gestao.bp, plano.bp, admin.bp, legado.bp):
        app.register_blueprint(bp)

    from .cli import registrar_comandos

    registrar_comandos(app)
    _registrar_template_helpers(app)
    _registrar_hooks(app)
    _registrar_erros(app)

    @app.get("/healthz")
    def healthz():
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", versao=__version__)

    return app


def _configurar_logs(app: Flask) -> None:
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=os.environ.get("LOG_LEVEL", "INFO"),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )


def _registrar_hooks(app: Flask) -> None:
    livres = {"auth.login", "auth.logout", "auth.trocar_senha", "static", "healthz"}

    @app.before_request
    def exigir_troca_de_senha():
        if current_user.is_authenticated and current_user.precisa_trocar_senha and request.endpoint not in livres:
            return redirect(url_for("auth.trocar_senha"))
        return None

    @app.after_request
    def cabecalhos_de_seguranca(resposta):
        h = resposta.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
            "form-action 'self'",
        )
        if request.endpoint != "static":
            # Páginas contêm dados pessoais de segurados: nada de cache.
            h["Cache-Control"] = "no-store"
        return resposta


def _registrar_erros(app: Flask) -> None:
    mensagens = {
        400: ("Requisição inválida", "O formulário expirou ou veio incompleto. Recarregue a página e tente de novo."),
        403: ("Acesso restrito", "Seu perfil não tem permissão para abrir esta página."),
        404: ("Página não encontrada", "O endereço não existe ou o registro foi removido."),
        413: ("Envio grande demais", "O formulário excedeu o limite permitido."),
        500: ("Erro interno", "Algo falhou do nosso lado. A equipe de sistemas foi avisada pelos logs."),
    }

    def tratar(erro):
        codigo = getattr(erro, "code", 500) or 500
        if codigo == 500:
            db.session.rollback()
        titulo, texto = mensagens.get(codigo, mensagens[500])
        if request.accept_mimetypes.best == "application/json" or request.path.startswith("/api/"):
            return jsonify(erro=titulo, detalhe=texto), codigo
        return render_template("errors/erro.html", codigo=codigo, titulo=titulo, texto=texto), codigo

    for codigo in mensagens:
        app.register_error_handler(codigo, tratar)


def _registrar_template_helpers(app: Flask) -> None:
    fuso = ZoneInfo(app.config["SFX_FUSO"])

    @app.template_filter("data_local")
    def data_local(valor: datetime | None, formato: str = "%d/%m/%Y %H:%M") -> str:
        if not valor:
            return ""
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=UTC)
        return valor.astimezone(fuso).strftime(formato)

    @app.template_filter("numero")
    def numero(valor) -> str:
        if valor is None or valor == "":
            return ""
        try:
            return f"{int(valor):,}".replace(",", ".")
        except (TypeError, ValueError):
            return str(valor)

    @app.template_filter("pct")
    def pct(valor) -> str:
        if valor is None:
            return ""
        return f"{valor:.1f}%".replace(".", ",")

    @app.context_processor
    def contexto_global():
        return {
            "C": constants,
            "config_sfx": {
                "nome": app.config["SFX_NOME_SETOR"],
                "sigla": app.config["SFX_SIGLA"],
                "instituicao": app.config["SFX_INSTITUICAO"],
                "contatos": app.config["SFX_CONTATOS"],
            },
            "versao": __version__,
            "ano_atual": datetime.now(fuso).year,
        }
