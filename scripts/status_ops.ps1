$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

Write-Step "Project root: $repoRoot"
Write-Step "Stack status"
python -m oclaw.ops stack status

Write-Host ""
Write-Step "WeCom status"
python -m oclaw.ops channel wecom status

Write-Host ""
Write-Host "Admin: http://127.0.0.1:8787/admin"
Write-Host "Chat:  http://127.0.0.1:8787/chat"

