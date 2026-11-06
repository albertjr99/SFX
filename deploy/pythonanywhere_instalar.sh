#!/usr/bin/env bash
# Instala o SFX numa conta do PythonAnywhere. Rode num "Bash console":
#   git clone https://github.com/albertjr99/SFX.git ~/SFX && bash ~/SFX/deploy/pythonanywhere_instalar.sh
set -euo pipefail
PROJ="$HOME/SFX"
VENV="$HOME/.virtualenvs/sfx"
cd "$PROJ"

PY=""
for v in 3.13 3.12 3.11; do
  if command -v "python$v" >/dev/null 2>&1; then PY="python$v"; break; fi
done
[ -n "$PY" ] || { echo "Nenhum Python 3.11+ encontrado."; exit 1; }
echo "==> Usando $PY"

[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Criando .env com chave secreta nova"
  cat > .env <<CONF
SFX_ENV=production
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
SFX_FUSO=America/Sao_Paulo
SESSION_COOKIE_SECURE=true
PROXY_FIX=true
# SFX_CONTATOS=Nome <email@orgao.gov.br>; Outro Nome <email@orgao.gov.br>
CONF
fi

echo "==> Preparando o banco"
flask --app wsgi sfx preparar

cat <<FIM

============================================================
 Quase lá! Agora, na aba "Web" do PythonAnywhere:

 1. "Add a new web app" → Next → "Manual configuration"
    → escolha $PY → Next.
 2. Em "Virtualenv", informe:   $VENV
 3. Em "Static files" adicione:
      URL:       /static/
      Directory: $PROJ/sfx/static
 4. Abra o "WSGI configuration file", apague tudo e cole
    o conteúdo de:  $PROJ/deploy/pythonanywhere_wsgi.py
 5. Ligue "Force HTTPS" e clique no botão verde "Reload".

 Endereço: https://${USER,,}.pythonanywhere.com
============================================================
FIM
