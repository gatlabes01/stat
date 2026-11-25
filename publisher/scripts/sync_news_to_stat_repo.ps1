# Copy exported TMZ site from ab -> gatlabes01/stat repo as news/
#
# Usage:
#   $env:STAT_REPO_ROOT = "C:\path\to\stat"
#   powershell -File .\scripts\sync_news_to_stat_repo.ps1
#
# Then open the stat repo in GitHub Desktop, commit, push.

param(
    [string]$StatRepo = $(if ($env:STAT_REPO_ROOT) { $env:STAT_REPO_ROOT } else { "$env:USERPROFILE\Documents\GitHub\stat" }),
    [string]$SourceNews = ""
)

$ErrorActionPreference = "Stop"
$AbRoot = Split-Path $PSScriptRoot -Parent

if (-not $StatRepo) {
    Write-Host "Set STAT_REPO_ROOT to your local clone of gatlabes01/stat"
    Write-Host 'Example: $env:STAT_REPO_ROOT = "C:\Users\PC\Desktop\stat"'
    exit 1
}

if (-not $SourceNews) {
    $SourceNews = Join-Path $AbRoot "site\news"
}

if (-not (Test-Path $SourceNews)) {
    Write-Host "Run export first: python tools\detailz_publisher.py --export-only --no-deploy"
    exit 1
}

if (-not (Test-Path $StatRepo)) {
    Write-Host "Stat repo path not found: $StatRepo"
    exit 1
}

$Dest = Join-Path $StatRepo "news"
if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
}
Copy-Item -Recurse -Force $SourceNews $Dest

Write-Host "Copied to: $Dest"
Write-Host "Next: GitHub Desktop -> stat repo -> commit 'Add news feed' -> push"
Write-Host "Live URL after deploy: https://detailz.xyz/news/"