param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repoParent = Split-Path -Parent $repoRoot
Set-Location $repoParent
$env:PYTHONPATH = $repoParent

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

Write-Step "Project root: $repoRoot"
Write-Step "Working directory: $repoParent"
Write-Step "Stopping stack services..."

try {
    & $pythonExe -m oclaw.runtime.operations stack down
    Write-Host "Stack stopped." -ForegroundColor Green
} catch {
    Write-Host "[WARN] stack down failed: $($_.Exception.Message)" -ForegroundColor Yellow
    if (-not $Force) {
        exit 1
    }
}

Write-Step "Current status"
try {
    & $pythonExe -m oclaw.runtime.operations stack status
} catch {
    Write-Host "[WARN] Unable to read status after stop." -ForegroundColor Yellow
}


