param(
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [bool]$WithWikiWorker = $true
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_desktop.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -SkipInstall:$SkipInstall -Background:$Background -WithWikiWorker:$WithWikiWorker

