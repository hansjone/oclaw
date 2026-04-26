param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [bool]$WithWikiWorker = $true
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_gateway.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background -WithWikiWorker:$WithWikiWorker

