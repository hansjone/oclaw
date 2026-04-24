param(
    [string]$ChannelId = "oclaw-weixin"
)

$ErrorActionPreference = "Stop"

$real = Join-Path $PSScriptRoot "..\\runtime\\operations\\scripts\\weixin_login.ps1"
if (-not (Test-Path $real)) {
    throw "Forward script target not found: $real"
}

& $real -ChannelId $ChannelId

