FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SFX_ENV=production \
    TZ=America/Sao_Paulo

WORKDIR /app
RUN useradd --create-home --uid 1000 sfx
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=sfx:sfx . .
RUN mkdir -p /app/instance && chown sfx:sfx /app/instance

USER sfx
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

# Aplica migrações pendentes e sobe o servidor
CMD ["sh", "-c", "flask --app wsgi db upgrade && exec gunicorn wsgi:app --workers 2 --threads 4 --bind 0.0.0.0:8000 --access-logfile -"]
