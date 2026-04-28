param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$WithoutWeixin = $false,
    [switch]$WithoutWhatsApp = $false,
    [bool]$WithWikiWorker = $true,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WeixinGatewayBaseUrl = "",
    [string]$WhatsAppChannelId = "whatsapp"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
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

if (-not $WithoutWeixin) {
    $gwBase = ($WeixinGatewayBaseUrl | ForEach-Object { "$_".Trim() })
    if (-not $gwBase) {
        $gwBase = "http://$BindHost`:$Port"
    }
    Write-Step "Starting weixin sidecar"
    try {
        & "$PSScriptRoot/weixin_start.ps1" -ChannelId $WeixinChannelId -GatewayBaseUrl $gwBase
    } catch {
        Warn "weixin sidecar skipped: $($_.Exception.Message)"
    }
}
if (-not $WithoutWhatsApp) {
    $waBase = "http://$BindHost`:$Port"
    Write-Step "Starting whatsapp sidecar"
    try {
        & "$PSScriptRoot/whatsapp_start.ps1" -ChannelId $WhatsAppChannelId -GatewayBaseUrl $waBase
    } catch {
        Warn "whatsapp sidecar skipped: $($_.Exception.Message)"
    }
}
Write-Host ""
Write-Host "All started." -ForegroundColor Green


