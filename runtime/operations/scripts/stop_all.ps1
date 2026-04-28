param(
    [int]$Port = 8787,
    [switch]$Force = $false,
    [switch]$WithoutWeixin = $false,
    [switch]$WithWikiWorker = $false,
    [string]$WeixinChannelId = "oclaw-weixin"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Step "Stopping desktop"
try {
    & "$PSScriptRoot/stop_desktop.ps1" -Force:$Force
} catch {
    if (-not $Force) { throw }
}

Write-Step "Stopping gateway/web"
try {
    & "$PSScriptRoot/stop_gateway.ps1" -Port $Port -Force:$Force
} catch {
    if (-not $Force) { throw }
}

if (-not $WithoutWeixin) {
    Write-Step "Stopping weixin sidecar"
    try {
        & "$PSScriptRoot/weixin_stop.ps1" -ChannelId $WeixinChannelId -Force:$Force
    } catch {
        if (-not $Force) { throw }
    }
}
if ($WithWikiWorker) {
    Write-Step "Stopping wiki worker"
    try {
        & "$PSScriptRoot/stop_wiki_worker.ps1" -Force:$Force
    } catch {
        if (-not $Force) { throw }
    }
}

Write-Host ""
Write-Host "All stopped." -ForegroundColor Green

