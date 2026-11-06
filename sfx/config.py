"""Configuração por variáveis de ambiente (12-factor).

Valores sensíveis (SECRET_KEY, DATABASE_URL) nunca ficam no código: em
produção a aplicação se recusa a subir sem SECRET_KEY definida.
"""

from __future__ import annotations

import os
from datetime import timedelta


def _bool(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _contatos() -> list[dict[str, str]]:
    """SFX_CONTATOS="Nome <email>; Outro Nome <email>"."""
    bruto = os.environ.get("SFX_CONTATOS", "").strip()
    contatos = []
    for item in filter(None, (p.strip() for p in bruto.split(";"))):
        if "<" in item and item.endswith(">"):
            nome, email = item[:-1].split("<", 1)
            contatos.append({"nome": nome.strip(), "email": email.strip()})
        else:
            contatos.append({"nome": item, "email": ""})
    return contatos


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///producao.db")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    WTF_CSRF_TIME_LIMIT = None  # o token vale enquanto a sessão durar
    # A grade mensal envia muitos campos; o padrão do Werkzeug é 1000.
    MAX_FORM_PARTS = 20_000
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    SFX_NOME_SETOR = os.environ.get("SFX_NOME_SETOR", "Subgerência de Fixação")
    SFX_SIGLA = os.environ.get("SFX_SIGLA", "SFX")
    SFX_INSTITUICAO = os.environ.get("SFX_INSTITUICAO", "IPAJM")
    SFX_FUSO = os.environ.get("SFX_FUSO", "America/Sao_Paulo")
    SFX_CONTATOS = _contatos()
    SFX_TENTATIVAS_LOGIN = int(os.environ.get("SFX_TENTATIVAS_LOGIN", "5"))
    SFX_JANELA_LOGIN_MIN = int(os.environ.get("SFX_JANELA_LOGIN_MIN", "10"))
    SFX_SENHA_MINIMA = int(os.environ.get("SFX_SENHA_MINIMA", "8"))

    PROXY_FIX = _bool("PROXY_FIX", False)


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = Config.SECRET_KEY or "dev-inseguro-troque-em-producao"


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "teste"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    SFX_CONTATOS = [{"nome": "Suporte", "email": "suporte@example.com"}]


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
