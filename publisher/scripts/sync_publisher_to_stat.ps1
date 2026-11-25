# Refresh publisher/ in the stat repo (for GitHub Actions auto-sync).
param(
    [string]$StatRepo = $(if ($env:STAT_REPO_ROOT) { $env:STAT_REPO_ROOT } else { "$env:USERPROFILE\Documents\GitHub\stat" })
)

$ErrorActionPreference = "Stop"
$AbRoot = Split-Path $PSScriptRoot -Parent
$Dest = Join-Path $StatRepo "publisher"

if (-not (Test-Path $StatRepo)) {
    Write-Error "Stat repo not found: $StatRepo"
}

$dirs = @("app", "tools", "templates", "static", "scripts")
foreach ($d in $dirs) {
    $src = Join-Path $AbRoot $d
    $tgt = Join-Path $Dest $d
    if (-not (Test-Path $src)) { continue }
    New-Item -ItemType Directory -Force -Path $tgt | Out-Null
    robocopy $src $tgt /MIR /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

foreach ($f in @("requirements.txt", ".env.example")) {
    Copy-Item -Force (Join-Path $AbRoot $f) (Join-Path $Dest $f)
}

New-Item -ItemType Directory -Force -Path (Join-Path $Dest "data") | Out-Null
Write-Host "Publisher synced to $Dest"
Write-Host "Commit stat repo: publisher/ + .github/workflows/publish-news.yml"