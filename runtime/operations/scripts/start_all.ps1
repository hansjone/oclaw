param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$WithWeixin = $false,
    [switch]$WithWikiWorker = $false,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WeixinGatewayBaseUrl = ""
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

Write-Step "Starting gateway + desktop"

& "$PSScriptRoot/start_gateway.ps1" -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background

# When gateway is started in foreground, the call above blocks; desktop won't start.
if (-not $Background) {
    Write-Host ""
    Write-Host "[INFO] Gateway started in foreground and will block. Use -Background to start both." -ForegroundColor Yellow
    exit 0
}

& "$PSScriptRoot/start_desktop.ps1" -SkipInstall:$SkipInstall -Background

if ($WithWeixin) {
    $gwBase = ($WeixinGatewayBaseUrl | ForEach-Object { "$_".Trim() })
    if (-not $gwBase) {
        $gwBase = "http://$BindHost`:$Port"
    }
    Write-Step "Starting weixin sidecar"
    & "$PSScriptRoot/weixin_start.ps1" -ChannelId $WeixinChannelId -GatewayBaseUrl $gwBase
}
if ($WithWikiWorker) {
    Write-Step "Starting wiki worker"
    & "$PSScriptRoot/start_wiki_worker.ps1" -Background
}

Write-Host ""
Write-Host "All started." -ForegroundColor Green

