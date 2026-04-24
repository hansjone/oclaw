param(
    [string]$ChannelId = "oclaw-weixin",
    [string]$GatewayBaseUrl = "http://127.0.0.1:8787"
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\weixin_start.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -ChannelId $ChannelId -GatewayBaseUrl $GatewayBaseUrl

