param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false
)

# 网页端（/admin、/chat）由网关进程提供，这里只是一个语义化别名。
& "$PSScriptRoot/start_gateway.ps1" -BindHost $BindHost -Port $Port -SkipInstall:$SkipInstall -Background:$Background

