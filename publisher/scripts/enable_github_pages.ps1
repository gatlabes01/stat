# Enable GitHub Pages: branch main, folder /site
# One-time setup (after gh auth login):
#   winget install GitHub.cli
#   gh auth login
#   powershell -File .\scripts\enable_github_pages.ps1

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "Install GitHub CLI first: winget install GitHub.cli"
    exit 1
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host "Sign in first: gh auth login"
    exit 1
}

$owner = "gatlabes01"
$repo = "ab"
$jsonPath = Join-Path $env:TEMP "pages-config.json"
@'
{"build_type":"legacy","source":{"branch":"main","path":"/site"}}
'@ | Set-Content -Path $jsonPath -Encoding utf8NoBOM

gh api -X POST "/repos/$owner/$repo/pages" --input $jsonPath
if ($LASTEXITCODE -ne 0) {
    gh api -X PUT "/repos/$owner/$repo/pages" --input $jsonPath
}

Write-Host ""
Write-Host "Done. Site URL: https://$owner.github.io/$repo/"
gh api "/repos/$owner/$repo/pages"