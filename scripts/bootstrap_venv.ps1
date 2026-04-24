param()

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\bootstrap_venv.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real @args

