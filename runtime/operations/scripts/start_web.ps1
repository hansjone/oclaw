param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [bool]$Background = $true,
    [switch]$WithoutWeixin = $false,
    [switch]$WithoutWhatsApp = $false,
    [bool]$WithWikiWorker = $true,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WeixinGatewayBaseUrl = "",
    [string]$WhatsAppChannelId = "whatsapp"
)

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

Write-Step "Starting web stack (gateway + sidecars; desktop excluded)"
& "$PSScriptRoot/start_gateway.ps1" -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background -WithWikiWorker:$WithWikiWorker

if (-not $Background) {
    Write-Host ""
    Write-Host "[INFO] Gateway is running in foreground; sidecars were not started in this mode." -ForegroundColor Yellow
    Write-Host "       Run start_web.ps1 with -Background:`$true for one-command full web startup." -ForegroundColor Yellow
    exit 0
}

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
Write-Host "Web stack started." -ForegroundColor Green

