param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$WithWeixin = $false,
    [bool]$WithWikiWorker = $true,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WeixinGatewayBaseUrl = ""
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repoParent = Split-Path -Parent $repoRoot
Set-Location $repoRoot
$env:PYTHONPATH = $repoParent
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

Write-Step "Starting gateway + desktop"

& "$PSScriptRoot/start_gateway.ps1" -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background -WithWikiWorker:$WithWikiWorker

# When gateway is started in foreground, the call above blocks; desktop won't start.
if (-not $Background) {
    Write-Host ""
    Write-Host "[INFO] Gateway started in foreground and will block. Use -Background to start both." -ForegroundColor Yellow
    exit 0
}

& "$PSScriptRoot/start_desktop.ps1" -SkipInstall:$SkipInstall -Background -WithWikiWorker:$WithWikiWorker

if ($WithWeixin) {
    $gwBase = ($WeixinGatewayBaseUrl | ForEach-Object { "$_".Trim() })
    if (-not $gwBase) {
        $gwBase = "http://$BindHost`:$Port"
    }
    Write-Step "Starting weixin sidecar"
    & "$PSScriptRoot/weixin_start.ps1" -ChannelId $WeixinChannelId -GatewayBaseUrl $gwBase
}
Write-Host ""
Write-Host "All started." -ForegroundColor Green


