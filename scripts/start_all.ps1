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

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\start_all.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background -WithWeixin:$WithWeixin -WithWikiWorker:$WithWikiWorker -WeixinChannelId $WeixinChannelId -WeixinGatewayBaseUrl $WeixinGatewayBaseUrl

