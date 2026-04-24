param()

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_web.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real @args

