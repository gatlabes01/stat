$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Create venv first: python -m venv .venv"
    exit 1
}

.\.venv\Scripts\python tools\detailz_publisher.py --deploy cloudflare