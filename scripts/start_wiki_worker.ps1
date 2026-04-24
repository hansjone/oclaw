param(
    [switch]$Background = $false
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_wiki_worker.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -Background:$Background

