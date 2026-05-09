param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = $null
function Resolve-RepoRoot([string]$fromDir) {
    $cur = (Resolve-Path $fromDir).Path
    for ($i = 0; $i -lt 12; $i++) {
        $cfg = Join-Path $cur "oclaw.json"
        if (Test-Path $cfg) {
            return $cur
        }
        $parent = Split-Path -Parent $cur
        if (-not $parent -or $parent -eq $cur) {
            break
        }
        $cur = $parent
    }
    return $null
}

$repoRoot = Resolve-RepoRoot $PSScriptRoot
if (-not $repoRoot) {
    # Fallback: old relative layout assumption
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}
$repoParent = Split-Path -Parent $repoRoot
Set-Location $repoRoot
$env:PYTHONPATH = $repoParent
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


