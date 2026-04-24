param()

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\stop_all.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real @args

