"""Ponto de entrada WSGI: ``gunicorn wsgi:app`` ou ``flask --app wsgi run``."""

from sfx import create_app

app = create_app()
