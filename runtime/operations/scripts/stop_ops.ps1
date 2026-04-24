param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

Write-Step "Project root: $repoRoot"
Write-Step "Stopping stack services..."

try {
    python -m oclaw.runtime.operations stack down
    Write-Host "Stack stopped." -ForegroundColor Green
} catch {
    Write-Host "[WARN] stack down failed: $($_.Exception.Message)" -ForegroundColor Yellow
    if (-not $Force) {
        exit 1
    }
}

Write-Step "Current status"
try {
    python -m oclaw.runtime.operations stack status
} catch {
    Write-Host "[WARN] Unable to read status after stop." -ForegroundColor Yellow
}

