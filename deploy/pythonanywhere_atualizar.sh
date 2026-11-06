#!/usr/bin/env bash
# Atualiza o SFX no PythonAnywhere com a última versão do GitHub (o banco é preservado).
#   bash ~/SFX/deploy/pythonanywhere_atualizar.sh
set -euo pipefail
cd "$HOME/SFX"
mkdir -p "$HOME/backups"
[ -f instance/producao.db ] && cp instance/producao.db "$HOME/backups/producao-$(date +%Y-%m-%d_%H%M).db"
ls -1t "$HOME"/backups/producao-*.db 2>/dev/null | tail -n +15 | xargs -r rm --   # guarda os 14 mais recentes
git pull --ff-only
# shellcheck disable=SC1091
source "$HOME/.virtualenvs/sfx/bin/activate"
pip install --quiet -r requirements.txt
flask --app wsgi sfx preparar
touch "/var/www/${USER}_pythonanywhere_com_wsgi.py"   # recarrega o site
echo "Atualizado. Backup do banco em ~/backups/."
