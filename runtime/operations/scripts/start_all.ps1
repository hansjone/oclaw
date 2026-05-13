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

$repoRoot = $null
function Resolve-RepoRoot([string]$fromDir) {
    $cur = (Resolve-Path $fromDir).Path
    for ($i = 0; $i -lt 12; $i++) {
        $cfg = Join-Path $cur "oclaw.json"
        if (Test-Path $cfg) {
            return $cur
        }
        $parent = Split-Path -Parent $cur
        if (-not $parent -or $parent -eq $cur) {
            break
        }
        $cur = $parent
    }
    return $null
}

$repoRoot = Resolve-RepoRoot $PSScriptRoot
if (-not $repoRoot) {
    # Fallback: old relative layout assumption
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}
Set-Location $repoRoot
$env:PYTHONPATH = $repoRoot
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

Write-Step "Starting gateway + desktop"

& "$PSScriptRoot/start_gateway.ps1" -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background -WithWikiWorker:$WithWikiWorker

# When gateway is started in foreground, the call above blocks; desktop / sidecars won't run in this script.
if (-not $Background) {
    Write-Host ""
    Write-Host "[INFO] Gateway is running in the foreground (this window blocks). Desktop was not started." -ForegroundColor Yellow
    Write-Host "       For gateway + desktop + sidecars in one go, run:  start_all.ps1 -Background" -ForegroundColor Yellow
    Write-Host "       Or start desktop in another terminal after the gateway is listening:  start_desktop.ps1 -Background -KeepExistingGateway" -ForegroundColor Yellow
    exit 0
}

# start_desktop.ps1 defaults to stop_gateway.ps1 to free the port when launching desktop alone.
# After start_gateway above we must keep the listener — pass -KeepExistingGateway.
$gwUrl = "http://$BindHost`:$Port"
& "$PSScriptRoot/start_desktop.ps1" -SkipInstall:$SkipInstall -Background -WithWikiWorker:$WithWikiWorker -KeepExistingGateway -GatewayBaseUrl $gwUrl

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


