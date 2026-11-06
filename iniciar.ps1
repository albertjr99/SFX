# Instala (na primeira vez) e inicia o SFX em um computador Windows da rede.
# Uso: clique duas vezes em INICIAR_SFX.bat  (ou: powershell -ExecutionPolicy Bypass -File iniciar.ps1)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Porta = 8000

function Passo($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }

# 1. Python
Passo "Verificando o Python"
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $python = "py"; $pyArgs = @("-3") } else {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "Python nao encontrado. Instale o Python 3.11 ou mais novo em https://www.python.org/downloads/ (marque 'Add python.exe to PATH') e rode de novo." -ForegroundColor Red
        Read-Host "Enter para sair"; exit 1
    }
    $python = "python"; $pyArgs = @()
}

# 2. Ambiente virtual e dependencias
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Passo "Criando ambiente virtual (.venv)"
    & $python @pyArgs -m venv .venv
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Passo "Instalando/atualizando dependencias"
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r requirements.txt

# 3. Configuracao (.env) na primeira execucao
if (-not (Test-Path ".env")) {
    Passo "Criando configuracao (.env) com chave secreta nova"
    $chave = & $venvPy -c "import secrets; print(secrets.token_hex(32))"
    @(
        "SFX_ENV=production",
        "SECRET_KEY=$chave",
        "SFX_FUSO=America/Sao_Paulo",
        "# Rede interna sem HTTPS: cookies precisam funcionar em http://",
        "SESSION_COOKIE_SECURE=false",
        "# SFX_CONTATOS=Nome <email@orgao.gov.br>; Outro Nome <email@orgao.gov.br>"
    ) | Set-Content -Path ".env" -Encoding ASCII
}

# 4. Banco de dados
Passo "Atualizando o banco de dados (instance\producao.db)"
New-Item -ItemType Directory -Force -Path "instance" | Out-Null
if (Test-Path "instance\producao.db") {
    $backup = "instance\backup-$(Get-Date -Format 'yyyy-MM-dd_HHmm').db"
    Copy-Item "instance\producao.db" $backup
    Write-Host "Backup salvo em $backup"
}
& $venvPy -m flask --app wsgi sfx preparar

# 6. Endereco de acesso
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress
Passo "SFX no ar!"
Write-Host "Neste computador:  http://localhost:$Porta" -ForegroundColor Green
foreach ($ip in $ips) { Write-Host "Para os colegas:   http://${ip}:$Porta" -ForegroundColor Green }
Write-Host "Se o Windows perguntar sobre o Firewall, permita o acesso em 'Redes privadas/de dominio'."
Write-Host "Mantenha esta janela aberta. Para parar: Ctrl+C.`n"

& $venvPy -m waitress --listen="0.0.0.0:$Porta" --threads=8 wsgi:app
