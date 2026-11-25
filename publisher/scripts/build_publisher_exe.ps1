$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\pip install -r requirements.txt pyinstaller -q

.\.venv\Scripts\pyinstaller `
    --noconfirm `
    --onefile `
    --name DetailzPublisher `
    --paths . `
    --collect-data feedparser `
    --hidden-import=app.sync `
    --hidden-import=app.enrich `
    --hidden-import=app.static_export `
    --hidden-import=app.git_publish `
    tools\detailz_publisher.py

Write-Host "Built: dist\DetailzPublisher.exe"