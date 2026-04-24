param(
    [string]$Python = "python",
    [switch]$Recreate = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Fail([string]$msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

$venvDir = Join-Path $repoRoot "oclaw/.venv"
$venvPython = Join-Path $venvDir "Scripts/python.exe"

$py = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $py) {
    Fail "python not found in PATH. Please install Python 3.10+ and retry."
}

if ($Recreate -and (Test-Path $venvDir)) {
    Write-Step "Removing existing venv: $venvDir"
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Write-Step "Creating venv: $venvDir"
    & $Python -m venv $venvDir
}

if (-not (Test-Path $venvPython)) {
    Fail "venv python not found after creation: $venvPython"
}

Write-Step "Upgrading pip"
& $venvPython -m pip install -U pip

Write-Step "Installing requirements"
& $venvPython -m pip install -r "requirements.txt"

Write-Host ""
Write-Host "OK. Next:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File .\\oclaw\\scripts\\start_gateway.ps1"
Write-Host ""
