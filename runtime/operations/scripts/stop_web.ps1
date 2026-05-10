param(
    [int]$Port = 8787,
    [switch]$Force = $false,
    [switch]$WithoutWeixin = $false,
    [switch]$WithoutWhatsApp = $false,
    [bool]$WithWikiWorker = $true,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WhatsAppChannelId = "whatsapp"
)

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Step "Stopping web stack (gateway + sidecars; desktop excluded)"

if (-not $WithoutWeixin) {
    Write-Step "Stopping weixin sidecar"
    try {
        & "$PSScriptRoot/weixin_stop.ps1" -ChannelId $WeixinChannelId -Force:$Force
    } catch {
        if (-not $Force) { throw }
    }
}
if (-not $WithoutWhatsApp) {
    Write-Step "Stopping whatsapp sidecar"
    try {
        & "$PSScriptRoot/whatsapp_stop.ps1" -ChannelId $WhatsAppChannelId -Force:$Force
    } catch {
        if (-not $Force) { throw }
    }
}

Write-Step "Stopping gateway/web"
try {
    & "$PSScriptRoot/stop_gateway.ps1" -Port $Port -Force:$Force
} catch {
    if (-not $Force) { throw }
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
Write-Host "Web stack stopped." -ForegroundColor Green

