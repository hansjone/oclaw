param(
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$KeepExistingGateway = $false,
    [string]$GatewayBaseUrl = "",
    [bool]$WithWikiWorker = $true
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_desktop.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -SkipInstall:$SkipInstall -Background:$Background -KeepExistingGateway:$KeepExistingGateway -GatewayBaseUrl $GatewayBaseUrl -WithWikiWorker:$WithWikiWorker

