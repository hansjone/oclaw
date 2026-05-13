$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $repoRoot
$env:PYTHONPATH = $repoRoot
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

Write-Step "Project root: $repoRoot"
Write-Step "Working directory: $repoRoot"
Write-Step "Stack status"
& $pythonExe -m runtime.operations stack status

Write-Host ""
Write-Step "WeCom status"
& $pythonExe -m runtime.operations channel wecom status

Write-Host ""
Write-Host "Admin: http://127.0.0.1:8787/admin"
Write-Host "Chat:  http://127.0.0.1:8787/chat"


