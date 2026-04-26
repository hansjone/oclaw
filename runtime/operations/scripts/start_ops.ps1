param(
    [string]$Channel = "wecom",
    [switch]$SkipInstall = $false,
    [switch]$SkipConfigHint = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Fail([string]$msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repoParent = Split-Path -Parent $repoRoot
Set-Location $repoRoot

Write-Step "Project root: $repoRoot"
Write-Step "Working directory: $repoRoot"

$env:PYTHONPATH = $repoParent
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (Test-Path $venvPython) {
    Write-Step "Using venv python: $venvPython"
    $pythonExe = $venvPython
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Fail "python not found in PATH. Please install Python 3.10+ and retry."
    }
    Write-Step "Python detected: $($pythonCmd.Source)"
    $pythonExe = "python"
}

if (-not $SkipInstall) {
    Write-Step "Installing dependencies (pip install -r requirements.txt)"
    & $pythonExe -m pip install -r (Join-Path $repoRoot "requirements.txt")
} else {
    Write-Step "Skip dependency install"
}

if (-not $SkipConfigHint) {
    Write-Step "Current WeCom status"
    try {
        & $pythonExe -m oclaw.runtime.operations channel wecom status
    } catch {
        Write-Host "[WARN] Unable to read WeCom status yet." -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "If WeCom is not configured yet, run this first:" -ForegroundColor Yellow
    Write-Host "  python -m oclaw.runtime.operations channel wecom config --help"
    Write-Host ""
}

Write-Step "Stopping previous stack (safe if not running)"
& $pythonExe -m oclaw.runtime.operations stack down

Write-Step "Starting stack: python -m oclaw.runtime.operations stack up --channel $Channel"
& $pythonExe -m oclaw.runtime.operations stack up --channel $Channel

Write-Host ""
Write-Host "Started successfully." -ForegroundColor Green
Write-Host "Admin: http://127.0.0.1:8787/admin"
Write-Host "Chat:  http://127.0.0.1:8787/chat"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  python -m oclaw.runtime.operations stack status"
Write-Host "  python -m oclaw.runtime.operations stack down"



