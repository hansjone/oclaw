param(
    [string]$Channel = "wecom",
    [switch]$SkipInstall = $false,
    [switch]$SkipConfigHint = $false,
    [switch]$Background = $false
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_ops.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -Channel $Channel -SkipInstall:$SkipInstall -SkipConfigHint:$SkipConfigHint -Background:$Background

