param(
    [int]$Port = 8787,
    [switch]$Force = $false
)

# 网页端（/admin、/chat）由网关进程提供，这里只是一个语义化别名。
& "$PSScriptRoot/stop_gateway.ps1" -Port $Port -Force:$Force

